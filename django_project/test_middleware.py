"""Tests for custom middleware."""

from django.conf import settings
from django.test import RequestFactory, TestCase, override_settings

from .middleware import CSRFExemptMiddleware


class CSRFExemptMiddlewareTests(TestCase):
    """Tests for CSRFExemptMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = CSRFExemptMiddleware(get_response=lambda r: r)

    @override_settings(CSRF_EXEMPT_URLS=[r"^api/v1/browser/v1/auth/"])
    def test_matching_url_is_exempted(self):
        """URLs matching CSRF_EXEMPT_URLS are exempted from CSRF."""
        request = self.factory.post("/api/v1/browser/v1/auth/login/")
        self.middleware.process_request(request)
        self.assertTrue(getattr(request, "_dont_enforce_csrf_checks", False))

    @override_settings(CSRF_EXEMPT_URLS=[r"^api/v1/browser/v1/auth/"])
    def test_non_matching_url_is_not_exempted(self):
        """URLs not matching CSRF_EXEMPT_URLS are not exempted."""
        request = self.factory.post("/api/v1/children/")
        self.middleware.process_request(request)
        self.assertFalse(getattr(request, "_dont_enforce_csrf_checks", False))

    @override_settings()
    def test_no_csrf_exempt_urls_setting(self):
        """No error when CSRF_EXEMPT_URLS setting is absent."""
        # Remove the setting entirely
        if hasattr(settings, "CSRF_EXEMPT_URLS"):
            delattr(settings, "CSRF_EXEMPT_URLS")
        request = self.factory.post("/api/v1/browser/v1/auth/login/")
        # Should not raise - just skips exempt logic
        self.middleware.process_request(request)
        self.assertFalse(getattr(request, "_dont_enforce_csrf_checks", False))
