"""Tests for custom middleware."""

import logging
from unittest.mock import patch

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from .middleware import APITimingMiddleware, CSRFExemptMiddleware


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


class APITimingMiddlewareTests(TestCase):
    """Tests for APITimingMiddleware query logging and Server-Timing header."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = APITimingMiddleware(
            get_response=lambda r: HttpResponse(status=200)
        )

    def _make_api_request(self):
        request = self.factory.get("/api/v1/children/")
        self.middleware.process_request(request)
        return request

    # --- Server-Timing header ---

    @override_settings(DEBUG=True, API_PERF_SLOW_QUERY_MS=100)
    def test_server_timing_includes_db_metric_in_debug(self):
        """Server-Timing header contains db metric when DEBUG=True."""
        fake_queries = [
            {"time": "0.005", "sql": "SELECT 1"},
            {"time": "0.010", "sql": "SELECT 2"},
        ]
        with patch("django_project.middleware.connection") as mock_conn:
            mock_conn.queries = fake_queries
            request = self._make_api_request()
            # Simulate query baseline at 0
            request._perf_query_start = 0
            response = self.middleware.process_response(request, HttpResponse())

        header = response["Server-Timing"]
        self.assertIn("total;dur=", header)
        self.assertIn("db;dur=", header)
        self.assertIn('desc="2 queries"', header)

    @override_settings(DEBUG=False)
    def test_server_timing_total_only_when_not_debug(self):
        """Server-Timing header only contains total when DEBUG=False."""
        request = self._make_api_request()
        response = self.middleware.process_response(request, HttpResponse())

        header = response["Server-Timing"]
        self.assertIn("total;dur=", header)
        self.assertNotIn("db;dur=", header)

    # --- Query count logging ---

    @override_settings(DEBUG=True, API_PERF_SLOW_QUERY_MS=100)
    def test_query_count_in_log_output(self):
        """Log message includes query count and db time in DEBUG."""
        fake_queries = [{"time": "0.002", "sql": "SELECT 1"}]
        with (
            patch("django_project.middleware.connection") as mock_conn,
            self.assertLogs("poopyfeed.performance", level="INFO") as cm,
        ):
            mock_conn.queries = fake_queries
            request = self._make_api_request()
            request._perf_query_start = 0
            self.middleware.process_response(request, HttpResponse())

        log_output = "\n".join(cm.output)
        self.assertIn("queries=1", log_output)
        self.assertIn("db=", log_output)

    @override_settings(DEBUG=False)
    def test_no_query_stats_when_not_debug(self):
        """No query stats in log output when DEBUG=False."""
        with self.assertLogs("poopyfeed.performance", level="INFO") as cm:
            request = self._make_api_request()
            self.middleware.process_response(request, HttpResponse())

        log_output = "\n".join(cm.output)
        self.assertNotIn("queries=", log_output)

    # --- Slow query logging ---

    @override_settings(DEBUG=True, API_PERF_SLOW_QUERY_MS=50)
    def test_slow_query_logged_at_warning(self):
        """Individual slow queries are logged at WARNING."""
        fake_queries = [
            {"time": "0.010", "sql": "SELECT fast"},
            {"time": "0.200", "sql": "SELECT slow FROM big_table"},
        ]
        with (
            patch("django_project.middleware.connection") as mock_conn,
            self.assertLogs("poopyfeed.performance", level="DEBUG") as cm,
        ):
            mock_conn.queries = fake_queries
            request = self._make_api_request()
            request._perf_query_start = 0
            self.middleware.process_response(request, HttpResponse())

        warning_logs = [m for m in cm.output if "WARNING" in m]
        self.assertTrue(
            any(
                "SLOW QUERY" in m and "SELECT slow FROM big_table" in m
                for m in warning_logs
            ),
            f"Expected SLOW QUERY warning, got: {warning_logs}",
        )
        # The fast query should NOT appear as a slow query warning
        self.assertFalse(
            any("SELECT fast" in m for m in warning_logs),
        )

    @override_settings(DEBUG=True, API_PERF_SLOW_QUERY_MS=9999)
    def test_no_slow_query_warning_below_threshold(self):
        """No SLOW QUERY warning when all queries are fast."""
        fake_queries = [{"time": "0.005", "sql": "SELECT 1"}]
        with (
            patch("django_project.middleware.connection") as mock_conn,
            self.assertLogs("poopyfeed.performance", level="DEBUG") as cm,
        ):
            mock_conn.queries = fake_queries
            request = self._make_api_request()
            request._perf_query_start = 0
            self.middleware.process_response(request, HttpResponse())

        self.assertFalse(any("SLOW QUERY" in m for m in cm.output))

    # --- Non-API requests ---

    def test_non_api_request_skipped(self):
        """Non-API requests don't get Server-Timing header."""
        request = self.factory.get("/admin/")
        self.middleware.process_request(request)
        response = self.middleware.process_response(request, HttpResponse())
        self.assertNotIn("Server-Timing", response)

    def test_request_without_start_time(self):
        """Response returned as-is when _perf_start is missing."""
        request = self.factory.get("/api/v1/children/")
        # Skip process_request — no _perf_start set
        response = HttpResponse()
        result = self.middleware.process_response(request, response)
        self.assertIs(result, response)
