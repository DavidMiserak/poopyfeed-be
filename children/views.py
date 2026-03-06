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

from analytics.fuss_bus import (
    COLIC_SECTION,
    FUSS_BUS_GLOSSARY,
    SELF_CARE_ITEMS,
    SOOTHING_TOOLKIT,
    WHEN_TO_CALL_DOCTOR_BULLETS,
    AutoCheckState,
    build_checklist_items,
    get_auto_check_state,
    get_child_age_months,
    get_developmental_contexts,
    get_lullaby_songs,
    prioritize_suggestions,
)
from analytics.utils import compute_pattern_alerts, get_child_timeline_events

from .forms import ChildForm, FussBusStep1Form, FussBusStep2Form
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
            .select_related("parent")
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
            .select_related("parent")
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
    object: Child  # type narrowing for mixin conflict in stubs
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
        # Pattern alerts: feeding/nap overdue warnings from last 7 days
        from analytics.utils import compute_pattern_alerts

        alerts_data = compute_pattern_alerts(self.object.id)
        pattern_alerts = []
        for key in ("feeding", "nap"):
            part = alerts_data.get(key, {})
            if part.get("alert") and part.get("message"):
                pattern_alerts.append({"key": key, "message": part["message"]})
        context["pattern_alerts"] = pattern_alerts
        # Quick-log bottle button labels: oz amounts that will be submitted
        from .quick_log_views import _get_bottle_amount_for_preset

        context["quick_log_bottle_low_oz"] = _get_bottle_amount_for_preset(
            self.object, "low"
        )
        context["quick_log_bottle_mid_oz"] = _get_bottle_amount_for_preset(
            self.object, "mid"
        )
        context["quick_log_bottle_high_oz"] = _get_bottle_amount_for_preset(
            self.object, "high"
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


class ChildAdvancedView(ChildAccessMixin, View):
    """Advanced tools hub: links to pediatrician summary, analytics, export, timeline, catch-up, lists, sharing."""

    template_name = "children/child_advanced.html"

    def get(self, request, pk):
        return render(
            request,
            self.template_name,
            {
                "child": self.child,
                "can_manage_sharing": self.child.can_manage_sharing(request.user),
            },
        )


class ChildFussBusView(ChildAccessMixin, View):
    """The Fuss Bus: guided 3-step troubleshooting wizard in Django templates."""

    template_name = "children/child_fuss_bus.html"

    SESSION_KEY = "fuss_bus_state"

    def _get_state(self, request) -> dict:
        """Return per-child wizard state from session with sensible defaults."""
        session_state = request.session.get(self.SESSION_KEY, {})
        child_key = str(self.child.id)
        child_state = session_state.get(
            child_key,
            {
                "step": 1,
                "symptom": "general_fussiness",
                "checked": [],
            },
        )
        child_state.setdefault("step", 1)
        child_state.setdefault("symptom", "general_fussiness")
        child_state.setdefault("checked", [])
        return child_state

    def _save_state(self, request, state: dict) -> None:
        session_state = request.session.get(self.SESSION_KEY, {})
        session_state[str(self.child.id)] = {
            "step": state.get("step", 1),
            "symptom": state.get("symptom") or "general_fussiness",
            "checked": list(state.get("checked", [])),
        }
        request.session[self.SESSION_KEY] = session_state
        request.session.modified = True

    def _build_auto_state_and_checklist(
        self, *, symptom: str, checked_ids: set[str]
    ) -> tuple[AutoCheckState, list]:
        """Shared helper to compute auto-check state and checklist items."""
        child = self.child
        pattern_alerts = compute_pattern_alerts(child.id)
        timeline_events = get_child_timeline_events(child.id)
        age_months = get_child_age_months(child.date_of_birth)
        auto_state = get_auto_check_state(
            pattern_alerts=pattern_alerts,
            timeline_events=timeline_events,
            child_age_months=age_months,
        )
        checklist_items = build_checklist_items(
            symptom_id=symptom,  # type: ignore[arg-type]
            child_age_months=age_months,
            auto_check_state=auto_state,
        )
        return auto_state, checklist_items

    def _get_fuss_bus_step_state(self, request) -> dict:
        """Resolve and persist step from GET; return current state."""
        if not request.GET:
            state = {
                "step": 1,
                "symptom": "general_fussiness",
                "checked": [],
            }
            self._save_state(request, state)
        else:
            state = self._get_state(request)
        try:
            raw_step = request.GET.get("step") or state.get("step", 1)
            step_param = int(raw_step)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            step_param = 1
        state["step"] = max(1, min(3, step_param))
        self._save_state(request, state)
        return state

    def _build_soothing_toolkit_for_template(self) -> list[dict]:
        """Build list of soothing categories with glossary metadata for template."""
        result: list[dict] = []
        for cat in SOOTHING_TOOLKIT:
            items_with_meta = []
            for label in cat.items:
                entry = FUSS_BUS_GLOSSARY.get(label)
                items_with_meta.append(
                    {
                        "label": label,
                        "glossary_title": entry.title if entry else "",
                        "glossary_body": entry.body if entry else "",
                    }
                )
            result.append({"title": cat.title, "items": items_with_meta})
        return result

    def get(self, request, pk):
        child = self.child
        state = self._get_fuss_bus_step_state(request)
        step = int(state["step"])
        symptom = state.get("symptom") or "general_fussiness"
        checked_ids = set(state.get("checked", []))

        age_months = get_child_age_months(child.date_of_birth)
        auto_state, checklist_items = self._build_auto_state_and_checklist(
            symptom=symptom, checked_ids=checked_ids
        )

        suggestions = []
        developmental_contexts: list[str] = []
        show_colic = False
        if step == 3 and symptom:
            suggestions = prioritize_suggestions(
                checklist_items=checklist_items,
                checked_manual_ids=checked_ids,
                symptom_id=symptom,
                auto_check_state=auto_state,
            )
            developmental_contexts = get_developmental_contexts(age_months)
            show_colic = age_months <= 4 and symptom == "crying"

        context = {
            "child": child,
            "step": step,
            "symptom": symptom,
            "checked_ids": checked_ids,
            "auto_state": auto_state,
            "checklist_items": checklist_items,
            "suggestions": suggestions,
            "developmental_contexts": developmental_contexts,
            "show_colic": show_colic,
            "when_to_call_doctor": WHEN_TO_CALL_DOCTOR_BULLETS,
            "self_care_items": SELF_CARE_ITEMS,
            "soothing_toolkit": self._build_soothing_toolkit_for_template(),
            "lullaby_songs": get_lullaby_songs(),
            "colic_section": COLIC_SECTION,
            "age_months": age_months,
        }
        return render(request, self.template_name, context)

    def _parse_fuss_bus_step(self, request, state: dict) -> int:
        """Parse step from POST or fall back to state; return 1 on invalid."""
        try:
            return int(request.POST.get("step") or state.get("step", 1))
        except ValueError:
            return 1

    def _process_fuss_bus_post_steps(self, state: dict, request, action: str) -> None:
        """Update state from POST according to current step and action."""
        current_step = state["step"]
        symptom = state.get("symptom") or "general_fussiness"
        if current_step == 1:
            step1_form = FussBusStep1Form(request.POST)
            if step1_form.is_valid():
                state["symptom"] = step1_form.cleaned_data["symptom"]
                state["step"] = 2 if action == "next" else 1
        elif current_step == 2:
            auto_state, checklist_items = self._build_auto_state_and_checklist(
                symptom=symptom, checked_ids=set(state.get("checked", []))
            )
            manual_ids = [item.id for item in checklist_items if item.kind == "manual"]
            step2_form = FussBusStep2Form(request.POST, manual_ids=manual_ids)
            if step2_form.is_valid():
                state["checked"] = step2_form.cleaned_data.get("checked", [])
                state["step"] = 3 if action == "next" else 1
        else:
            state["step"] = 2 if action == "back" else 3

    def post(self, request, pk):
        """Advance/back/reset wizard; state stored in session."""
        state = self._get_state(request)
        action = request.POST.get("action") or "next"
        state["step"] = self._parse_fuss_bus_step(request, state)

        if action == "start_over":
            self._save_state(
                request,
                {"step": 1, "symptom": "general_fussiness", "checked": []},
            )
            return redirect("children:child_fuss_bus", pk=pk)

        self._process_fuss_bus_post_steps(state, request, action)
        self._save_state(request, state)
        return redirect(
            reverse("children:child_fuss_bus", kwargs={"pk": pk})
            + f"?step={state.get('step', 1)}"
        )


PEDIATRICIAN_SUMMARY_DAYS = 7


class ChildPediatricianSummaryView(ChildAccessMixin, View):
    """Printable 7-day summary for pediatrician visits. Uses get_weekly_summary."""

    template_name = "children/child_pediatrician_summary.html"

    def get(self, request, pk):
        from analytics.utils import get_weekly_summary

        child = self.child
        summary = get_weekly_summary(child.id)
        # Per-day averages for doctor-friendly display
        days = PEDIATRICIAN_SUMMARY_DAYS
        feedings = summary.get("feedings", {})
        diapers = summary.get("diapers", {})
        sleep = summary.get("sleep", {})
        context = {
            "child": child,
            "summary": summary,
            "feedings_per_day": round(feedings.get("count", 0) / days, 1),
            "oz_per_day": round(feedings.get("total_oz", 0) / days, 1),
            "diapers_per_day": round(diapers.get("count", 0) / days, 1),
            "naps_per_day": round(sleep.get("naps", 0) / days, 1),
            "sleep_minutes_per_day": int(
                round(sleep.get("total_minutes", 0) / days, 0)
            ),
        }
        return render(request, self.template_name, context)


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
