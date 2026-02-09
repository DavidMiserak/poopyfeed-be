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
