"""Tests for FCM push notification features.

Covers DeviceToken CRUD API, send_push_to_user utility, quiet hours
suppression, pattern alerts task, and stale token cleanup.
"""

import sys
from datetime import timedelta
from types import ModuleType
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from django_project.test_constants import TEST_PASSWORD

# Create mock firebase_admin modules so tests work without the package installed
_mock_messaging = MagicMock()
_mock_firebase_admin = ModuleType("firebase_admin")
_mock_firebase_admin.messaging = _mock_messaging  # type: ignore[attr-defined]
_mock_firebase_admin.credentials = MagicMock()  # type: ignore[attr-defined]
_mock_firebase_admin.initialize_app = MagicMock()  # type: ignore[attr-defined]
_mock_firebase_admin.get_app = MagicMock(side_effect=ValueError("No app"))  # type: ignore[attr-defined]


def _reset_fcm():
    """Reset FCM module state between tests."""
    import notifications.fcm as fcm_module

    fcm_module._firebase_app = None
    fcm_module._firebase_init_attempted = False


def _setup_fcm_mock():
    """Set up FCM with a mock app so send_push_to_user proceeds."""
    import notifications.fcm as fcm_module

    fcm_module._firebase_app = MagicMock()
    fcm_module._firebase_init_attempted = True


class DeviceTokenAPITests(TestCase):
    """Tests for device token registration/unregistration API."""

    @classmethod
    def setUpTestData(cls):
        from accounts.models import CustomUser

        cls.user = CustomUser.objects.create_user(
            username="push", email="push@example.com", password=TEST_PASSWORD
        )
        cls.user2 = CustomUser.objects.create_user(
            username="push2", email="push2@example.com", password=TEST_PASSWORD
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_register_device_token(self):
        resp = self.client.post(
            "/api/v1/notifications/devices/",
            {"token": "fcm-token-123", "platform": "android"},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["status"] == "registered"

        from notifications.models import DeviceToken

        token = DeviceToken.objects.get(token="fcm-token-123")
        assert token.user == self.user
        assert token.platform == "android"
        assert token.is_active is True

    def test_register_token_defaults_to_web(self):
        resp = self.client.post(
            "/api/v1/notifications/devices/",
            {"token": "web-token-456"},
        )
        assert resp.status_code == status.HTTP_201_CREATED

        from notifications.models import DeviceToken

        token = DeviceToken.objects.get(token="web-token-456")
        assert token.platform == "web"

    def test_register_existing_token_upserts(self):
        """Re-registering same token reassigns to current user (device handoff)."""
        client2 = APIClient()
        client2.force_authenticate(user=self.user2)
        client2.post(
            "/api/v1/notifications/devices/",
            {"token": "shared-token", "platform": "android"},
        )

        resp = self.client.post(
            "/api/v1/notifications/devices/",
            {"token": "shared-token", "platform": "android"},
        )
        assert resp.status_code == status.HTTP_200_OK

        from notifications.models import DeviceToken

        token = DeviceToken.objects.get(token="shared-token")
        assert token.user == self.user

    def test_unregister_device_token(self):
        from notifications.models import DeviceToken

        DeviceToken.objects.create(
            user=self.user, token="to-remove-token", platform="web"
        )

        resp = self.client.delete(
            "/api/v1/notifications/devices/",
            {"token": "to-remove-token"},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["status"] == "unregistered"

        token = DeviceToken.objects.get(token="to-remove-token")
        assert token.is_active is False

    def test_unregister_nonexistent_token_returns_404(self):
        resp = self.client.delete(
            "/api/v1/notifications/devices/",
            {"token": "does-not-exist"},
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_unregister_other_users_token_returns_404(self):
        from notifications.models import DeviceToken

        DeviceToken.objects.create(
            user=self.user2, token="other-user-token", platform="web"
        )

        resp = self.client.delete(
            "/api/v1/notifications/devices/",
            {"token": "other-user-token"},
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_register_requires_auth(self):
        client = APIClient()
        resp = client.post(
            "/api/v1/notifications/devices/",
            {"token": "anon-token"},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_reactivate_inactive_token(self):
        from notifications.models import DeviceToken

        DeviceToken.objects.create(
            user=self.user, token="inactive-token", platform="web", is_active=False
        )

        resp = self.client.post(
            "/api/v1/notifications/devices/",
            {"token": "inactive-token", "platform": "web"},
        )
        assert resp.status_code == status.HTTP_200_OK

        token = DeviceToken.objects.get(token="inactive-token")
        assert token.is_active is True


@patch.dict(
    sys.modules,
    {
        "firebase_admin": _mock_firebase_admin,
        "firebase_admin.messaging": _mock_messaging,
        "firebase_admin.credentials": _mock_firebase_admin.credentials,
    },
)
class SendPushToUserTests(TestCase):
    """Tests for the send_push_to_user FCM utility."""

    @classmethod
    def setUpTestData(cls):
        from accounts.models import CustomUser

        cls.user = CustomUser.objects.create_user(
            username="fcm", email="fcm@example.com", password=TEST_PASSWORD
        )

    def setUp(self):
        _mock_messaging.reset_mock()
        _mock_messaging.Message = MagicMock()
        _mock_messaging.Notification = MagicMock()
        # Mock send_each to return a BatchResponse with successful SendResponses
        self._mock_send_response = MagicMock(success=True, exception=None)
        self._mock_batch_response = MagicMock(
            responses=[self._mock_send_response],
            success_count=1,
        )
        _mock_messaging.send_each = MagicMock(return_value=self._mock_batch_response)

    def tearDown(self):
        _reset_fcm()

    def test_no_op_when_firebase_not_configured(self):
        """Returns 0 when Firebase is not initialized."""
        _reset_fcm()

        # Reimport to pick up mock modules
        import importlib

        import notifications.fcm

        importlib.reload(notifications.fcm)
        from notifications.fcm import send_push_to_user

        result = send_push_to_user(self.user.id, "Test", "Body")
        assert result == 0

    def test_no_op_when_no_active_tokens(self):
        _setup_fcm_mock()
        from notifications.fcm import send_push_to_user

        result = send_push_to_user(self.user.id, "Test", "Body")
        assert result == 0

    def test_sends_to_all_active_devices(self):
        from notifications.models import DeviceToken

        _setup_fcm_mock()

        DeviceToken.objects.create(user=self.user, token="token-1", platform="web")
        DeviceToken.objects.create(user=self.user, token="token-2", platform="android")
        DeviceToken.objects.create(
            user=self.user, token="token-inactive", platform="web", is_active=False
        )

        # Mock batch response with 2 successful sends
        resp1 = MagicMock(success=True, exception=None)
        resp2 = MagicMock(success=True, exception=None)
        _mock_messaging.send_each.return_value = MagicMock(responses=[resp1, resp2])

        from notifications.fcm import send_push_to_user

        result = send_push_to_user(self.user.id, "Title", "Body", data={"key": "val"})
        assert result == 2
        assert _mock_messaging.send_each.call_count == 1
        # Verify 2 messages were passed to send_each
        messages = _mock_messaging.send_each.call_args[0][0]
        assert len(messages) == 2

    def test_deactivates_stale_token_on_not_found(self):
        from notifications.models import DeviceToken

        _setup_fcm_mock()

        DeviceToken.objects.create(user=self.user, token="stale-token", platform="web")

        error = Exception("Token not found")
        error.code = "NOT_FOUND"
        failed_response = MagicMock(success=False, exception=error)
        _mock_messaging.send_each.return_value = MagicMock(responses=[failed_response])

        from notifications.fcm import send_push_to_user

        result = send_push_to_user(self.user.id, "Title", "Body")
        assert result == 0

        token = DeviceToken.objects.get(token="stale-token")
        assert token.is_active is False

    def test_android_gets_data_only_message(self):
        from notifications.models import DeviceToken

        _setup_fcm_mock()

        DeviceToken.objects.create(
            user=self.user, token="android-token", platform="android"
        )

        from notifications.fcm import send_push_to_user

        send_push_to_user(self.user.id, "Title", "Body")

        # The Message constructor should have been called with data but no notification
        msg = _mock_messaging.Message.call_args
        assert (
            msg.kwargs.get("notification") is None or "notification" not in msg.kwargs
        )
        assert "title" in msg.kwargs["data"]

    def test_web_gets_notification_and_data(self):
        from notifications.models import DeviceToken

        _setup_fcm_mock()

        DeviceToken.objects.create(user=self.user, token="web-token", platform="web")

        from notifications.fcm import send_push_to_user

        send_push_to_user(self.user.id, "Title", "Body")

        msg = _mock_messaging.Message.call_args
        # Web: notification + data
        assert msg.kwargs.get("notification") is not None

    def test_token_validation_rejects_short_token(self):
        """Serializer rejects tokens shorter than 10 chars."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.post(
            "/api/v1/notifications/devices/",
            {"token": "short"},
        )
        assert resp.status_code == 400


class ActivityPushNotificationTests(TestCase):
    """Tests that activity notifications also send push."""

    @classmethod
    def setUpTestData(cls):
        from accounts.models import CustomUser
        from children.models import Child

        cls.owner = CustomUser.objects.create_user(
            username="actowner", email="owner@test.com", password=TEST_PASSWORD
        )
        cls.actor = CustomUser.objects.create_user(
            username="actor", email="actor@test.com", password=TEST_PASSWORD
        )
        cls.child = Child.objects.create(
            parent=cls.owner, name="Baby", date_of_birth="2024-01-01"
        )

    @patch("notifications.fcm.send_push_to_user")
    def test_activity_notification_sends_push(self, mock_push):
        from notifications.tasks import create_notifications_for_activity

        result = create_notifications_for_activity(
            self.child.id, self.actor.id, "feeding"
        )
        assert "Created 1 notifications" in result
        mock_push.assert_called_once()
        call_kwargs = mock_push.call_args
        assert call_kwargs[0][0] == self.owner.id
        assert call_kwargs[1]["data"]["event_type"] == "feeding"


class FeedingReminderPushTests(TestCase):
    """Tests that feeding reminders also send push."""

    @classmethod
    def setUpTestData(cls):
        from accounts.models import CustomUser
        from children.models import Child

        cls.owner = CustomUser.objects.create_user(
            username="remowner", email="reminder-owner@test.com", password=TEST_PASSWORD
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name="Hungry Baby",
            date_of_birth="2024-01-01",
            feeding_reminder_interval=3,
        )

    @patch("notifications.fcm.send_push_to_user")
    def test_feeding_reminder_sends_push(self, mock_push):
        from feedings.models import Feeding
        from notifications.tasks import check_feeding_reminders

        Feeding.objects.create(
            child=self.child,
            feeding_type="breast",
            side="left",
            duration_minutes=15,
            fed_at=timezone.now() - timedelta(hours=4),
        )

        result = check_feeding_reminders()
        assert "Created 1 feeding reminder" in result
        mock_push.assert_called_once()
        assert mock_push.call_args[1]["data"]["event_type"] == "feeding_reminder"


class CleanupStaleTokensTests(TestCase):
    """Tests that cleanup task removes stale device tokens."""

    @classmethod
    def setUpTestData(cls):
        from accounts.models import CustomUser

        cls.user = CustomUser.objects.create_user(
            username="cleanup", email="cleanup@test.com", password=TEST_PASSWORD
        )

    def test_cleanup_removes_old_inactive_tokens(self):
        from notifications.models import DeviceToken
        from notifications.tasks import cleanup_old_notifications

        token = DeviceToken.objects.create(
            user=self.user, token="old-token", platform="web", is_active=False
        )
        DeviceToken.objects.filter(pk=token.pk).update(
            updated_at=timezone.now() - timedelta(days=31)
        )

        DeviceToken.objects.create(
            user=self.user, token="recent-token", platform="web", is_active=False
        )
        DeviceToken.objects.create(user=self.user, token="active-token", platform="web")

        result = cleanup_old_notifications()
        assert "1 stale device tokens" in result

        remaining = list(DeviceToken.objects.values_list("token", flat=True))
        assert "old-token" not in remaining
        assert "recent-token" in remaining
        assert "active-token" in remaining

    def test_cleanup_removes_old_pattern_alert_logs(self):
        from children.models import Child
        from notifications.models import PatternAlertLog
        from notifications.tasks import cleanup_old_notifications

        child = Child.objects.create(
            parent=self.user, name="Baby", date_of_birth="2024-01-01"
        )
        log = PatternAlertLog.objects.create(
            child=child,
            alert_type="feeding",
            window_start=timezone.now() - timedelta(days=10),
        )
        PatternAlertLog.objects.filter(pk=log.pk).update(
            sent_at=timezone.now() - timedelta(days=8)
        )

        result = cleanup_old_notifications()
        assert "1 pattern alert logs" in result
        assert not PatternAlertLog.objects.filter(pk=log.pk).exists()


class CheckPatternAlertsTests(TestCase):
    """Tests for the check_pattern_alerts periodic task."""

    @classmethod
    def setUpTestData(cls):
        from accounts.models import CustomUser
        from children.models import Child

        cls.owner = CustomUser.objects.create_user(
            username="patowner", email="pattern-owner@test.com", password=TEST_PASSWORD
        )
        cls.child = Child.objects.create(
            parent=cls.owner, name="Pattern Baby", date_of_birth="2024-01-01"
        )

    def setUp(self):
        """Add recent feeding so child is considered 'active'."""
        from feedings.models import Feeding

        Feeding.objects.create(
            child=self.child,
            feeding_type="breast",
            side="left",
            duration_minutes=10,
            fed_at=timezone.now() - timedelta(hours=4),
        )

    @patch("notifications.fcm.send_push_to_user")
    @patch("analytics.utils.compute_pattern_alerts")
    def test_creates_notification_and_push_on_alert(self, mock_compute, mock_push):
        from notifications.models import Notification, PatternAlertLog
        from notifications.tasks import check_pattern_alerts

        mock_compute.return_value = {
            "child_id": self.child.id,
            "feeding": {
                "alert": True,
                "message": "Baby usually feeds every 3h — it's been 4h",
                "last_fed_at": "2024-02-10T06:00:00+00:00",
                "data_points": 5,
            },
            "nap": {
                "alert": False,
                "message": None,
                "last_nap_ended_at": None,
                "data_points": 0,
            },
        }

        result = check_pattern_alerts()
        assert "Created 1 pattern alert" in result

        notif = Notification.objects.get(
            recipient=self.owner, event_type="pattern_alert"
        )
        assert "3h" in notif.message

        mock_push.assert_called_once()

        assert PatternAlertLog.objects.filter(
            child=self.child, alert_type="feeding"
        ).exists()

    @patch("notifications.fcm.send_push_to_user")
    @patch("analytics.utils.compute_pattern_alerts")
    def test_idempotency_prevents_duplicate_alerts(self, mock_compute, mock_push):
        from notifications.tasks import check_pattern_alerts

        mock_compute.return_value = {
            "child_id": self.child.id,
            "feeding": {
                "alert": True,
                "message": "Test alert",
                "last_fed_at": "2024-02-10T06:00:00+00:00",
                "data_points": 5,
            },
            "nap": {
                "alert": False,
                "message": None,
                "last_nap_ended_at": None,
                "data_points": 0,
            },
        }

        check_pattern_alerts()
        assert mock_push.call_count == 1

        check_pattern_alerts()
        assert mock_push.call_count == 1

    @patch("notifications.fcm.send_push_to_user")
    @patch("analytics.utils.compute_pattern_alerts")
    def test_quiet_hours_suppresses_pattern_alert(self, mock_compute, mock_push):
        from notifications.models import Notification, QuietHours
        from notifications.tasks import check_pattern_alerts

        qh = QuietHours.objects.create(user=self.owner, enabled=True)
        qh.start_time = "00:00"
        qh.end_time = "23:59"
        qh.save()

        mock_compute.return_value = {
            "child_id": self.child.id,
            "feeding": {
                "alert": True,
                "message": "Test alert",
                "last_fed_at": "2024-02-10T06:00:00+00:00",
                "data_points": 5,
            },
            "nap": {
                "alert": False,
                "message": None,
                "last_nap_ended_at": None,
                "data_points": 0,
            },
        }

        check_pattern_alerts()
        assert not Notification.objects.filter(
            recipient=self.owner, event_type="pattern_alert"
        ).exists()
        mock_push.assert_not_called()
