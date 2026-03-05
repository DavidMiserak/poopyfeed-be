"""Tests for health check endpoints."""

from unittest.mock import patch

from django.test import TestCase


class HealthzTests(TestCase):
    """Tests for the liveness probe endpoint."""

    def test_healthz_returns_200(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")

    def test_healthz_no_auth_required(self):
        """Health check must work without authentication."""
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)


class ReadyzTests(TestCase):
    """Tests for the readiness probe endpoint."""

    def test_readyz_returns_200_when_healthy(self):
        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["checks"]["database"], "ok")
        self.assertEqual(data["checks"]["cache"], "ok")

    def test_readyz_returns_503_when_db_down(self):
        with patch("django_project.health.connection") as mock_conn:
            mock_conn.cursor.side_effect = Exception("DB connection refused")
            response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data["status"], "degraded")
        self.assertEqual(data["checks"]["database"], "unavailable")

    def test_readyz_returns_503_when_cache_down(self):
        with patch("django.core.cache.cache") as mock_cache:
            mock_cache.set.side_effect = Exception("Redis connection refused")
            response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data["status"], "degraded")
        self.assertEqual(data["checks"]["cache"], "unavailable")

    def test_readyz_no_auth_required(self):
        """Readiness check must work without authentication."""
        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 200)

    def test_readyz_returns_503_when_cache_get_returns_unexpected_value(self):
        """Readiness check fails when cache.get does not return the written value."""
        with patch("django.core.cache.cache") as mock_cache:
            mock_cache.set.return_value = None
            mock_cache.get.return_value = None  # e.g. key expired or wrong value
            response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data["status"], "degraded")
        self.assertEqual(data["checks"]["cache"], "unavailable")
