import logging
import re
import time

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("poopyfeed.performance")


class APITimingMiddleware(MiddlewareMixin):
    """Middleware to measure and log API response times.

    Logs response time for all /api/ requests. Adds a Server-Timing header
    for visibility in browser DevTools. Slow requests (>500ms) are logged
    at WARNING level.
    """

    SLOW_REQUEST_THRESHOLD_MS = 500

    def process_request(self, request: HttpRequest) -> None:
        """Record request start time."""
        setattr(request, "_perf_start", time.monotonic())

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        """Log response time and add Server-Timing header for API requests."""
        start = getattr(request, "_perf_start", None)
        if start is None:
            return response

        duration_ms = (time.monotonic() - start) * 1000

        if request.path_info.startswith("/api/"):
            response["Server-Timing"] = f"total;dur={duration_ms:.1f}"

            log_data = {
                "method": request.method,
                "path": request.path_info,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 1),
            }

            if duration_ms >= self.SLOW_REQUEST_THRESHOLD_MS:
                logger.warning(
                    "Slow API response: %(duration_ms).1fms %(method)s %(path)s [%(status)s]",
                    log_data,
                )
            else:
                logger.info(
                    "%(method)s %(path)s [%(status)s] %(duration_ms).1fms", log_data
                )

        return response


class CSRFExemptMiddleware(MiddlewareMixin):
    """Middleware to exempt specific URLs from CSRF validation."""

    def process_request(self, request: HttpRequest) -> None:
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

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        """Add Cache-Control headers to API responses."""
        if request.path_info.startswith("/api/"):
            response["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        return response
