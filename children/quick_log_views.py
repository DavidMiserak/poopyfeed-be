"""One-tap quick-log views: create a tracking record with defaults and redirect to dashboard.

POST-only Django views (no REST API). Used by the child dashboard template with
CSRF forms. Send tracking_created signal for in-app notifications; cache
invalidation runs via post_save in children.apps.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View

from diapers.models import DiaperChange
from feedings.constants import MAX_BOTTLE_OZ, MIN_BOTTLE_OZ
from feedings.models import Feeding
from naps.models import Nap

from .cache_utils import invalidate_child_activities_cache
from .mixins import ChildAccessMixin

VALID_DIAPER_CHANGE_TYPES = ("wet", "dirty", "both")
VALID_BOTTLE_PRESETS = ("low", "mid", "high")
DEFAULT_BOTTLE_OZ = Decimal("4")


def _get_bottle_amount_for_preset(child, preset: str) -> Decimal:
    """Calculate bottle amount for low/mid/high presets using child custom values when present.

    Fallback rules (aligned with frontend semantics):
    - mid: use custom_bottle_mid_oz if valid, else DEFAULT_BOTTLE_OZ
    - low: use custom_bottle_low_oz if valid, else mid - 1
    - high: use custom_bottle_high_oz if valid, else mid + 1

    Final value is clamped to MIN_BOTTLE_OZ/MAX_BOTTLE_OZ.
    """

    # Resolve a safe mid baseline first
    mid_custom = getattr(child, "custom_bottle_mid_oz", None)
    if mid_custom is not None and MIN_BOTTLE_OZ <= mid_custom <= MAX_BOTTLE_OZ:
        mid_base = mid_custom
    else:
        mid_base = DEFAULT_BOTTLE_OZ

    if preset == "mid":
        amount = mid_base
    elif preset == "low":
        low_custom = getattr(child, "custom_bottle_low_oz", None)
        if low_custom is not None and MIN_BOTTLE_OZ <= low_custom <= MAX_BOTTLE_OZ:
            amount = low_custom
        else:
            amount = mid_base - Decimal("1")
    elif preset == "high":
        high_custom = getattr(child, "custom_bottle_high_oz", None)
        if high_custom is not None and MIN_BOTTLE_OZ <= high_custom <= MAX_BOTTLE_OZ:
            amount = high_custom
        else:
            amount = mid_base + Decimal("1")
    else:
        # Should not happen if caller validates preset; default to mid
        amount = mid_base

    # Clamp to allowed range
    if amount < MIN_BOTTLE_OZ:
        return MIN_BOTTLE_OZ
    if amount > MAX_BOTTLE_OZ:
        return MAX_BOTTLE_OZ
    return amount


class QuickLogFeedingView(ChildAccessMixin, View):
    """POST-only: create a bottle feeding for low/mid/high preset, then redirect."""

    def get(self, request, pk, preset):
        return redirect(reverse("children:child_dashboard", kwargs={"pk": pk}))

    def post(self, request, pk, preset):
        if preset not in VALID_BOTTLE_PRESETS:
            messages.error(request, "Invalid bottle preset.")
            return redirect(reverse("children:child_dashboard", kwargs={"pk": pk}))

        child = self.child
        amount = _get_bottle_amount_for_preset(child, preset)

        fed_at = timezone.now()
        feeding = Feeding.objects.create(
            child=child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            amount_oz=amount,
            fed_at=fed_at,
        )
        invalidate_child_activities_cache(child.id)
        from notifications.signals import tracking_created

        tracking_created.send(
            sender=Feeding,
            instance=feeding,
            actor_id=request.user.id,
            event_type="feeding",
        )
        messages.success(request, "Feeding logged.")
        return redirect(reverse("children:child_dashboard", kwargs={"pk": child.pk}))


class QuickLogDiaperView(ChildAccessMixin, View):
    """POST-only: create a diaper change with change_type from URL, redirect to dashboard."""

    def get(self, request, pk, change_type):
        return redirect(reverse("children:child_dashboard", kwargs={"pk": pk}))

    def post(self, request, pk, change_type):
        if change_type not in VALID_DIAPER_CHANGE_TYPES:
            messages.error(request, "Invalid diaper change type.")
            return redirect(reverse("children:child_dashboard", kwargs={"pk": pk}))

        child = self.child
        changed_at = timezone.now()
        diaper = DiaperChange.objects.create(
            child=child,
            change_type=change_type,
            changed_at=changed_at,
        )
        invalidate_child_activities_cache(child.id)
        from notifications.signals import tracking_created

        tracking_created.send(
            sender=DiaperChange,
            instance=diaper,
            actor_id=request.user.id,
            event_type="diaper",
        )
        messages.success(request, "Diaper change logged.")
        return redirect(reverse("children:child_dashboard", kwargs={"pk": child.pk}))


class QuickLogNapView(ChildAccessMixin, View):
    """POST-only: create a nap start (napped_at=now, no end), redirect to dashboard."""

    def get(self, request, pk):
        return redirect(reverse("children:child_dashboard", kwargs={"pk": pk}))

    def post(self, request, pk):
        child = self.child
        napped_at = timezone.now()
        nap = Nap.objects.create(
            child=child,
            napped_at=napped_at,
            ended_at=None,
        )
        invalidate_child_activities_cache(child.id)
        from notifications.signals import tracking_created

        tracking_created.send(
            sender=Nap,
            instance=nap,
            actor_id=request.user.id,
            event_type="nap",
        )
        messages.success(request, "Nap logged.")
        return redirect(reverse("children:child_dashboard", kwargs={"pk": child.pk}))
