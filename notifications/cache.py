"""Cache helpers for notification-related data."""

from django.core.cache import cache

UNREAD_COUNT_CACHE_TTL = 60  # seconds


def unread_count_cache_key(user_id: int) -> str:
    """Return cache key for a user's notification unread count."""
    return f"notification_unread_count_{user_id}"


def invalidate_unread_count_cache(user_id: int) -> None:
    """Invalidate cached unread count for a user.

    Call when notifications are created for this user or when the user
    marks notifications as read, so the context processor and API
    return fresh counts.
    """
    cache.delete(unread_count_cache_key(user_id))
