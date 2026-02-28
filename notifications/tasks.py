"""Celery tasks for notification creation and cleanup."""

from datetime import timedelta

from celery import shared_task
from django.db import IntegrityError
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
    from .models import FeedingReminderLog, Notification

    cutoff = timezone.now() - timedelta(days=30)
    deleted_count, _ = Notification.objects.filter(created_at__lt=cutoff).delete()

    # Also cleanup old FeedingReminderLog entries
    log_cutoff = timezone.now() - timedelta(days=7)
    log_deleted_count, _ = FeedingReminderLog.objects.filter(
        sent_at__lt=log_cutoff
    ).delete()

    return (
        f"Deleted {deleted_count} notifications and {log_deleted_count} reminder logs"
    )


def _get_last_fed_at(child):
    """Return the fed_at of the last feeding for the child, or None."""
    from feedings.models import Feeding

    last = (
        Feeding.objects.filter(child=child).order_by("-fed_at").values("fed_at").first()
    )
    return last["fed_at"] if last else None


def _get_reminder_recipient_ids(child):
    """Return set of user ids who should receive reminders (owner + shared users)."""
    from children.models import ChildShare

    ids = {child.parent_id}
    ids.update(ChildShare.objects.filter(child=child).values_list("user_id", flat=True))
    return ids


def _build_reminder_notifications(child, recipient_ids, prefs, message):
    """Build list of Notification instances for recipients who have notify_feedings."""
    from .models import Notification

    notifications = []
    for recipient_id in recipient_ids:
        pref = prefs.get(recipient_id)
        if pref and not pref.notify_feedings:
            continue
        notifications.append(
            Notification(
                recipient_id=recipient_id,
                actor=None,
                child=child,
                event_type=Notification.EventType.FEEDING_REMINDER,
                message=message,
            )
        )
    return notifications


def _log_reminder_sent(child, last_fed_at, reminder_number):
    """Record reminder in FeedingReminderLog for idempotency. Ignores IntegrityError."""
    from .models import FeedingReminderLog

    try:
        FeedingReminderLog.objects.create(
            child=child,
            window_start=last_fed_at,
            reminder_number=reminder_number,
        )
    except IntegrityError:
        pass


def _maybe_send_reminder_batch(
    child,
    last_fed_at,
    recipient_ids,
    prefs,
    interval_hours,
    reminder_number,
    time_since_feeding,
    message,
):
    """Send one batch (initial or repeat) if thresholds and idempotency allow. Returns count sent."""
    from .models import FeedingReminderLog, Notification

    if reminder_number == 1:
        threshold = timedelta(hours=interval_hours)
    else:
        threshold = timedelta(hours=interval_hours * 1.5)
    if time_since_feeding < threshold:
        return 0
    if FeedingReminderLog.objects.filter(
        child=child, window_start=last_fed_at, reminder_number=reminder_number
    ).exists():
        return 0
    notifications = _build_reminder_notifications(child, recipient_ids, prefs, message)
    if notifications:
        Notification.objects.bulk_create(notifications)
    _log_reminder_sent(child, last_fed_at, reminder_number)
    return len(notifications)


def _process_child_reminders(child):
    """Process feeding reminders for one child. Returns number of notifications created."""
    from .models import NotificationPreference

    last_fed_at = _get_last_fed_at(child)
    if not last_fed_at:
        return 0
    time_since = timezone.now() - last_fed_at
    recipient_ids = _get_reminder_recipient_ids(child)
    prefs = {
        p.user_id: p
        for p in NotificationPreference.objects.filter(
            user_id__in=recipient_ids, child=child
        )
    }
    interval_hours = child.feeding_reminder_interval
    count = 0
    count += _maybe_send_reminder_batch(
        child,
        last_fed_at,
        recipient_ids,
        prefs,
        interval_hours,
        1,
        time_since,
        f"Baby hasn't been fed for {interval_hours} hours",
    )
    count += _maybe_send_reminder_batch(
        child,
        last_fed_at,
        recipient_ids,
        prefs,
        interval_hours,
        2,
        time_since,
        f"Baby still hasn't been fed (now {int(time_since.total_seconds() / 3600)} hours)",
    )
    return count


@shared_task(bind=True, time_limit=60)
def check_feeding_reminders(self):
    """Check for children that need feeding reminders.

    Runs every 30 minutes via Celery Beat. For each child with a configured
    feeding_reminder_interval and at least one feeding logged:
    1. Fires initial reminder if time since last feeding >= interval
    2. Fires repeat reminder if time since last feeding >= interval * 1.5

    Uses FeedingReminderLog for idempotency to prevent duplicate sends.
    Respects per-child notify_feedings preference but bypasses quiet hours (safety-critical).
    """
    from children.models import Child

    children = (
        Child.objects.filter(feeding_reminder_interval__isnull=False)
        .select_related("parent")
        .prefetch_related("shares__user")
    )
    reminder_count = sum(_process_child_reminders(child) for child in children)
    return f"Created {reminder_count} feeding reminder notifications"
