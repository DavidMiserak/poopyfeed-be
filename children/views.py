from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import ChildForm
from .mixins import ChildAccessMixin, ChildEditMixin, ChildOwnerMixin
from .models import Child, ChildShare, ShareInvite

URL_CHILD_LIST = "children:child_list"
URL_CHILD_SHARING = "children:child_sharing"

# Number of recent activities to show on dashboard (merged feed)
DASHBOARD_RECENT_ACTIVITY_LIMIT = 10


class ChildListView(LoginRequiredMixin, ListView):
    model = Child
    template_name = "children/child_list.html"
    context_object_name = "children"

    def dispatch(self, request, *args, **kwargs):
        """Prevent browser from caching this page.

        Forces browsers to always fetch fresh HTML when viewing the child list,
        ensuring users see updated last-activity timestamps after logging
        tracking records (diapers, feedings, naps). The cache invalidation
        signals fire when tracking records are saved, but browsers may serve
        cached HTML without this header.
        """
        response = super().dispatch(request, *args, **kwargs)
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response

    def get_queryset(self):
        return (
            Child.objects.filter(
                Q(parent=self.request.user) | Q(shares__user=self.request.user)
            )
            .prefetch_related("shares__user")
            .distinct()
            # Annotations will be applied in get_context_data via cache_utils
            # to avoid expensive Max() aggregations on every request
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Apply cached last-activity annotations
        from .cache_utils import get_child_last_activities

        children = context["children"]
        if children:
            child_ids = [child.id for child in children]
            activities = get_child_last_activities(child_ids)
            for child in children:
                activity = activities.get(child.id, {})
                child.last_diaper_change = activity.get("last_diaper_change")
                child.last_nap = activity.get("last_nap")
                child.last_feeding = activity.get("last_feeding")

        # Add role info for each child
        children_with_roles = []
        for child in children:
            children_with_roles.append(
                {
                    "child": child,
                    "role": child.get_user_role(self.request.user),
                    "can_edit": child.can_edit(self.request.user),
                    "is_owner": child.parent == self.request.user,
                }
            )
        context["children_with_roles"] = children_with_roles
        return context


class ChildCreateView(LoginRequiredMixin, CreateView):
    model = Child
    form_class = ChildForm
    template_name = "children/child_form.html"
    success_url = reverse_lazy(URL_CHILD_LIST)

    def form_valid(self, form):
        form.instance.parent = self.request.user
        return super().form_valid(form)


class ChildUpdateView(ChildEditMixin, UpdateView):
    model = Child
    form_class = ChildForm
    template_name = "children/child_form.html"
    success_url = reverse_lazy(URL_CHILD_LIST)

    def get_queryset(self):
        # Allow editing by owner or co-parent
        # Prefetch shares to avoid N+1 queries if form accesses role info
        return (
            Child.objects.filter(
                Q(parent=self.request.user)
                | Q(
                    shares__user=self.request.user,
                    shares__role=ChildShare.Role.CO_PARENT,
                )
            )
            .prefetch_related("shares__user")
            .distinct()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object:
            from notifications.forms import NotificationPreferenceForm
            from notifications.models import NotificationPreference

            pref, _ = NotificationPreference.objects.get_or_create(
                user=self.request.user, child=self.object
            )
            context["notification_preference"] = pref
            context["notification_preference_form"] = context.get(
                "notification_preference_form"
            ) or NotificationPreferenceForm(instance=pref)
            context["notifications_saved"] = (
                self.request.GET.get("notifications_saved") == "1"
            )
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "notification_preference":
            return self._handle_notification_preference(request, *args, **kwargs)
        return super().post(request, *args, **kwargs)

    def _handle_notification_preference(self, request, *args, **kwargs):
        from notifications.forms import NotificationPreferenceForm
        from notifications.models import NotificationPreference

        self.object = self.get_object()
        pref = NotificationPreference.objects.filter(
            user=request.user, child=self.object
        ).first()
        if not pref:
            return redirect(URL_CHILD_LIST)
        form = NotificationPreferenceForm(request.POST, instance=pref)
        if form.is_valid():
            form.save()
            return redirect(
                reverse("children:child_edit", kwargs={"pk": self.object.pk})
                + "?notifications_saved=1"
            )
        context = self.get_context_data(
            notification_preference_form=form,
        )
        return self.render_to_response(context)


class ChildDeleteView(ChildOwnerMixin, DeleteView):
    model = Child
    template_name = "children/child_confirm_delete.html"
    success_url = reverse_lazy(URL_CHILD_LIST)

    def get_queryset(self):
        # Only owners can delete
        return Child.objects.filter(parent=self.request.user)


class ChildDashboardView(ChildAccessMixin, DetailView):
    """Child dashboard: today summary, recent activity, quick actions and nav links.

    Any user with access (owner, co-parent, caregiver) can view. Shows today's
    counts, last N combined activities, and links to add/view tracking, analytics,
    export, catch-up, timeline; sharing link only for owner (NFR-1, FR-1–FR-3).
    """

    model = Child
    template_name = "children/child_dashboard.html"
    context_object_name = "child"

    def get_queryset(self):
        return Child.for_user(self.request.user).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from analytics.utils import get_today_summary

        user_tz = getattr(self.request.user, "timezone", None) or "UTC"
        context["today_summary"] = get_today_summary(
            self.object.id, user_timezone=user_tz
        )
        context["recent_activities"] = self._get_recent_activities()
        context["can_edit"] = self.object.can_edit(self.request.user)
        context["can_manage_sharing"] = self.object.can_manage_sharing(
            self.request.user
        )
        return context

    def _get_recent_activities(self):
        """Merge last feedings, diapers, naps by timestamp; return top N."""
        from analytics.utils import get_merged_activities

        URL_MAP = {
            "feeding": "feedings:feeding_edit",
            "diaper": "diapers:diaper_edit",
            "nap": "naps:nap_edit",
        }
        activities = get_merged_activities(self.object.id, limit_per_type=5)
        for item in activities:
            item["url_name"] = URL_MAP[item["type"]]
            item["url_pk"] = item["obj"]["id"]
        return activities[:DASHBOARD_RECENT_ACTIVITY_LIMIT]

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response


# Timeline: fetch up to this many per type before merge (then paginate)
TIMELINE_FETCH_PER_TYPE = 100
TIMELINE_PAGE_SIZE = 25


class ChildTimelineView(ChildAccessMixin, View):
    """Unified chronological timeline of feedings, diapers, naps (FR-4, FR-5)."""

    template_name = "children/child_timeline.html"

    def get(self, request, pk):
        from analytics.utils import get_merged_activities

        child = self.child
        merged = get_merged_activities(child.id, limit_per_type=TIMELINE_FETCH_PER_TYPE)

        paginator = Paginator(merged, TIMELINE_PAGE_SIZE)
        page_number = request.GET.get("page", 1)
        page = paginator.get_page(page_number)

        return render(
            request,
            self.template_name,
            {
                "child": child,
                "page_obj": page,
                "can_edit": child.can_edit(request.user),
            },
        )


class ChildAnalyticsView(ChildAccessMixin, View):
    """Analytics dashboard: feeding trends, diaper patterns, sleep summary (FR-6, FR-7)."""

    template_name = "children/child_analytics.html"

    def get(self, request, pk):
        from analytics.utils import (
            get_diaper_patterns,
            get_feeding_trends,
            get_sleep_summary,
        )

        child = self.child
        days = int(request.GET.get("days", 30))
        if days not in (7, 14, 30):
            days = 30

        feeding = get_feeding_trends(child.id, days=days)
        diaper = get_diaper_patterns(child.id, days=days)
        sleep = get_sleep_summary(child.id, days=days)

        return render(
            request,
            self.template_name,
            {
                "child": child,
                "days": days,
                "feeding_trends": feeding,
                "diaper_patterns": diaper,
                "sleep_summary": sleep,
            },
        )


class ChildExportView(ChildAccessMixin, View):
    """Export page: format (CSV/PDF) and date range; CSV download, PDF queue + poll (FR-8–FR-10)."""

    template_name = "children/child_export.html"

    def get(self, request, pk):
        return render(request, self.template_name, {"child": self.child})

    def post(self, request, pk):
        from analytics.tasks import generate_pdf_report
        from analytics.utils import (
            get_diaper_patterns,
            get_feeding_trends,
            get_sleep_summary,
        )

        child = self.child
        export_format = request.POST.get("format", "csv").lower()
        try:
            days = int(request.POST.get("days", 30))
        except (TypeError, ValueError):
            days = 30
        if days not in (7, 14, 30):
            days = 30

        if export_format == "csv":
            from analytics.utils import build_analytics_csv

            feeding_data = get_feeding_trends(child.id, days=days)
            diaper_data = get_diaper_patterns(child.id, days=days)
            sleep_data = get_sleep_summary(child.id, days=days)
            content, filename = build_analytics_csv(
                feeding_data, diaper_data, sleep_data, child.name, days
            )
            response = HttpResponse(content, content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        if export_format == "pdf":
            task = generate_pdf_report.delay(child.id, request.user.id, days)
            return redirect(
                "children:child_export_status", pk=child.pk, task_id=task.id
            )

        messages.warning(request, "Please choose CSV or PDF.")
        return redirect("children:child_export", pk=child.pk)


class ChildExportStatusView(ChildAccessMixin, View):
    """Poll PDF export job status; show download link when ready or error (FR-10)."""

    template_name = "children/child_export_status.html"

    def get(self, request, pk, task_id):
        from celery.result import AsyncResult

        child = self.child
        task_result = AsyncResult(task_id)
        status_map = {
            "PENDING": "pending",
            "STARTED": "processing",
            "SUCCESS": "completed",
            "FAILURE": "failed",
        }
        frontend_status = status_map.get(task_result.status, "processing")
        context = {
            "child": child,
            "task_id": task_id,
            "status": frontend_status,
            "poll_interval_sec": 2,
        }
        if task_result.successful():
            result = task_result.result
            context["filename"] = (
                result.get("filename") if isinstance(result, dict) else None
            )
            context["download_url"] = (
                result.get("download_url") if isinstance(result, dict) else None
            )
        elif task_result.failed():
            context["error"] = str(getattr(task_result, "info", "Unknown error"))
        return render(request, self.template_name, context)


def _parse_catchup_date_range(request):
    """Parse start/end from request GET; return (start_date, end_date) with defaults."""
    from datetime import datetime, timedelta

    from django.utils import timezone

    today = timezone.now().date()
    start_s = request.GET.get("start")
    end_s = request.GET.get("end")
    start_date = end_date = None
    if start_s and end_s:
        try:
            start_date = datetime.strptime(start_s, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_s, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pass
    if not start_date or not end_date or start_date > end_date:
        end_date = today
        start_date = today - timedelta(days=6)
    return start_date, end_date


class ChildCatchUpView(ChildAccessMixin, View):
    """Catch-up: time window selector and event timeline (FR-11, FR-12)."""

    template_name = "children/child_catchup.html"

    def get(self, request, pk):
        from analytics.utils import get_merged_activities

        child = self.child
        start_date, end_date = _parse_catchup_date_range(request)
        events = get_merged_activities(
            child.id, start_date=start_date, end_date=end_date
        )

        return render(
            request,
            self.template_name,
            {
                "child": child,
                "events": events,
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "can_edit": child.can_edit(request.user),
            },
        )


class ChildSharingView(ChildOwnerMixin, DetailView):
    """Manage sharing for a child - owner only."""

    model = Child
    template_name = "children/child_sharing.html"
    context_object_name = "child"

    def get_queryset(self):
        return Child.objects.filter(parent=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["shares"] = self.object.shares.select_related("user")
        context["invites"] = self.object.invites.all()
        context["roles"] = ChildShare.Role.choices
        return context


class CreateInviteView(ChildOwnerMixin, View):
    """Create a new sharing invite - owner only."""

    def post(self, request, pk):
        role = request.POST.get("role", ChildShare.Role.CAREGIVER)

        # Validate role
        if role not in [ChildShare.Role.CO_PARENT, ChildShare.Role.CAREGIVER]:
            role = ChildShare.Role.CAREGIVER

        ShareInvite.objects.create(
            child=self.child,
            role=role,
            created_by=request.user,
        )

        messages.success(request, f"Invite link created for {self.child.name}")
        return redirect(URL_CHILD_SHARING, pk=pk)


class RevokeAccessView(ChildOwnerMixin, View):
    """Revoke a user's access to child - owner only."""

    def post(self, request, pk, share_pk):
        share = get_object_or_404(ChildShare, pk=share_pk, child=self.child)

        user_email = share.user.email
        share.delete()

        messages.success(request, f"Access revoked for {user_email}")
        return redirect(URL_CHILD_SHARING, pk=pk)


class ToggleInviteView(ChildOwnerMixin, View):
    """Toggle invite active status - owner only."""

    def post(self, request, pk, invite_pk):
        invite = get_object_or_404(ShareInvite, pk=invite_pk, child=self.child)

        invite.is_active = not invite.is_active
        invite.save()

        status = "activated" if invite.is_active else "deactivated"
        messages.success(request, f"Invite link {status}")
        return redirect(URL_CHILD_SHARING, pk=pk)


class DeleteInviteView(ChildOwnerMixin, View):
    """Delete an invite link - owner only."""

    def post(self, request, pk, invite_pk):
        invite = get_object_or_404(ShareInvite, pk=invite_pk, child=self.child)

        invite.delete()

        messages.success(request, "Invite link deleted")
        return redirect(URL_CHILD_SHARING, pk=pk)


class AcceptInviteView(LoginRequiredMixin, View):
    """Accept an invite link - any authenticated user."""

    def get(self, request, token):
        invite = get_object_or_404(ShareInvite, token=token, is_active=True)

        # Check if user is already the owner
        if invite.child.parent == request.user:
            messages.warning(request, "You are already the owner of this child")
            return redirect(URL_CHILD_LIST)

        # Handle potential race condition with get_or_create
        with transaction.atomic():
            try:
                share, created = ChildShare.objects.get_or_create(
                    child=invite.child,
                    user=request.user,
                    defaults={
                        "role": invite.role,
                        "created_by": invite.created_by,
                    },
                )
            except IntegrityError:
                # Race condition: another request created the share concurrently
                # Fetch the existing share
                share = ChildShare.objects.get(child=invite.child, user=request.user)
                created = False

        if created:
            role_display = dict(ChildShare.Role.choices).get(invite.role, invite.role)
            messages.success(
                request,
                f"You now have {role_display} access to {invite.child.name}",
            )
        else:
            messages.info(
                request,
                f"You already have {share.get_role_display()} "
                f"access to {invite.child.name}",
            )
        return redirect(URL_CHILD_LIST)
