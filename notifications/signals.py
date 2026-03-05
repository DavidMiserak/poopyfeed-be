"""Signal definitions and handlers for the notifications app.

Defines a custom `tracking_created` signal dispatched from TrackingViewSet
and BatchCreateView after saving tracking records. Handlers queue Celery
tasks to create notifications for shared users.
"""

from django.db.models.signals import post_save
from django.dispatch import Signal, receiver

from .cache import invalidate_unread_count_cache
from .models import Notification

tracking_created = Signal()


@receiver(tracking_created)
def queue_notification_on_tracking_create(
    sender, instance, actor_id, event_type, **kwargs
):
    """Queue notification creation when a tracking record is created."""
    from .tasks import create_notifications_for_activity

    create_notifications_for_activity.delay(
        child_id=instance.child_id,
        actor_id=actor_id,
        event_type=event_type,
    )


@receiver(post_save, sender=Notification)
def invalidate_unread_count_on_notification_change(sender, instance, **kwargs):
    """Invalidate cached unread count when a notification is created or updated."""
    invalidate_unread_count_cache(instance.recipient_id)
