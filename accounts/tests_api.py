"""API tests for account management endpoints."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from django_project.test_constants import TEST_PASSWORD

User = get_user_model()


class UserProfileAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password=TEST_PASSWORD,
            first_name="Test",
            last_name="User",
        )
        cls.other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password=TEST_PASSWORD,
        )

    def setUp(self):
        self.client = APIClient()
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_get_profile(self):
        response = self.client.get("/api/v1/account/profile/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.user.pk)
        self.assertEqual(response.data["email"], "test@example.com")
        self.assertEqual(response.data["first_name"], "Test")
        self.assertEqual(response.data["last_name"], "User")
        self.assertEqual(response.data["timezone"], "UTC")

    def test_get_profile_unauthenticated(self):
        self.client.credentials()
        response = self.client.get("/api/v1/account/profile/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_first_name(self):
        response = self.client.patch(
            "/api/v1/account/profile/",
            {"first_name": "Updated"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Updated")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")

    def test_update_last_name(self):
        response = self.client.patch(
            "/api/v1/account/profile/",
            {"last_name": "NewLast"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["last_name"], "NewLast")

    def test_update_email(self):
        response = self.client.patch(
            "/api/v1/account/profile/",
            {"email": "newemail@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "newemail@example.com")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "newemail@example.com")

    def test_update_email_duplicate(self):
        response = self.client.patch(
            "/api/v1/account/profile/",
            {"email": "other@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_update_email_same_as_current(self):
        """User can keep their current email."""
        response = self.client.patch(
            "/api/v1/account/profile/",
            {"email": "test@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_timezone(self):
        response = self.client.patch(
            "/api/v1/account/profile/",
            {"timezone": "America/New_York"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["timezone"], "America/New_York")
        self.user.refresh_from_db()
        self.assertEqual(self.user.timezone, "America/New_York")

    def test_update_timezone_invalid(self):
        response = self.client.patch(
            "/api/v1/account/profile/",
            {"timezone": "Invalid/Timezone"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("timezone", response.data)

    def test_update_multiple_fields(self):
        response = self.client.patch(
            "/api/v1/account/profile/",
            {
                "first_name": "New",
                "last_name": "Name",
                "timezone": "Europe/London",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "New")
        self.assertEqual(response.data["last_name"], "Name")
        self.assertEqual(response.data["timezone"], "Europe/London")

    def test_id_is_read_only(self):
        response = self.client.patch(
            "/api/v1/account/profile/",
            {"id": 999},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.user.pk)


class ChangePasswordAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="passuser",
            email="pass@example.com",
            password=TEST_PASSWORD,
        )

    def setUp(self):
        self.client = APIClient()
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_change_password_success(self):
        new_password = "NewSecurePass123!"  # noqa: S105
        response = self.client.post(
            "/api/v1/account/password/",
            {
                "current_password": TEST_PASSWORD,
                "new_password": new_password,
                "new_password_confirm": new_password,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("auth_token", response.data)
        self.assertIn("detail", response.data)

        # Old token should be invalid
        self.assertFalse(Token.objects.filter(key=self.token.key).exists())

        # New token should work
        new_token = response.data["auth_token"]
        self.assertTrue(Token.objects.filter(key=new_token).exists())

        # Password should be changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    def test_change_password_wrong_current(self):
        response = self.client.post(
            "/api/v1/account/password/",
            {
                "current_password": "wrongpassword",
                "new_password": "NewSecurePass123!",
                "new_password_confirm": "NewSecurePass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_password", response.data)

    def test_change_password_mismatch(self):
        response = self.client.post(
            "/api/v1/account/password/",
            {
                "current_password": TEST_PASSWORD,
                "new_password": "NewSecurePass123!",
                "new_password_confirm": "DifferentPass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password_confirm", response.data)

    def test_change_password_too_weak(self):
        response = self.client.post(
            "/api/v1/account/password/",
            {
                "current_password": TEST_PASSWORD,
                "new_password": "123",
                "new_password_confirm": "123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)

    def test_change_password_token_rotation(self):
        """After password change, only the new token is valid."""
        old_token_key = self.token.key
        new_password = "NewSecurePass123!"  # noqa: S105
        response = self.client.post(
            "/api/v1/account/password/",
            {
                "current_password": TEST_PASSWORD,
                "new_password": new_password,
                "new_password_confirm": new_password,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Old token should be gone
        self.assertFalse(Token.objects.filter(key=old_token_key).exists())

        # Trying with old token should fail
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {old_token_key}")
        response = self.client.get("/api/v1/account/profile/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_unauthenticated(self):
        self.client.credentials()
        response = self.client.post(
            "/api/v1/account/password/",
            {
                "current_password": TEST_PASSWORD,
                "new_password": "NewSecurePass123!",
                "new_password_confirm": "NewSecurePass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_missing_fields(self):
        response = self.client.post(
            "/api/v1/account/password/",
            {"current_password": TEST_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_common_password(self):
        response = self.client.post(
            "/api/v1/account/password/",
            {
                "current_password": TEST_PASSWORD,
                "new_password": "password123",
                "new_password_confirm": "password123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)


class DeleteAccountAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="deleteuser",
            email="delete@example.com",
            password=TEST_PASSWORD,
        )
        self.client = APIClient()
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_delete_account_success(self):
        user_pk = self.user.pk
        response = self.client.post(
            "/api/v1/account/delete/",
            {"current_password": TEST_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=user_pk).exists())

    def test_delete_account_wrong_password(self):
        response = self.client.post(
            "/api/v1/account/delete/",
            {"current_password": "wrongpassword"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_password", response.data)
        # User should still exist
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_delete_account_unauthenticated(self):
        self.client.credentials()
        response = self.client.post(
            "/api/v1/account/delete/",
            {"current_password": TEST_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_account_cascade(self):
        """Deleting a user cascades to their children and tokens."""
        from children.models import Child

        Child.objects.create(
            parent=self.user, name="TestChild", date_of_birth="2024-01-01"
        )
        user_pk = self.user.pk
        response = self.client.post(
            "/api/v1/account/delete/",
            {"current_password": TEST_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=user_pk).exists())
        self.assertFalse(Child.objects.filter(parent_id=user_pk).exists())
        self.assertFalse(Token.objects.filter(user_id=user_pk).exists())

    def test_delete_account_missing_password(self):
        response = self.client.post(
            "/api/v1/account/delete/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_account_returns_no_content(self):
        response = self.client.post(
            "/api/v1/account/delete/",
            {"current_password": TEST_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.content, b"")
