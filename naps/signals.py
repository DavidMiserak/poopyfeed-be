"""Signals to auto-end open naps when a new activity is recorded.

When a feeding, diaper change, or new nap is created, any open naps
(ended_at is NULL) for the same child that started before the activity
are automatically ended with the activity's timestamp.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from diapers.models import DiaperChange
from feedings.models import Feeding

from .models import Nap


def _end_open_naps(child_id, activity_timestamp, exclude_pk=None):
    """End all open naps for a child that started before the given timestamp.

    Args:
        child_id: The child whose open naps should be ended.
        activity_timestamp: The timestamp to set as ended_at.
        exclude_pk: Optional nap PK to exclude (when a new nap triggers this).
    """
    qs = Nap.objects.filter(
        child_id=child_id,
        ended_at__isnull=True,
        napped_at__lt=activity_timestamp,
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    qs.update(ended_at=activity_timestamp, updated_at=timezone.now())


@receiver(post_save, sender=Feeding)
def end_naps_on_feeding(sender, instance, created, **kwargs):
    """End open naps when a new feeding is created."""
    if created:
        _end_open_naps(instance.child_id, instance.fed_at)


@receiver(post_save, sender=DiaperChange)
def end_naps_on_diaper_change(sender, instance, created, **kwargs):
    """End open naps when a new diaper change is created."""
    if created:
        _end_open_naps(instance.child_id, instance.changed_at)


@receiver(post_save, sender=Nap)
def end_naps_on_new_nap(sender, instance, created, **kwargs):
    """End open naps when a new nap is created (excluding itself)."""
    if created:
        _end_open_naps(instance.child_id, instance.napped_at, exclude_pk=instance.pk)
