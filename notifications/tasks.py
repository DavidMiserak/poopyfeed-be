"""Celery tasks for notification creation and cleanup."""

import logging
from datetime import timedelta

from celery import shared_task
from django.db import IntegrityError
from django.utils import timezone

logger = logging.getLogger(__name__)


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
        # bulk_create does not fire post_save; invalidate unread count cache per recipient
        from .cache import invalidate_unread_count_cache

        for recipient_id in {n.recipient_id for n in notifications}:
            invalidate_unread_count_cache(recipient_id)

        # Send push notifications
        from .fcm import send_push_to_user

        for n in notifications:
            try:
                send_push_to_user(
                    n.recipient_id,
                    title=child.name,
                    body=n.message,
                    data={"event_type": event_type, "child_id": str(child_id)},
                )
            except Exception:
                logger.exception("Failed to send push for activity notification")

    return f"Created {len(notifications)} notifications"


@shared_task(bind=True, time_limit=120)
def cleanup_old_notifications(self):
    """Delete notifications older than 30 days. Runs daily via Celery Beat."""
    from .models import DeviceToken, FeedingReminderLog, Notification, PatternAlertLog

    cutoff = timezone.now() - timedelta(days=30)
    deleted_count, _ = Notification.objects.filter(created_at__lt=cutoff).delete()

    # Also cleanup old FeedingReminderLog entries
    log_cutoff = timezone.now() - timedelta(days=7)
    log_deleted_count, _ = FeedingReminderLog.objects.filter(
        sent_at__lt=log_cutoff
    ).delete()

    # Cleanup old PatternAlertLog entries (7 days)
    pattern_log_deleted, _ = PatternAlertLog.objects.filter(
        sent_at__lt=log_cutoff
    ).delete()

    # Cleanup stale device tokens (inactive for 30+ days)
    token_deleted, _ = DeviceToken.objects.filter(
        is_active=False, updated_at__lt=cutoff
    ).delete()

    return (
        f"Deleted {deleted_count} notifications, {log_deleted_count} reminder logs, "
        f"{pattern_log_deleted} pattern alert logs, {token_deleted} stale device tokens"
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
        # Invalidate unread count cache (bulk_create skips post_save signals)
        from .cache import invalidate_unread_count_cache

        for recipient_id in {n.recipient_id for n in notifications}:
            invalidate_unread_count_cache(recipient_id)

        # Send push notifications for feeding reminders
        from .fcm import send_push_to_user

        for n in notifications:
            try:
                send_push_to_user(
                    n.recipient_id,
                    title=f"{child.name} — Feeding Reminder",
                    body=message,
                    data={
                        "event_type": "feeding_reminder",
                        "child_id": str(child.id),
                    },
                )
            except Exception:
                logger.exception("Failed to send push for feeding reminder")
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


@shared_task(bind=True, time_limit=60)
def check_pattern_alerts(self):
    """Check for pattern alerts and send push notifications.

    Runs every 15 minutes via Celery Beat. For each child with recent
    tracking activity, computes feeding interval and nap wake-window alerts.
    Uses PatternAlertLog for idempotency to prevent duplicate sends.
    Respects quiet hours (unlike feeding reminders, these are not safety-critical).
    """
    from dateutil.parser import isoparse  # type: ignore[import-untyped]

    from analytics.utils import compute_pattern_alerts
    from children.models import Child, ChildShare

    from .cache import invalidate_unread_count_cache
    from .fcm import send_push_to_user
    from .models import (
        Notification,
        NotificationPreference,
        PatternAlertLog,
        QuietHours,
    )

    now = timezone.now()
    recent_cutoff = now - timedelta(hours=48)

    # Only process children with recent feeding or nap activity
    from feedings.models import Feeding
    from naps.models import Nap

    active_child_ids = set(
        Feeding.objects.filter(fed_at__gte=recent_cutoff).values_list(
            "child_id", flat=True
        )
    ) | set(
        Nap.objects.filter(ended_at__gte=recent_cutoff).values_list(
            "child_id", flat=True
        )
    )

    if not active_child_ids:
        return "No active children to check"

    children = Child.objects.filter(id__in=active_child_ids).select_related("parent")

    # Prefetch shares, preferences, and quiet hours for all relevant users
    all_shares = {}
    for share in ChildShare.objects.filter(child_id__in=active_child_ids):
        all_shares.setdefault(share.child_id, set()).add(share.user_id)

    # Collect all relevant user IDs
    all_user_ids = set()
    for child in children:
        all_user_ids.add(child.parent_id)
    for user_ids in all_shares.values():
        all_user_ids.update(user_ids)

    # Prefetch preferences and quiet hours in bulk
    all_prefs = {}
    for p in NotificationPreference.objects.filter(
        user_id__in=all_user_ids, child_id__in=active_child_ids
    ):
        all_prefs[(p.user_id, p.child_id)] = p

    all_quiet_hours = {}
    for qh in QuietHours.objects.select_related("user").filter(
        user_id__in=all_user_ids, enabled=True
    ):
        all_quiet_hours[qh.user_id] = qh

    alert_count = 0

    for child in children:
        try:
            alerts = compute_pattern_alerts(child.id, now=now)
        except Exception:
            logger.exception("compute_pattern_alerts failed for child %s", child.id)
            continue

        for alert_type in ("feeding", "nap"):
            alert_data = alerts[alert_type]
            if not alert_data["alert"]:
                continue

            # Determine window_start from the alert data
            if alert_type == "feeding":
                last_event_str = alert_data.get("last_fed_at")
            else:
                last_event_str = alert_data.get("last_nap_ended_at")

            if not last_event_str:
                continue

            try:
                window_start = isoparse(last_event_str)
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid date in pattern alert for child %s: %s",
                    child.id,
                    last_event_str,
                )
                continue

            # Check idempotency
            if PatternAlertLog.objects.filter(
                child=child, alert_type=alert_type, window_start=window_start
            ).exists():
                continue

            # Build recipients: owner + shared users
            recipient_ids = {child.parent_id}
            recipient_ids.update(all_shares.get(child.id, set()))

            # Filter by preference and quiet hours
            pref_field = "notify_feedings" if alert_type == "feeding" else "notify_naps"
            message = alert_data["message"]
            notifications = []
            for recipient_id in recipient_ids:
                pref = all_prefs.get((recipient_id, child.id))
                if pref and not getattr(pref, pref_field):
                    continue

                qh = all_quiet_hours.get(recipient_id)
                if qh and qh.is_quiet_now():
                    continue

                notifications.append(
                    Notification(
                        recipient_id=recipient_id,
                        actor=None,
                        child=child,
                        event_type=Notification.EventType.PATTERN_ALERT,
                        message=message,
                    )
                )

            if notifications:
                Notification.objects.bulk_create(notifications)
                for n in notifications:
                    invalidate_unread_count_cache(n.recipient_id)
                    try:
                        send_push_to_user(
                            n.recipient_id,
                            title=f"{child.name} — Pattern Alert",
                            body=message,
                            data={
                                "event_type": "pattern_alert",
                                "child_id": str(child.id),
                                "alert_type": alert_type,
                            },
                        )
                    except Exception:
                        logger.exception("Failed to send push for pattern alert")
                alert_count += len(notifications)

            # Log for idempotency (even if no recipients after filtering)
            try:
                PatternAlertLog.objects.create(
                    child=child, alert_type=alert_type, window_start=window_start
                )
            except IntegrityError:
                pass

    return f"Created {alert_count} pattern alert notifications"
