import re

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class CSRFExemptMiddleware(MiddlewareMixin):
    """Middleware to exempt specific URLs from CSRF validation."""

    def process_request(self, request):
        """Exempt URLs matching patterns in CSRF_EXEMPT_URLS from CSRF."""
        if hasattr(settings, "CSRF_EXEMPT_URLS"):
            path = request.path_info.lstrip("/")
            for pattern in settings.CSRF_EXEMPT_URLS:
                if re.match(pattern, path):
                    setattr(request, "_dont_enforce_csrf_checks", True)
                    break


class NoCacheAPIMiddleware(MiddlewareMixin):
    """Middleware to disable browser caching on API responses.

    Prevents stale data being served from browser cache. This is critical for
    the children list endpoint which includes last-activity timestamps that
    update frequently. Without this, users see cached data with "Just Now"
    timestamps even hours after an activity was logged.

    Applies to all `/api/` endpoints to ensure fresh data for time-sensitive
    content (activity feeds, notifications, etc.).
    """

    def process_response(self, request, response):
        """Add Cache-Control headers to API responses."""
        if request.path_info.startswith("/api/"):
            response["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        return response
