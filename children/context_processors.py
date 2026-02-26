"""Template context processors."""


def user_timezone(request):
    """Add user_timezone to template context (user's profile timezone or UTC)."""
    if request.user.is_authenticated and hasattr(request.user, "timezone"):
        tz = getattr(request.user, "timezone", None) or "UTC"
    else:
        tz = "UTC"
    return {"user_timezone": tz}
