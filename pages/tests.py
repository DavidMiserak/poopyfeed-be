from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse

from .views import HomePageView


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
        User = get_user_model()
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(self.url)
        self.assertContains(response, "Go to My Children")
        self.assertContains(response, user.email)
        self.assertNotContains(response, "Get Started")
