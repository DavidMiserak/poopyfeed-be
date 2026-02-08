from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from django_project.test_constants import TEST_PASSWORD


class CustomUserTests(TestCase):
    def test_create_user(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="will", email="will@email.com", password=TEST_PASSWORD
        )
        self.assertEqual(user.username, "will")
        self.assertEqual(user.email, "will@email.com")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        user_model = get_user_model()
        admin_user = user_model.objects.create_superuser(
            username="superadmin", email="superadmin@email.com", password=TEST_PASSWORD
        )
        self.assertEqual(admin_user.username, "superadmin")
        self.assertEqual(admin_user.email, "superadmin@email.com")
        self.assertTrue(admin_user.is_active)
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)


class SignUpPageTests(TestCase):
    def setUp(self):
        url = reverse("account_signup")
        self.response = self.client.get(url)

    def test_signup_template(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertTemplateUsed(self.response, "account/signup.html")
        self.assertContains(self.response, "Sign Up")

    def test_signup_form(self):
        user_model = get_user_model()
        self.client.post(
            reverse("account_signup"),
            {
                "email": "testuser@email.com",
                "password1": TEST_PASSWORD,
                "password2": TEST_PASSWORD,
            },
        )
        self.assertEqual(user_model.objects.count(), 1)
        self.assertEqual(user_model.objects.first().email, "testuser@email.com")
