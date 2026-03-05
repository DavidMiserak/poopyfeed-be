from django.core.cache import cache

from .cache import UNREAD_COUNT_CACHE_TTL, unread_count_cache_key
from .models import Notification


def notification_unread_count(request):
    """
    Add unread notification count for the current user to the template context.

    Uses a short-lived cache (60s) to avoid a COUNT query on every request.
    Cache is invalidated when notifications are created or marked read.

    Returns:
        dict: {"notification_unread_count": int} when authenticated, else {}.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    key = unread_count_cache_key(user.id)
    count = cache.get(key)
    if count is None:
        count = Notification.objects.filter(recipient=user, is_read=False).count()
        cache.set(key, count, UNREAD_COUNT_CACHE_TTL)
    return {"notification_unread_count": count}
