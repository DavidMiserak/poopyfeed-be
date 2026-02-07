import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse

from .views import HomePageView, OfflinePageView, ServiceWorkerView


class HomePageTests(TestCase):
    def setUp(self):
        self.url = reverse("home")
        self.response = self.client.get(self.url)

    def test_homepage_status_code(self):
        self.assertEqual(self.response.status_code, 200)

    def test_homepage_template(self):
        self.assertTemplateUsed(self.response, "pages/home.html")

    def test_homepage_contains_correct_html(self):
        self.assertContains(self.response, "PoopyFeed")
        self.assertContains(self.response, "Feeding Tracker")
        self.assertContains(self.response, "Diaper Changes")
        self.assertContains(self.response, "Sleep Patterns")
        self.assertContains(self.response, "Health Metrics")

    def test_homepage_url_resolves_homepageview(self):
        view = resolve("/")
        self.assertEqual(view.func.__name__, HomePageView.as_view().__name__)

    def test_homepage_shows_login_signup_for_anonymous(self):
        self.assertContains(self.response, "Get Started")
        self.assertContains(self.response, "Log In")
        self.assertContains(self.response, reverse("account_signup"))
        self.assertContains(self.response, reverse("account_login"))

    def test_homepage_shows_welcome_for_authenticated_user(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.url)
        self.assertContains(response, "Go to My Children")
        self.assertContains(response, user.email)
        self.assertNotContains(response, "Get Started")


class OfflinePageTests(TestCase):
    def setUp(self):
        self.url = reverse("offline")
        self.response = self.client.get(self.url)

    def test_offline_page_status_code(self):
        self.assertEqual(self.response.status_code, 200)

    def test_offline_page_template(self):
        self.assertTemplateUsed(self.response, "pwa/offline.html")

    def test_offline_page_contains_correct_content(self):
        self.assertContains(self.response, "You're Offline")
        self.assertContains(self.response, "Try Again")

    def test_offline_page_url_resolves_view(self):
        view = resolve("/offline/")
        self.assertEqual(view.func.__name__, OfflinePageView.as_view().__name__)


class ServiceWorkerTests(TestCase):
    def setUp(self):
        self.url = reverse("service_worker")
        self.response = self.client.get(self.url)

    def test_service_worker_status_code(self):
        self.assertEqual(self.response.status_code, 200)

    def test_service_worker_content_type(self):
        self.assertEqual(self.response["Content-Type"], "application/javascript")

    def test_service_worker_allowed_header(self):
        self.assertEqual(self.response["Service-Worker-Allowed"], "/")

    def test_service_worker_contains_cache_name(self):
        self.assertIn(b"poopyfeed-v1", self.response.content)

    def test_service_worker_contains_offline_url(self):
        self.assertIn(b"/offline/", self.response.content)

    def test_service_worker_url_resolves_view(self):
        view = resolve("/sw.js")
        self.assertEqual(view.func.__name__, ServiceWorkerView.as_view().__name__)


class PWAMetaTagsTests(TestCase):
    """Test that PWA meta tags are present in the base template."""

    def setUp(self):
        self.response = self.client.get(reverse("home"))

    def test_manifest_link_present(self):
        self.assertContains(self.response, 'rel="manifest"')
        # WhiteNoise adds hash to filename, so just check for manifest in the href
        self.assertContains(self.response, "manifest.")

    def test_theme_color_meta_tag_present(self):
        self.assertContains(self.response, 'name="theme-color"')
        self.assertContains(self.response, "#74C0FC")

    def test_apple_mobile_web_app_meta_tags_present(self):
        self.assertContains(self.response, 'name="apple-mobile-web-app-capable"')
        self.assertContains(self.response, 'name="apple-mobile-web-app-title"')
        self.assertContains(self.response, 'rel="apple-touch-icon"')

    def test_service_worker_registration_script_present(self):
        self.assertContains(self.response, "serviceWorker")
        self.assertContains(self.response, "/sw.js")


class ManifestTests(TestCase):
    """Test that the manifest.json file is valid and contains required fields."""

    def _load_manifest(self):
        """Load manifest.json directly from the static directory."""
        from pathlib import Path

        from django.conf import settings

        manifest_path = Path(settings.BASE_DIR) / "static" / "manifest.json"
        return json.loads(manifest_path.read_text())

    def test_manifest_is_valid_json(self):
        # Will raise json.JSONDecodeError if invalid, failing the test
        self._load_manifest()

    def test_manifest_contains_required_fields(self):
        manifest = self._load_manifest()
        self.assertIn("name", manifest)
        self.assertIn("short_name", manifest)
        self.assertIn("start_url", manifest)
        self.assertIn("display", manifest)
        self.assertIn("icons", manifest)

    def test_manifest_has_correct_values(self):
        manifest = self._load_manifest()
        self.assertEqual(manifest["short_name"], "PoopyFeed")
        self.assertEqual(manifest["theme_color"], "#74C0FC")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "/")
