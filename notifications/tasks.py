"""Celery tasks for notification creation and cleanup."""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task(bind=True, time_limit=60)
def create_notifications_for_activity(self, child_id, actor_id, event_type):
    """Create notifications for all users with access to a child.

    Excludes the actor (person who logged the activity).
    Respects per-child notification preferences and quiet hours.
    """
    from accounts.models import CustomUser
    from children.models import Child, ChildShare

    from .models import Notification, NotificationPreference, QuietHours

    try:
        child = Child.objects.select_related("parent").get(id=child_id)
    except Child.DoesNotExist:
        return "Child not found"

    try:
        actor = CustomUser.objects.get(id=actor_id)
    except CustomUser.DoesNotExist:
        return "Actor not found"

    # Build recipient set: owner + all shared users, minus actor
    recipient_ids = set()
    recipient_ids.add(child.parent_id)
    shared_user_ids = ChildShare.objects.filter(child=child).values_list(
        "user_id", flat=True
    )
    recipient_ids.update(shared_user_ids)
    recipient_ids.discard(actor_id)

    if not recipient_ids:
        return "No recipients"

    # Map event_type to preference field
    pref_field_map = {
        "feeding": "notify_feedings",
        "diaper": "notify_diapers",
        "nap": "notify_naps",
    }
    pref_field = pref_field_map.get(event_type)
    if not pref_field:
        return f"Unknown event type: {event_type}"

    # Fetch preferences for all recipients at once
    prefs = {
        p.user_id: p
        for p in NotificationPreference.objects.filter(
            user_id__in=recipient_ids, child=child
        )
    }

    # Fetch quiet hours for all recipients at once
    quiet_hours = {
        qh.user_id: qh
        for qh in QuietHours.objects.select_related("user").filter(
            user_id__in=recipient_ids, enabled=True
        )
    }

    # Build message
    event_labels = {
        "feeding": "a feeding",
        "diaper": "a diaper change",
        "nap": "a nap",
    }
    actor_name = actor.first_name or actor.email.split("@")[0]
    message = f"{actor_name} logged {event_labels[event_type]} for {child.name}"

    notifications = []
    for recipient_id in recipient_ids:
        # Check per-child preference (default: enabled if no pref row)
        pref = prefs.get(recipient_id)
        if pref and not getattr(pref, pref_field):
            continue

        # Check quiet hours
        qh = quiet_hours.get(recipient_id)
        if qh and qh.is_quiet_now():
            continue

        notifications.append(
            Notification(
                recipient_id=recipient_id,
                actor=actor,
                child=child,
                event_type=event_type,
                message=message,
            )
        )

    if notifications:
        Notification.objects.bulk_create(notifications)

    return f"Created {len(notifications)} notifications"


@shared_task(bind=True, time_limit=120)
def cleanup_old_notifications(self):
    """Delete notifications older than 30 days. Runs daily via Celery Beat."""
    from .models import Notification

    cutoff = timezone.now() - timedelta(days=30)
    deleted_count, _ = Notification.objects.filter(created_at__lt=cutoff).delete()
    return f"Deleted {deleted_count} old notifications"
