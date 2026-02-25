import csv
from io import StringIO

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

        context["today_summary"] = get_today_summary(self.object.id)
        context["recent_activities"] = self._get_recent_activities()
        context["can_edit"] = self.object.can_edit(self.request.user)
        context["can_manage_sharing"] = self.object.can_manage_sharing(
            self.request.user
        )
        return context

    def _get_recent_activities(self):
        """Merge last feedings, diapers, naps by timestamp; return top N."""
        from diapers.models import DiaperChange
        from feedings.models import Feeding
        from naps.models import Nap

        child_id = self.object.id
        n_per_type = 5
        feedings = list(
            Feeding.objects.filter(child_id=child_id)
            .order_by("-fed_at")[:n_per_type]
            .values("id", "fed_at", "feeding_type", "amount_oz", "duration_minutes")
        )
        diapers = list(
            DiaperChange.objects.filter(child_id=child_id)
            .order_by("-changed_at")[:n_per_type]
            .values("id", "changed_at", "change_type")
        )
        naps = list(
            Nap.objects.filter(child_id=child_id)
            .order_by("-napped_at")[:n_per_type]
            .values("id", "napped_at", "ended_at")
        )
        merged = []
        for f in feedings:
            merged.append(
                {
                    "type": "feeding",
                    "at": f["fed_at"],
                    "obj": f,
                    "url_name": "feedings:feeding_edit",
                    "url_pk": f["id"],
                }
            )
        for d in diapers:
            merged.append(
                {
                    "type": "diaper",
                    "at": d["changed_at"],
                    "obj": d,
                    "url_name": "diapers:diaper_edit",
                    "url_pk": d["id"],
                }
            )
        for n in naps:
            merged.append(
                {
                    "type": "nap",
                    "at": n["napped_at"],
                    "obj": n,
                    "url_name": "naps:nap_edit",
                    "url_pk": n["id"],
                }
            )
        merged.sort(key=lambda x: x["at"], reverse=True)
        return merged[:DASHBOARD_RECENT_ACTIVITY_LIMIT]

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
        from diapers.models import DiaperChange
        from feedings.models import Feeding
        from naps.models import Nap

        child = self.child
        feedings = list(
            Feeding.objects.filter(child_id=child.id)
            .order_by("-fed_at")[:TIMELINE_FETCH_PER_TYPE]
            .values("id", "fed_at", "feeding_type", "amount_oz", "duration_minutes")
        )
        diapers = list(
            DiaperChange.objects.filter(child_id=child.id)
            .order_by("-changed_at")[:TIMELINE_FETCH_PER_TYPE]
            .values("id", "changed_at", "change_type")
        )
        naps = list(
            Nap.objects.filter(child_id=child.id)
            .order_by("-napped_at")[:TIMELINE_FETCH_PER_TYPE]
            .values("id", "napped_at", "ended_at")
        )
        merged = []
        for f in feedings:
            merged.append({"type": "feeding", "at": f["fed_at"], "obj": f})
        for d in diapers:
            merged.append({"type": "diaper", "at": d["changed_at"], "obj": d})
        for n in naps:
            merged.append({"type": "nap", "at": n["napped_at"], "obj": n})
        merged.sort(key=lambda x: x["at"], reverse=True)

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
            feeding_data = get_feeding_trends(child.id, days=days)
            diaper_data = get_diaper_patterns(child.id, days=days)
            sleep_data = get_sleep_summary(child.id, days=days)

            csv_buffer = StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(
                [
                    "Date",
                    "Feedings (count)",
                    "Feedings (avg duration min)",
                    "Feedings (total oz)",
                    "Diaper Changes (count)",
                    "Diaper Changes (wet)",
                    "Diaper Changes (dirty)",
                    "Diaper Changes (both)",
                    "Naps (count)",
                    "Naps (avg duration min)",
                    "Naps (total minutes)",
                ]
            )
            feeding_by_date = {d["date"]: d for d in feeding_data.get("daily_data", [])}
            diaper_by_date = {d["date"]: d for d in diaper_data.get("daily_data", [])}
            sleep_by_date = {d["date"]: d for d in sleep_data.get("daily_data", [])}
            all_dates = sorted(
                set(feeding_by_date.keys())
                | set(diaper_by_date.keys())
                | set(sleep_by_date.keys())
            )
            for d in all_dates:
                f = feeding_by_date.get(d, {})
                di = diaper_by_date.get(d, {})
                s = sleep_by_date.get(d, {})
                writer.writerow(
                    [
                        d,
                        f.get("count", 0),
                        f.get("average_duration") or "",
                        f.get("total_oz") or "",
                        di.get("count", 0),
                        di.get("wet_count", 0),
                        di.get("dirty_count", 0),
                        di.get("both_count", 0),
                        s.get("count", 0),
                        s.get("average_duration") or "",
                        s.get("total_minutes") or "",
                    ]
                )
            response = HttpResponse(csv_buffer.getvalue(), content_type="text/csv")
            filename = f"analytics-{child.name.replace(' ', '_')}-{days}days.csv"
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


class ChildCatchUpView(ChildAccessMixin, View):
    """Catch-up: time window selector and event timeline (FR-11, FR-12)."""

    template_name = "children/child_catchup.html"

    def get(self, request, pk):
        from datetime import timedelta

        from django.utils import timezone

        from diapers.models import DiaperChange
        from feedings.models import Feeding
        from naps.models import Nap

        child = self.child
        today = timezone.now().date()
        start_s = request.GET.get("start")
        end_s = request.GET.get("end")
        events = []
        start_date = end_date = None

        if start_s and end_s:
            try:
                from datetime import datetime

                start_date = datetime.strptime(start_s, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_s, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass
        if not start_date or not end_date or start_date > end_date:
            end_date = today
            start_date = today - timedelta(days=6)

        feedings = list(
            Feeding.objects.filter(
                child_id=child.id,
                fed_at__date__gte=start_date,
                fed_at__date__lte=end_date,
            )
            .order_by("-fed_at")
            .values("id", "fed_at", "feeding_type", "amount_oz", "duration_minutes")
        )
        diapers = list(
            DiaperChange.objects.filter(
                child_id=child.id,
                changed_at__date__gte=start_date,
                changed_at__date__lte=end_date,
            )
            .order_by("-changed_at")
            .values("id", "changed_at", "change_type")
        )
        naps = list(
            Nap.objects.filter(
                child_id=child.id,
                napped_at__date__gte=start_date,
                napped_at__date__lte=end_date,
            )
            .order_by("-napped_at")
            .values("id", "napped_at", "ended_at")
        )
        for f in feedings:
            events.append({"type": "feeding", "at": f["fed_at"], "obj": f})
        for d in diapers:
            events.append({"type": "diaper", "at": d["changed_at"], "obj": d})
        for n in naps:
            events.append({"type": "nap", "at": n["napped_at"], "obj": n})
        events.sort(key=lambda x: x["at"], reverse=True)

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
