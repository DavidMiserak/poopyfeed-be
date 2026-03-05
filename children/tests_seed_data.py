"""Tests for the seed_data management command."""

import io

from django.core.management import call_command
from django.test import TestCase

from accounts.models import CustomUser
from children.models import Child, ChildShare, ShareInvite
from diapers.models import DiaperChange
from feedings.models import Feeding
from naps.models import Nap
from notifications.models import Notification, NotificationPreference, QuietHours

from .management.commands.seed_data import SEED_DOMAIN


class SeedDataCommandTests(TestCase):
    """Tests for seed_data management command."""

    def test_seed_data_creates_users_and_children(self):
        """Running seed_data creates 3 seed users and 3 children."""
        call_command("seed_data", stdout=io.StringIO())
        users = CustomUser.objects.filter(email__endswith=SEED_DOMAIN)
        self.assertEqual(users.count(), 3)
        emails = set(users.values_list("email", flat=True))
        self.assertIn("sarah@seed.poopyfeed.local", emails)
        self.assertIn("michael@seed.poopyfeed.local", emails)
        self.assertIn("maria@seed.poopyfeed.local", emails)

        children = Child.objects.filter(parent__email__endswith=SEED_DOMAIN)
        self.assertEqual(children.count(), 3)
        names = set(children.values_list("name", flat=True))
        self.assertEqual(names, {"Emma", "Liam", "Noah"})

    def test_seed_data_creates_tracking_records(self):
        """Running seed_data creates feedings, diapers, and naps over 14 days."""
        call_command("seed_data", stdout=io.StringIO())
        self.assertGreater(Feeding.objects.count(), 0)
        self.assertGreater(DiaperChange.objects.count(), 0)
        self.assertGreater(Nap.objects.count(), 0)
        # 14 days × 3 children × multiple events each
        self.assertGreaterEqual(
            Feeding.objects.count(), 14 * 3 * 3
        )  # min ~3/day toddler
        self.assertGreaterEqual(DiaperChange.objects.count(), 14 * 3 * 4)  # min ~4/day
        self.assertGreaterEqual(Nap.objects.count(), 14 * 3 * 1)  # min 1 nap/day

    def test_seed_data_creates_sharing_and_invite(self):
        """Running seed_data creates ChildShares and one ShareInvite."""
        call_command("seed_data", stdout=io.StringIO())
        self.assertGreater(ChildShare.objects.count(), 0)
        self.assertEqual(ShareInvite.objects.filter(is_active=True).count(), 1)

    def test_seed_data_creates_notification_prefs_and_quiet_hours(self):
        """Running seed_data creates notification preferences and quiet hours."""
        call_command("seed_data", stdout=io.StringIO())
        self.assertGreater(NotificationPreference.objects.count(), 0)
        self.assertEqual(QuietHours.objects.count(), 2)  # Sarah and Michael

    def test_seed_data_creates_sample_notifications(self):
        """Running seed_data creates sample in-app notifications."""
        call_command("seed_data", stdout=io.StringIO())
        self.assertGreater(Notification.objects.count(), 0)
        notifications = Notification.objects.filter(
            recipient__email__endswith=SEED_DOMAIN
        )
        self.assertGreaterEqual(notifications.count(), 10)

    def test_seed_data_idempotent_without_flush(self):
        """Running seed_data again without --flush warns and does not duplicate."""
        out = io.StringIO()
        call_command("seed_data", stdout=out)
        count_before = CustomUser.objects.filter(email__endswith=SEED_DOMAIN).count()
        self.assertEqual(count_before, 3)

        out2 = io.StringIO()
        call_command("seed_data", stdout=out2)
        count_after = CustomUser.objects.filter(email__endswith=SEED_DOMAIN).count()
        self.assertEqual(count_after, 3)
        self.assertIn("already exists", out2.getvalue())
        self.assertIn("--flush", out2.getvalue())

    def test_seed_data_flush_deletes_and_recreates(self):
        """Running seed_data --flush deletes seed users and recreates data."""
        out = io.StringIO()
        call_command("seed_data", stdout=out)
        user_ids_before = set(
            CustomUser.objects.filter(email__endswith=SEED_DOMAIN).values_list(
                "id", flat=True
            )
        )
        self.assertEqual(len(user_ids_before), 3)

        out2 = io.StringIO()
        call_command("seed_data", "--flush", stdout=out2)
        self.assertIn("Flushed", out2.getvalue())
        users_after = CustomUser.objects.filter(email__endswith=SEED_DOMAIN)
        self.assertEqual(users_after.count(), 3)
        # New user PKs (recreated)
        user_ids_after = set(users_after.values_list("id", flat=True))
        self.assertNotEqual(user_ids_before, user_ids_after)
        self.assertIn("Seed data created successfully", out2.getvalue())

    def test_seed_data_output_contains_login_credentials(self):
        """Command output includes login credentials and success message."""
        out = io.StringIO()
        call_command("seed_data", stdout=out)
        output = out.getvalue()
        self.assertIn("Seed data created successfully", output)
        self.assertIn("sarah@seed.poopyfeed.local", output)
        self.assertIn("michael@seed.poopyfeed.local", output)
        self.assertIn("maria@seed.poopyfeed.local", output)
        self.assertIn("seedpass123", output)
        self.assertIn("Emma", output)
        self.assertIn("Liam", output)
        self.assertIn("Noah", output)
