"""Model and signal tests for the notifications app."""

from datetime import date, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from children.models import Child, ChildShare

from .models import Notification, NotificationPreference, QuietHours
from .signals import tracking_created

User = get_user_model()


class NotificationModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="testpass123",  # noqa: S106
        )
        cls.coparent = User.objects.create_user(
            username="coparent",
            email="coparent@example.com",
            password="testpass123",  # noqa: S106
        )
        cls.child = Child.objects.create(
            parent=cls.owner, name="Baby Alice", date_of_birth=date(2025, 6, 15)
        )

    def test_notification_creation(self):
        notif = Notification.objects.create(
            recipient=self.owner,
            actor=self.coparent,
            child=self.child,
            event_type=Notification.EventType.FEEDING,
            message="Test logged a feeding for Baby Alice",
        )
        self.assertEqual(notif.is_read, False)
        self.assertIsNotNone(notif.created_at)

    def test_notification_str(self):
        notif = Notification.objects.create(
            recipient=self.owner,
            actor=self.coparent,
            child=self.child,
            event_type=Notification.EventType.FEEDING,
            message="Test message",
        )
        self.assertIn("owner@example.com", str(notif))
        self.assertIn("Test message", str(notif))

    def test_notification_ordering(self):
        """Notifications are ordered newest first."""
        Notification.objects.create(
            recipient=self.owner,
            actor=self.coparent,
            child=self.child,
            event_type=Notification.EventType.FEEDING,
            message="First",
        )
        Notification.objects.create(
            recipient=self.owner,
            actor=self.coparent,
            child=self.child,
            event_type=Notification.EventType.DIAPER,
            message="Second",
        )
        notifications = list(Notification.objects.filter(recipient=self.owner))
        self.assertEqual(notifications[0].message, "Second")
        self.assertEqual(notifications[1].message, "First")

    def test_serializer_handles_null_actor(self):
        """Serializer should return 'System' for notifications with no actor."""
        from .serializers import NotificationSerializer

        notif = Notification.objects.create(
            recipient=self.owner,
            actor=None,
            child=self.child,
            event_type=Notification.EventType.FEEDING_REMINDER,
            message="Baby hasn't been fed for 3 hours",
        )
        serializer = NotificationSerializer(notif)
        self.assertEqual(serializer.data["actor_name"], "System")

    def test_serializer_returns_actor_first_name(self):
        """Serializer should return actor's first name when available."""
        from .serializers import NotificationSerializer

        self.coparent.first_name = "Jane"
        self.coparent.save()
        notif = Notification.objects.create(
            recipient=self.owner,
            actor=self.coparent,
            child=self.child,
            event_type=Notification.EventType.FEEDING,
            message="Jane logged a feeding",
        )
        serializer = NotificationSerializer(notif)
        self.assertEqual(serializer.data["actor_name"], "Jane")

    def test_serializer_falls_back_to_email(self):
        """Serializer should use email prefix when first_name is empty."""
        from .serializers import NotificationSerializer

        self.coparent.first_name = ""
        self.coparent.save()
        notif = Notification.objects.create(
            recipient=self.owner,
            actor=self.coparent,
            child=self.child,
            event_type=Notification.EventType.FEEDING,
            message="Someone logged a feeding",
        )
        serializer = NotificationSerializer(notif)
        self.assertEqual(serializer.data["actor_name"], "coparent")


class NotificationPreferenceModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="testpass123",  # noqa: S106
        )
        cls.child = Child.objects.create(
            parent=cls.user, name="Baby Bob", date_of_birth=date(2025, 6, 15)
        )

    def test_preference_defaults(self):
        pref = NotificationPreference.objects.create(user=self.user, child=self.child)
        self.assertTrue(pref.notify_feedings)
        self.assertTrue(pref.notify_diapers)
        self.assertTrue(pref.notify_naps)

    def test_preference_unique_together(self):
        NotificationPreference.objects.create(user=self.user, child=self.child)
        with self.assertRaises(IntegrityError):
            NotificationPreference.objects.create(user=self.user, child=self.child)

    def test_preference_str(self):
        pref = NotificationPreference.objects.create(user=self.user, child=self.child)
        self.assertIn("user1@example.com", str(pref))
        self.assertIn("Baby Bob", str(pref))


class QuietHoursModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="qhuser",
            email="qh@example.com",
            password="testpass123",  # noqa: S106
            timezone="America/New_York",
        )

    def test_quiet_hours_defaults(self):
        qh = QuietHours.objects.create(user=self.user)
        qh.refresh_from_db()
        self.assertFalse(qh.enabled)
        self.assertEqual(qh.start_time, time(22, 0))
        self.assertEqual(qh.end_time, time(7, 0))

    def test_quiet_hours_disabled_is_not_quiet(self):
        qh = QuietHours.objects.create(user=self.user, enabled=False)
        self.assertFalse(qh.is_quiet_now())

    @patch("notifications.models.timezone.now")
    def test_overnight_quiet_hours_during_quiet(self, mock_now):
        """22:00-07:00 at 23:00 ET should be quiet."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # 23:00 ET = 04:00 UTC next day
        mock_now.return_value = datetime(2026, 2, 26, 4, 0, 0, tzinfo=ZoneInfo("UTC"))
        qh = QuietHours.objects.create(
            user=self.user,
            enabled=True,
            start_time=time(22, 0),
            end_time=time(7, 0),
        )
        self.assertTrue(qh.is_quiet_now())

    @patch("notifications.models.timezone.now")
    def test_overnight_quiet_hours_outside_quiet(self, mock_now):
        """22:00-07:00 at 12:00 ET should NOT be quiet."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # 12:00 ET = 17:00 UTC
        mock_now.return_value = datetime(2026, 2, 26, 17, 0, 0, tzinfo=ZoneInfo("UTC"))
        qh = QuietHours.objects.create(
            user=self.user,
            enabled=True,
            start_time=time(22, 0),
            end_time=time(7, 0),
        )
        self.assertFalse(qh.is_quiet_now())

    @patch("notifications.models.timezone.now")
    def test_same_day_quiet_hours_during_quiet(self, mock_now):
        """09:00-17:00 at 12:00 ET should be quiet."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        mock_now.return_value = datetime(2026, 2, 26, 17, 0, 0, tzinfo=ZoneInfo("UTC"))
        qh = QuietHours.objects.create(
            user=self.user,
            enabled=True,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        self.assertTrue(qh.is_quiet_now())

    @patch("notifications.models.timezone.now")
    def test_same_day_quiet_hours_outside_quiet(self, mock_now):
        """09:00-17:00 at 20:00 ET should NOT be quiet."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # 20:00 ET = 01:00 UTC next day
        mock_now.return_value = datetime(2026, 2, 27, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
        qh = QuietHours.objects.create(
            user=self.user,
            enabled=True,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        self.assertFalse(qh.is_quiet_now())

    @patch("notifications.models.timezone.now")
    def test_overnight_quiet_hours_at_start_boundary(self, mock_now):
        """22:00-07:00 at exactly 22:00 ET should be quiet (inclusive start)."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # 22:00 ET = 03:00 UTC next day
        mock_now.return_value = datetime(2026, 2, 27, 3, 0, 0, tzinfo=ZoneInfo("UTC"))
        qh = QuietHours.objects.create(
            user=self.user,
            enabled=True,
            start_time=time(22, 0),
            end_time=time(7, 0),
        )
        self.assertTrue(qh.is_quiet_now())

    @patch("notifications.models.timezone.now")
    def test_overnight_quiet_hours_at_end_boundary(self, mock_now):
        """22:00-07:00 at exactly 07:00 ET should be quiet (inclusive end)."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # 07:00 ET = 12:00 UTC
        mock_now.return_value = datetime(2026, 2, 26, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        qh = QuietHours.objects.create(
            user=self.user,
            enabled=True,
            start_time=time(22, 0),
            end_time=time(7, 0),
        )
        self.assertTrue(qh.is_quiet_now())

    @patch("notifications.models.timezone.now")
    def test_same_day_quiet_hours_at_start_boundary(self, mock_now):
        """09:00-17:00 at exactly 09:00 ET should be quiet (inclusive start)."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # 09:00 ET = 14:00 UTC
        mock_now.return_value = datetime(2026, 2, 26, 14, 0, 0, tzinfo=ZoneInfo("UTC"))
        qh = QuietHours.objects.create(
            user=self.user,
            enabled=True,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        self.assertTrue(qh.is_quiet_now())

    @patch("notifications.models.timezone.now")
    def test_same_day_quiet_hours_at_end_boundary(self, mock_now):
        """09:00-17:00 at exactly 17:00 ET should be quiet (inclusive end)."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # 17:00 ET = 22:00 UTC
        mock_now.return_value = datetime(2026, 2, 26, 22, 0, 0, tzinfo=ZoneInfo("UTC"))
        qh = QuietHours.objects.create(
            user=self.user,
            enabled=True,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        self.assertTrue(qh.is_quiet_now())

    @patch("notifications.models.timezone.now")
    def test_same_day_quiet_hours_one_minute_after_end(self, mock_now):
        """09:00-17:00 at 17:01 ET should NOT be quiet."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # 17:01 ET = 22:01 UTC
        mock_now.return_value = datetime(2026, 2, 26, 22, 1, 0, tzinfo=ZoneInfo("UTC"))
        qh = QuietHours.objects.create(
            user=self.user,
            enabled=True,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        self.assertFalse(qh.is_quiet_now())

    def test_quiet_hours_str(self):
        qh = QuietHours.objects.create(user=self.user, enabled=True)
        self.assertIn("qh@example.com", str(qh))
        self.assertIn("ON", str(qh))


class NotificationTaskTests(TestCase):
    """Test the Celery task logic synchronously (no broker needed)."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="taskowner",
            email="taskowner@example.com",
            password="testpass123",  # noqa: S106
            first_name="Sarah",
        )
        cls.coparent = User.objects.create_user(
            username="taskcoparent",
            email="taskcoparent@example.com",
            password="testpass123",  # noqa: S106
            first_name="Michael",
        )
        cls.caregiver = User.objects.create_user(
            username="taskcg",
            email="taskcg@example.com",
            password="testpass123",  # noqa: S106
            first_name="Maria",
        )
        cls.child = Child.objects.create(
            parent=cls.owner, name="Baby Test", date_of_birth=date(2025, 6, 15)
        )
        ChildShare.objects.create(
            child=cls.child,
            user=cls.coparent,
            role=ChildShare.Role.CO_PARENT,
            created_by=cls.owner,
        )
        ChildShare.objects.create(
            child=cls.child,
            user=cls.caregiver,
            role=ChildShare.Role.CAREGIVER,
            created_by=cls.owner,
        )

    def test_creates_notifications_for_shared_users(self):
        """Caregiver logs feeding → owner and coparent get notifications."""
        from .tasks import create_notifications_for_activity

        create_notifications_for_activity(
            child_id=self.child.id,
            actor_id=self.caregiver.id,
            event_type="feeding",
        )
        # Owner and coparent should get notifications, not caregiver
        self.assertEqual(Notification.objects.filter(recipient=self.owner).count(), 1)
        self.assertEqual(
            Notification.objects.filter(recipient=self.coparent).count(), 1
        )
        self.assertEqual(
            Notification.objects.filter(recipient=self.caregiver).count(), 0
        )

    def test_no_self_notification(self):
        """Owner logs diaper → only coparent and caregiver get notifications."""
        from .tasks import create_notifications_for_activity

        create_notifications_for_activity(
            child_id=self.child.id,
            actor_id=self.owner.id,
            event_type="diaper",
        )
        self.assertEqual(Notification.objects.filter(recipient=self.owner).count(), 0)
        self.assertEqual(
            Notification.objects.filter(recipient=self.coparent).count(), 1
        )
        self.assertEqual(
            Notification.objects.filter(recipient=self.caregiver).count(), 1
        )

    def test_message_includes_actor_name_and_child(self):
        from .tasks import create_notifications_for_activity

        create_notifications_for_activity(
            child_id=self.child.id,
            actor_id=self.caregiver.id,
            event_type="nap",
        )
        notif = Notification.objects.filter(recipient=self.owner).first()
        self.assertIn("Maria", notif.message)
        self.assertIn("Baby Test", notif.message)
        self.assertIn("nap", notif.message)

    def test_preference_suppresses_notification(self):
        """If owner disables feeding notifications for this child, skip them."""
        from .tasks import create_notifications_for_activity

        NotificationPreference.objects.create(
            user=self.owner, child=self.child, notify_feedings=False
        )
        create_notifications_for_activity(
            child_id=self.child.id,
            actor_id=self.caregiver.id,
            event_type="feeding",
        )
        # Owner opted out of feedings, coparent should still get it
        self.assertEqual(Notification.objects.filter(recipient=self.owner).count(), 0)
        self.assertEqual(
            Notification.objects.filter(recipient=self.coparent).count(), 1
        )

    @patch("notifications.models.QuietHours.is_quiet_now", return_value=True)
    def test_quiet_hours_suppress_notification(self, mock_quiet):
        """Notifications not created during quiet hours."""
        from .tasks import create_notifications_for_activity

        QuietHours.objects.create(user=self.owner, enabled=True)
        create_notifications_for_activity(
            child_id=self.child.id,
            actor_id=self.caregiver.id,
            event_type="feeding",
        )
        # Owner in quiet hours, coparent should still get it
        self.assertEqual(Notification.objects.filter(recipient=self.owner).count(), 0)
        self.assertEqual(
            Notification.objects.filter(recipient=self.coparent).count(), 1
        )

    def test_cleanup_old_notifications(self):
        """Cleanup task deletes notifications older than 30 days."""
        from .tasks import cleanup_old_notifications

        old_notif = Notification.objects.create(
            recipient=self.owner,
            actor=self.coparent,
            child=self.child,
            event_type="feeding",
            message="Old notification",
        )
        # Manually backdate
        Notification.objects.filter(id=old_notif.id).update(
            created_at=timezone.now() - timezone.timedelta(days=31)
        )
        new_notif = Notification.objects.create(
            recipient=self.owner,
            actor=self.coparent,
            child=self.child,
            event_type="diaper",
            message="New notification",
        )
        result = cleanup_old_notifications()
        self.assertIn("Deleted 1", result)
        self.assertIn("notification", result)
        self.assertFalse(Notification.objects.filter(id=old_notif.id).exists())
        self.assertTrue(Notification.objects.filter(id=new_notif.id).exists())

    def test_task_with_deleted_child(self):
        """Task handles missing child gracefully."""
        from .tasks import create_notifications_for_activity

        result = create_notifications_for_activity(
            child_id=99999,
            actor_id=self.caregiver.id,
            event_type="feeding",
        )
        self.assertEqual(result, "Child not found")
        self.assertEqual(Notification.objects.count(), 0)

    def test_task_with_deleted_actor(self):
        """Task handles missing actor gracefully."""
        from .tasks import create_notifications_for_activity

        result = create_notifications_for_activity(
            child_id=self.child.id,
            actor_id=99999,
            event_type="feeding",
        )
        self.assertEqual(result, "Actor not found")
        self.assertEqual(Notification.objects.count(), 0)

    def test_unknown_event_type_returns_early(self):
        """Task rejects unknown event types without creating notifications."""
        from .tasks import create_notifications_for_activity

        result = create_notifications_for_activity(
            child_id=self.child.id,
            actor_id=self.caregiver.id,
            event_type="unknown",
        )
        self.assertIn("Unknown event type", result)
        self.assertEqual(Notification.objects.count(), 0)


class SignalDispatchTests(TestCase):
    """Test that the tracking_created signal dispatches correctly."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="sigowner",
            email="sigowner@example.com",
            password="testpass123",  # noqa: S106
        )
        cls.child = Child.objects.create(
            parent=cls.owner, name="Signal Baby", date_of_birth=date(2025, 6, 15)
        )

    @patch("notifications.tasks.create_notifications_for_activity")
    def test_signal_queues_celery_task(self, mock_task):
        """tracking_created signal should call the Celery task."""
        from diapers.models import DiaperChange

        instance = DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=timezone.now(),
        )
        tracking_created.send(
            sender=DiaperChange,
            instance=instance,
            actor_id=self.owner.id,
            event_type="diaper",
        )
        mock_task.delay.assert_called_once_with(
            child_id=self.child.id,
            actor_id=self.owner.id,
            event_type="diaper",
        )


class FeedingReminderTaskTests(TestCase):
    """Test the check_feeding_reminders Celery task."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="remowner",
            email="remowner@example.com",
            password="testpass123",  # noqa: S106
            first_name="Sarah",
        )
        cls.coparent = User.objects.create_user(
            username="remcoparent",
            email="remcoparent@example.com",
            password="testpass123",  # noqa: S106
            first_name="Michael",
        )
        cls.caregiver = User.objects.create_user(
            username="remcg",
            email="remcg@example.com",
            password="testpass123",  # noqa: S106
            first_name="Maria",
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name="Baby Reminder",
            date_of_birth=date(2025, 6, 15),
            feeding_reminder_interval=3,  # 3 hours
        )
        ChildShare.objects.create(
            child=cls.child,
            user=cls.coparent,
            role=ChildShare.Role.CO_PARENT,
            created_by=cls.owner,
        )
        ChildShare.objects.create(
            child=cls.child,
            user=cls.caregiver,
            role=ChildShare.Role.CAREGIVER,
            created_by=cls.owner,
        )

    def test_no_reminder_without_feedings(self):
        """No reminders sent if child has no feedings (FR-REM-006)."""
        from .tasks import check_feeding_reminders

        result = check_feeding_reminders()
        self.assertEqual(Notification.objects.filter(child=self.child).count(), 0)
        self.assertIn("Created 0", result)

    def test_initial_reminder_fires_at_threshold(self):
        """Initial reminder fires when time since feeding >= interval (AC-001)."""
        from feedings.models import Feeding

        # Create feeding 3h 5m ago
        last_fed_at = timezone.now() - timezone.timedelta(hours=3, minutes=5)
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            amount_oz=4,
            fed_at=last_fed_at,
        )

        from .tasks import check_feeding_reminders

        result = check_feeding_reminders()
        # Owner, coparent, and caregiver should all get notifications
        self.assertEqual(
            Notification.objects.filter(child=self.child, recipient=self.owner).count(),
            1,
        )
        self.assertEqual(
            Notification.objects.filter(
                child=self.child, recipient=self.coparent
            ).count(),
            1,
        )
        self.assertEqual(
            Notification.objects.filter(
                child=self.child, recipient=self.caregiver
            ).count(),
            1,
        )
        # Check FeedingReminderLog was created
        from .models import FeedingReminderLog

        log = FeedingReminderLog.objects.filter(child=self.child, reminder_number=1)
        self.assertEqual(log.count(), 1)
        self.assertEqual(log.first().window_start, last_fed_at)

    def test_no_reminder_under_threshold(self):
        """No reminder if time since feeding < interval."""
        from feedings.models import Feeding

        # Create feeding 2h 50m ago (before 3h threshold)
        last_fed_at = timezone.now() - timezone.timedelta(hours=2, minutes=50)
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            amount_oz=4,
            fed_at=last_fed_at,
        )

        from .tasks import check_feeding_reminders

        check_feeding_reminders()
        self.assertEqual(Notification.objects.filter(child=self.child).count(), 0)

    def test_repeat_reminder_fires_at_1_5x_threshold(self):
        """Repeat reminder fires when time since feeding >= interval * 1.5 (AC-002)."""
        from feedings.models import Feeding

        # Create feeding 4h 35m ago (> 3 * 1.5 = 4.5h threshold)
        last_fed_at = timezone.now() - timezone.timedelta(hours=4, minutes=35)
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            amount_oz=4,
            fed_at=last_fed_at,
        )

        from .models import FeedingReminderLog

        # Manually log that initial reminder was already sent
        FeedingReminderLog.objects.create(
            child=self.child, window_start=last_fed_at, reminder_number=1
        )

        from .tasks import check_feeding_reminders

        check_feeding_reminders()
        # Should get both initial (from setup) and repeat reminders
        initial_notifs = Notification.objects.filter(
            child=self.child, recipient=self.owner
        )
        self.assertGreaterEqual(initial_notifs.count(), 1)

        # Check repeat log was created
        repeat_log = FeedingReminderLog.objects.filter(
            child=self.child, reminder_number=2
        )
        self.assertEqual(repeat_log.count(), 1)

    def test_no_third_reminder(self):
        """Only two reminders per window (initial + repeat), no third (AC-003)."""
        from feedings.models import Feeding

        from .models import FeedingReminderLog

        # Create feeding 5h ago
        last_fed_at = timezone.now() - timezone.timedelta(hours=5)
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            amount_oz=4,
            fed_at=last_fed_at,
        )

        # Log both initial and repeat reminders
        FeedingReminderLog.objects.create(
            child=self.child, window_start=last_fed_at, reminder_number=1
        )
        FeedingReminderLog.objects.create(
            child=self.child, window_start=last_fed_at, reminder_number=2
        )

        # Clear any notifications from previous setup
        Notification.objects.filter(child=self.child).delete()

        from .tasks import check_feeding_reminders

        check_feeding_reminders()
        # No new notifications should be created
        self.assertEqual(Notification.objects.filter(child=self.child).count(), 0)

    def test_window_reset_on_new_feeding(self):
        """New feeding resets reminder window (AC-004)."""
        from feedings.models import Feeding

        from .models import FeedingReminderLog

        # Create old feeding 5h ago
        old_fed_at = timezone.now() - timezone.timedelta(hours=5)
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            amount_oz=4,
            fed_at=old_fed_at,
        )

        # Log reminders for old feeding
        FeedingReminderLog.objects.create(
            child=self.child, window_start=old_fed_at, reminder_number=1
        )
        FeedingReminderLog.objects.create(
            child=self.child, window_start=old_fed_at, reminder_number=2
        )

        # Create new feeding 10 minutes ago
        new_fed_at = timezone.now() - timezone.timedelta(minutes=10)
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            amount_oz=4,
            fed_at=new_fed_at,
        )

        # Clear notifications
        Notification.objects.filter(child=self.child).delete()

        from .tasks import check_feeding_reminders

        check_feeding_reminders()
        # No reminder should fire (< 3h since new feeding)
        self.assertEqual(Notification.objects.filter(child=self.child).count(), 0)

        # Create a separate child with 3h+ since feeding to verify task still works
        child2 = Child.objects.create(
            parent=self.owner,
            name="Baby 2",
            date_of_birth=date(2025, 6, 15),
            feeding_reminder_interval=3,
        )
        old_fed_at2 = timezone.now() - timezone.timedelta(hours=3, minutes=5)
        Feeding.objects.create(
            child=child2,
            feeding_type=Feeding.FeedingType.BOTTLE,
            amount_oz=4,
            fed_at=old_fed_at2,
        )

        check_feeding_reminders()
        # Reminder should fire for child2
        self.assertGreaterEqual(Notification.objects.filter(child=child2).count(), 1)

    def test_notify_feedings_preference_respected(self):
        """Reminders respect notify_feedings preference (AC-006, FR-REM-009)."""
        from feedings.models import Feeding

        # Create feeding 3h 5m ago
        last_fed_at = timezone.now() - timezone.timedelta(hours=3, minutes=5)
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            amount_oz=4,
            fed_at=last_fed_at,
        )

        # Disable feedings for owner
        NotificationPreference.objects.create(
            user=self.owner, child=self.child, notify_feedings=False
        )

        from .tasks import check_feeding_reminders

        check_feeding_reminders()
        # Owner should NOT get reminder, coparent should
        self.assertEqual(
            Notification.objects.filter(child=self.child, recipient=self.owner).count(),
            0,
        )
        self.assertEqual(
            Notification.objects.filter(
                child=self.child, recipient=self.coparent
            ).count(),
            1,
        )

    @patch("notifications.models.QuietHours.is_quiet_now", return_value=True)
    def test_quiet_hours_bypassed_for_reminders(self, mock_quiet):
        """Reminders bypass quiet hours (AC-007, FR-REM-008)."""
        from feedings.models import Feeding

        # Create feeding 3h 5m ago
        last_fed_at = timezone.now() - timezone.timedelta(hours=3, minutes=5)
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            amount_oz=4,
            fed_at=last_fed_at,
        )

        # Create quiet hours for owner
        QuietHours.objects.create(user=self.owner, enabled=True)

        from .tasks import check_feeding_reminders

        check_feeding_reminders()
        # Even though owner is in quiet hours, reminder should be sent
        # (because reminders bypass quiet hours per spec)
        notifs = Notification.objects.filter(
            child=self.child, recipient=self.owner, event_type="feeding_reminder"
        )
        self.assertGreaterEqual(notifs.count(), 1)

    def test_disabled_reminders_not_sent(self):
        """No reminders when interval is null."""
        self.child.feeding_reminder_interval = None
        self.child.save()

        from feedings.models import Feeding

        # Create feeding 5h ago
        last_fed_at = timezone.now() - timezone.timedelta(hours=5)
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            amount_oz=4,
            fed_at=last_fed_at,
        )

        from .tasks import check_feeding_reminders

        check_feeding_reminders()
        self.assertEqual(Notification.objects.filter(child=self.child).count(), 0)

    def test_idempotency_prevents_duplicates(self):
        """Running task twice doesn't create duplicate reminders (FR-REM-011)."""
        from feedings.models import Feeding

        # Create feeding 3h 5m ago
        last_fed_at = timezone.now() - timezone.timedelta(hours=3, minutes=5)
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            amount_oz=4,
            fed_at=last_fed_at,
        )

        from .tasks import check_feeding_reminders

        # Run task twice
        check_feeding_reminders()
        notif_count_first = Notification.objects.filter(child=self.child).count()

        check_feeding_reminders()
        notif_count_second = Notification.objects.filter(child=self.child).count()

        # Should be the same (idempotent)
        self.assertEqual(notif_count_first, notif_count_second)

    def test_reminder_notification_event_type(self):
        """Reminder notifications have event_type='feeding_reminder'."""
        from feedings.models import Feeding

        # Create feeding 3h 5m ago
        last_fed_at = timezone.now() - timezone.timedelta(hours=3, minutes=5)
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            amount_oz=4,
            fed_at=last_fed_at,
        )

        from .tasks import check_feeding_reminders

        check_feeding_reminders()
        notif = Notification.objects.filter(child=self.child).first()
        self.assertEqual(notif.event_type, "feeding_reminder")
        self.assertIsNone(notif.actor)  # System-generated, no actor
