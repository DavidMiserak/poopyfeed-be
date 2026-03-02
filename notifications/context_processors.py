from .models import Notification


def notification_unread_count(request):
    """
    Add unread notification count for the current user to the template context.

    Returns:
        dict: {"notification_unread_count": int} when authenticated, else {}.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    count = Notification.objects.filter(recipient=user, is_read=False).count()
    return {"notification_unread_count": count}
