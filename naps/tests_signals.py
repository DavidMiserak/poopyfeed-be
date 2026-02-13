"""Tests for nap auto-end signals."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from children.models import Child
from diapers.models import DiaperChange
from django_project.test_constants import TEST_PASSWORD
from feedings.models import Feeding

from .models import Nap


class NapAutoEndSignalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="testparent",
            email="parent@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name="Baby Jane",
            date_of_birth=date(2025, 6, 15),
        )
        cls.other_child = Child.objects.create(
            parent=cls.user,
            name="Baby Joe",
            date_of_birth=date(2025, 8, 1),
        )

    def test_feeding_ends_open_nap(self):
        nap_start = timezone.now() - timedelta(hours=2)
        nap = Nap.objects.create(child=self.child, napped_at=nap_start)

        feeding_time = timezone.now() - timedelta(hours=1)
        Feeding.objects.create(
            child=self.child,
            fed_at=feeding_time,
            feeding_type="bottle",
            amount_oz=4.0,
        )

        nap.refresh_from_db()
        self.assertEqual(nap.ended_at, feeding_time)

    def test_diaper_ends_open_nap(self):
        nap_start = timezone.now() - timedelta(hours=2)
        nap = Nap.objects.create(child=self.child, napped_at=nap_start)

        diaper_time = timezone.now() - timedelta(hours=1)
        DiaperChange.objects.create(
            child=self.child,
            changed_at=diaper_time,
            change_type="wet",
        )

        nap.refresh_from_db()
        self.assertEqual(nap.ended_at, diaper_time)

    def test_new_nap_ends_old_open_nap(self):
        old_nap_start = timezone.now() - timedelta(hours=3)
        old_nap = Nap.objects.create(child=self.child, napped_at=old_nap_start)

        new_nap_start = timezone.now() - timedelta(hours=1)
        new_nap = Nap.objects.create(child=self.child, napped_at=new_nap_start)

        old_nap.refresh_from_db()
        self.assertEqual(old_nap.ended_at, new_nap_start)

        new_nap.refresh_from_db()
        self.assertIsNone(new_nap.ended_at)

    def test_does_not_end_nap_for_different_child(self):
        nap_start = timezone.now() - timedelta(hours=2)
        nap = Nap.objects.create(child=self.child, napped_at=nap_start)

        feeding_time = timezone.now() - timedelta(hours=1)
        Feeding.objects.create(
            child=self.other_child,
            fed_at=feeding_time,
            feeding_type="bottle",
            amount_oz=4.0,
        )

        nap.refresh_from_db()
        self.assertIsNone(nap.ended_at)

    def test_does_not_end_already_ended_nap(self):
        nap_start = timezone.now() - timedelta(hours=3)
        original_end = timezone.now() - timedelta(hours=2)
        nap = Nap.objects.create(
            child=self.child,
            napped_at=nap_start,
            ended_at=original_end,
        )

        feeding_time = timezone.now() - timedelta(hours=1)
        Feeding.objects.create(
            child=self.child,
            fed_at=feeding_time,
            feeding_type="bottle",
            amount_oz=4.0,
        )

        nap.refresh_from_db()
        self.assertEqual(nap.ended_at, original_end)

    def test_does_not_end_nap_started_after_activity(self):
        """A nap that started after the activity timestamp should not be ended."""
        feeding_time = timezone.now() - timedelta(hours=2)
        nap_start = timezone.now() - timedelta(hours=1)
        nap = Nap.objects.create(child=self.child, napped_at=nap_start)

        # Create feeding with timestamp before the nap started
        Feeding.objects.create(
            child=self.child,
            fed_at=feeding_time,
            feeding_type="bottle",
            amount_oz=4.0,
        )

        nap.refresh_from_db()
        self.assertIsNone(nap.ended_at)

    def test_update_does_not_trigger_auto_end(self):
        """Updating an existing feeding should not end open naps."""
        nap_start = timezone.now() - timedelta(hours=2)
        nap = Nap.objects.create(child=self.child, napped_at=nap_start)

        feeding_time = timezone.now() - timedelta(hours=3)
        feeding = Feeding.objects.create(
            child=self.child,
            fed_at=feeding_time,
            feeding_type="bottle",
            amount_oz=4.0,
        )

        # The nap started after the feeding, so it shouldn't be ended
        nap.refresh_from_db()
        self.assertIsNone(nap.ended_at)

        # Update the feeding (should not trigger auto-end since created=False)
        feeding.amount_oz = 6.0
        feeding.save()

        nap.refresh_from_db()
        self.assertIsNone(nap.ended_at)
