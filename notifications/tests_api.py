"""API tests for the notifications system."""

from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from children.models import Child, ChildShare

from .models import Notification, NotificationPreference, QuietHours

User = get_user_model()

TEST_PASSWORD = "testpass123"  # noqa: S105


class NotificationAPITests(APITestCase):
    """Tests for GET /api/v1/notifications/ and related actions."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="notifuser",
            email="notifuser@example.com",
            password=TEST_PASSWORD,  # noqa: S106
            first_name="Alice",
        )
        cls.other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password=TEST_PASSWORD,  # noqa: S106
        )
        cls.child = Child.objects.create(
            parent=cls.user, name="Baby Notif", date_of_birth=date(2025, 6, 15)
        )

    def setUp(self):
        self.token = Token.objects.create(user=self.user)
        self.other_token = Token.objects.create(user=self.other_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _create_notification(self, recipient=None, is_read=False, message="Test"):
        return Notification.objects.create(
            recipient=recipient or self.user,
            actor=self.other_user,
            child=self.child,
            event_type=Notification.EventType.FEEDING,
            message=message,
            is_read=is_read,
        )

    def test_list_returns_own_notifications(self):
        self._create_notification(message="For me")
        self._create_notification(recipient=self.other_user, message="For other")
        response = self.client.get("/api/v1/notifications/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["message"], "For me")

    def test_list_ordered_newest_first(self):
        self._create_notification(message="First")
        self._create_notification(message="Second")
        response = self.client.get("/api/v1/notifications/")
        self.assertEqual(response.data["results"][0]["message"], "Second")
        self.assertEqual(response.data["results"][1]["message"], "First")

    def test_list_includes_actor_name_and_child_name(self):
        self._create_notification()
        response = self.client.get("/api/v1/notifications/")
        result = response.data["results"][0]
        self.assertIn("actor_name", result)
        self.assertIn("child_name", result)
        self.assertEqual(result["child_name"], "Baby Notif")

    def test_list_unauthenticated(self):
        self.client.credentials()
        response = self.client.get("/api/v1/notifications/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unread_count(self):
        self._create_notification(is_read=False)
        self._create_notification(is_read=False)
        self._create_notification(is_read=True)
        response = self.client.get("/api/v1/notifications/unread-count/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_unread_count_excludes_other_users(self):
        self._create_notification(is_read=False)
        self._create_notification(recipient=self.other_user, is_read=False)
        response = self.client.get("/api/v1/notifications/unread-count/")
        self.assertEqual(response.data["count"], 1)

    def test_mark_all_read(self):
        self._create_notification(is_read=False)
        self._create_notification(is_read=False)
        self._create_notification(is_read=True)
        response = self.client.post("/api/v1/notifications/mark-all-read/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated"], 2)
        # Verify all are now read
        self.assertEqual(
            Notification.objects.filter(recipient=self.user, is_read=False).count(), 0
        )

    def test_mark_single_read(self):
        notif = self._create_notification(is_read=False)
        response = self.client.patch(f"/api/v1/notifications/{notif.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_read"])
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_cannot_access_other_users_notification(self):
        notif = self._create_notification(recipient=self.other_user)
        response = self.client.patch(f"/api/v1/notifications/{notif.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_disabled(self):
        response = self.client.post(
            "/api/v1/notifications/",
            {"event_type": "feeding", "message": "hack"},
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class NotificationPreferenceAPITests(APITestCase):
    """Tests for GET/PATCH /api/v1/notifications/preferences/."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="prefuser",
            email="prefuser@example.com",
            password=TEST_PASSWORD,  # noqa: S106
        )
        cls.other_user = User.objects.create_user(
            username="prefother",
            email="prefother@example.com",
            password=TEST_PASSWORD,  # noqa: S106
        )
        cls.child = Child.objects.create(
            parent=cls.user, name="Baby Pref", date_of_birth=date(2025, 6, 15)
        )
        ChildShare.objects.create(
            child=cls.child,
            user=cls.other_user,
            role=ChildShare.Role.CO_PARENT,
            created_by=cls.user,
        )

    def setUp(self):
        self.token = Token.objects.create(user=self.user)
        self.other_token = Token.objects.create(user=self.other_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_list_auto_creates_preferences(self):
        """Listing preferences auto-creates rows for accessible children."""
        self.assertEqual(
            NotificationPreference.objects.filter(user=self.user).count(), 0
        )
        response = self.client.get("/api/v1/notifications/preferences/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["child_name"], "Baby Pref")
        self.assertTrue(results[0]["notify_feedings"])

    def test_list_shows_only_own_preferences(self):
        """Each user sees only their own preferences."""
        self.client.get("/api/v1/notifications/preferences/")  # auto-create for user
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        response = self.client.get("/api/v1/notifications/preferences/")
        results = response.data["results"]
        # other_user also has access via ChildShare, so should see 1 pref
        self.assertEqual(len(results), 1)
        # Verify it's the other_user's preference, not the owner's
        pref = NotificationPreference.objects.get(
            user=self.other_user, child=self.child
        )
        self.assertEqual(results[0]["id"], pref.id)

    def test_update_preference(self):
        pref = NotificationPreference.objects.create(user=self.user, child=self.child)
        response = self.client.patch(
            f"/api/v1/notifications/preferences/{pref.id}/",
            {"notify_feedings": False},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["notify_feedings"])
        pref.refresh_from_db()
        self.assertFalse(pref.notify_feedings)

    def test_cannot_update_other_users_preference(self):
        pref = NotificationPreference.objects.create(
            user=self.other_user, child=self.child
        )
        response = self.client.patch(
            f"/api/v1/notifications/preferences/{pref.id}/",
            {"notify_feedings": False},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_preferences_unauthenticated(self):
        self.client.credentials()
        response = self.client.get("/api/v1/notifications/preferences/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class QuietHoursAPITests(APITestCase):
    """Tests for GET/PATCH /api/v1/notifications/quiet-hours/."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="qhuser",
            email="qhuser@example.com",
            password=TEST_PASSWORD,  # noqa: S106
        )

    def setUp(self):
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_get_auto_creates_quiet_hours(self):
        self.assertFalse(QuietHours.objects.filter(user=self.user).exists())
        response = self.client.get("/api/v1/notifications/quiet-hours/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["enabled"])
        self.assertTrue(QuietHours.objects.filter(user=self.user).exists())

    def test_patch_quiet_hours(self):
        QuietHours.objects.create(user=self.user)
        response = self.client.patch(
            "/api/v1/notifications/quiet-hours/",
            {"enabled": True, "start_time": "23:00", "end_time": "06:00"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["enabled"])
        self.assertEqual(response.data["start_time"], "23:00:00")
        self.assertEqual(response.data["end_time"], "06:00:00")

    def test_patch_partial_update(self):
        """Can update just enabled without changing times."""
        QuietHours.objects.create(user=self.user)
        response = self.client.patch(
            "/api/v1/notifications/quiet-hours/",
            {"enabled": True},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["enabled"])

    def test_quiet_hours_unauthenticated(self):
        self.client.credentials()
        response = self.client.get("/api/v1/notifications/quiet-hours/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
