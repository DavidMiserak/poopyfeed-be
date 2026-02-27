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
    from django.db.models import Q

    from accounts.models import CustomUser
    from children.models import Child, ChildShare
    from feedings.models import Feeding

    from .models import FeedingReminderLog, Notification, NotificationPreference

    # Get all children with reminder intervals configured
    children = (
        Child.objects.filter(feeding_reminder_interval__isnull=False)
        .select_related("parent")
        .prefetch_related("shares__user")
    )

    reminder_count = 0

    for child in children:
        # Get the last feeding for this child
        last_feeding = (
            Feeding.objects.filter(child=child)
            .order_by("-fed_at")
            .values("fed_at")
            .first()
        )

        # Skip if no feedings on record (FR-REM-006)
        if not last_feeding:
            continue

        last_fed_at = last_feeding["fed_at"]
        time_since_feeding = timezone.now() - last_fed_at

        # Determine which reminders should be sent
        interval_hours = child.feeding_reminder_interval
        initial_threshold = timedelta(hours=interval_hours)
        repeat_threshold = timedelta(hours=interval_hours * 1.5)

        # Check if initial reminder should be sent (FR-REM-004)
        initial_needed = time_since_feeding >= initial_threshold
        initial_sent = FeedingReminderLog.objects.filter(
            child=child, window_start=last_fed_at, reminder_number=1
        ).exists()

        # Check if repeat reminder should be sent (FR-REM-005)
        repeat_needed = time_since_feeding >= repeat_threshold
        repeat_sent = FeedingReminderLog.objects.filter(
            child=child, window_start=last_fed_at, reminder_number=2
        ).exists()

        # Build recipient list: owner + all shared users
        recipient_ids = set()
        recipient_ids.add(child.parent_id)
        shared_user_ids = ChildShare.objects.filter(child=child).values_list(
            "user_id", flat=True
        )
        recipient_ids.update(shared_user_ids)

        # Fetch preferences for all recipients
        prefs = {
            p.user_id: p
            for p in NotificationPreference.objects.filter(
                user_id__in=recipient_ids, child=child
            )
        }

        notifications = []

        # Send initial reminder if needed and not already sent (FR-REM-004)
        if initial_needed and not initial_sent:
            for recipient_id in recipient_ids:
                # Respect notify_feedings preference (FR-REM-009)
                pref = prefs.get(recipient_id)
                if pref and not pref.notify_feedings:
                    continue

                notifications.append(
                    Notification(
                        recipient_id=recipient_id,
                        actor=None,  # System-generated, no actor
                        child=child,
                        event_type=Notification.EventType.FEEDING_REMINDER,
                        message=f"Baby hasn't been fed for {interval_hours} hours",
                    )
                )

            if notifications:
                Notification.objects.bulk_create(notifications)
                reminder_count += len(notifications)

            # Log that we sent the initial reminder (for idempotency)
            try:
                FeedingReminderLog.objects.create(
                    child=child, window_start=last_fed_at, reminder_number=1
                )
            except IntegrityError:
                # Silently catch unique constraint violations (race condition)
                pass

        # Send repeat reminder if needed and not already sent (FR-REM-005)
        if repeat_needed and not repeat_sent:
            notifications = []
            for recipient_id in recipient_ids:
                # Respect notify_feedings preference (FR-REM-009)
                pref = prefs.get(recipient_id)
                if pref and not pref.notify_feedings:
                    continue

                notifications.append(
                    Notification(
                        recipient_id=recipient_id,
                        actor=None,
                        child=child,
                        event_type=Notification.EventType.FEEDING_REMINDER,
                        message=f"Baby still hasn't been fed (now {int(time_since_feeding.total_seconds() / 3600)} hours)",
                    )
                )

            if notifications:
                Notification.objects.bulk_create(notifications)
                reminder_count += len(notifications)

            # Log that we sent the repeat reminder
            try:
                FeedingReminderLog.objects.create(
                    child=child, window_start=last_fed_at, reminder_number=2
                )
            except IntegrityError:
                # Silently catch unique constraint violations
                pass

    return f"Created {reminder_count} feeding reminder notifications"
