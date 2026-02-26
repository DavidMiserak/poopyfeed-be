"""Signal definitions and handlers for the notifications app.

Defines a custom `tracking_created` signal dispatched from TrackingViewSet
and BatchCreateView after saving tracking records. Handlers queue Celery
tasks to create notifications for shared users.
"""

from django.dispatch import Signal, receiver

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
