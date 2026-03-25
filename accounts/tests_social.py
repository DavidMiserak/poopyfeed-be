"""Tests for social account integration (allauth socialaccount)."""

from django.test import TestCase

from accounts.models import CustomUser
from django_project.test_constants import TEST_PASSWORD


class SocialAccountConfigTests(TestCase):
    """Verify social account configuration is correct."""

    def test_socialaccount_apps_installed(self):
        """allauth.socialaccount and provider apps are in INSTALLED_APPS."""
        from django.conf import settings

        assert "allauth.socialaccount" in settings.INSTALLED_APPS
        assert "allauth.socialaccount.providers.google" in settings.INSTALLED_APPS
        assert "allauth.socialaccount.providers.facebook" in settings.INSTALLED_APPS

    def test_email_authentication_enabled(self):
        """Social accounts auto-link by email."""
        from django.conf import settings

        assert settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION is True
        assert settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT is True

    def test_google_provider_configured(self):
        """Google provider has correct scopes."""
        from django.conf import settings

        google_config = settings.SOCIALACCOUNT_PROVIDERS.get("google", {})
        assert "email" in google_config.get("SCOPE", [])
        assert "profile" in google_config.get("SCOPE", [])

    def test_facebook_provider_configured(self):
        """Facebook provider has correct scopes."""
        from django.conf import settings

        fb_config = settings.SOCIALACCOUNT_PROVIDERS.get("facebook", {})
        assert "email" in fb_config.get("SCOPE", [])
        assert "public_profile" in fb_config.get("SCOPE", [])


class SocialAccountEndpointTests(TestCase):
    """Verify social account API endpoints are accessible."""

    def test_provider_redirect_endpoint_exists(self):
        """POST to provider redirect returns 400 (missing provider), not 404."""
        response = self.client.post(
            "/api/v1/browser/v1/auth/provider/redirect",
            content_type="application/json",
            secure=True,
        )
        # 400 = endpoint exists but request is invalid (no provider specified)
        # 401 or 403 = endpoint exists but needs auth
        # 404 = endpoint doesn't exist (test should fail)
        assert response.status_code != 404

    def test_providers_list_requires_auth(self):
        """GET providers list requires authentication."""
        response = self.client.get(
            "/api/v1/browser/v1/account/providers",
            secure=True,
        )
        assert response.status_code in (401, 403)

    def test_providers_list_returns_for_authenticated_user(self):
        """Authenticated user with no social accounts gets provider list."""
        user = CustomUser.objects.create_user(
            username="testuser",
            email="test@example.com",
            password=TEST_PASSWORD,
        )
        self.client.force_login(user)
        response = self.client.get(
            "/api/v1/browser/v1/account/providers",
            secure=True,
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("data", []) == []
