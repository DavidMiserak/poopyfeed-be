"""Comprehensive test suite for analytics endpoints.

Tests permission checking, data aggregation accuracy, caching behavior,
and error handling for all analytics endpoints.
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from children.models import Child, ChildShare
from diapers.models import DiaperChange
from feedings.models import Feeding
from naps.models import Nap

from .cache import invalidate_child_analytics
from .tasks import generate_pdf_report

User = get_user_model()


class AnalyticsPermissionTests(APITestCase):
    """Test permission checks for analytics endpoints."""

    @classmethod
    def setUpTestData(cls):
        """Create test users and children."""
        # Users
        cls.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="password123",
        )
        cls.coparent = User.objects.create_user(
            username="coparent",
            email="coparent@example.com",
            password="password123",
        )
        cls.caregiver = User.objects.create_user(
            username="caregiver",
            email="caregiver@example.com",
            password="password123",
        )
        cls.unauthorized = User.objects.create_user(
            username="unauthorized",
            email="unauthorized@example.com",
            password="password123",
        )

        # Child owned by owner
        cls.child = Child.objects.create(
            parent=cls.owner,
            name="Test Child",
            date_of_birth="2024-01-15",
        )

        # Share child with coparent and caregiver
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

    def test_feeding_trends_owner_access(self):
        """Owner should access feeding trends."""
        token = Token.objects.create(user=self.owner)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_feeding_trends_coparent_access(self):
        """Co-parent should access feeding trends."""
        token = Token.objects.create(user=self.coparent)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_feeding_trends_caregiver_access(self):
        """Caregiver should access feeding trends."""
        token = Token.objects.create(user=self.caregiver)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_feeding_trends_unauthorized_returns_404(self):
        """Unauthorized user should get 404."""
        token = Token.objects.create(user=self.unauthorized)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/"
        )

        # Should return 404, not 403
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_feeding_trends_unauthenticated_returns_401(self):
        """Unauthenticated user should get 401."""
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nonexistent_child_returns_404(self):
        """Request for nonexistent child should return 404."""
        token = Token.objects.create(user=self.owner)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.get(f"/api/v1/analytics/children/99999/feeding-trends/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class FeedingTrendsTests(APITestCase):
    """Test feeding trends endpoint."""

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="user@example.com",
            password="password123",
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name="Test Child",
            date_of_birth="2024-01-15",
        )

    def setUp(self):
        """Set up authentication for each test."""
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_feeding_trends_response_structure(self):
        """Response should have correct structure."""
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertIn("period", data)
        self.assertIn("child_id", data)
        self.assertIn("daily_data", data)
        self.assertIn("weekly_summary", data)
        self.assertIn("last_updated", data)

        self.assertEqual(data["child_id"], self.child.id)

    def test_feeding_trends_daily_data_has_correct_fields(self):
        """Daily data should have required fields."""
        # Create some feedings
        now = timezone.now()
        for i in range(3):
            Feeding.objects.create(
                child=self.child,
                feeding_type=Feeding.FeedingType.BOTTLE,
                fed_at=now - timedelta(days=i),
                amount_oz=8.0,
            )

        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertTrue(len(data["daily_data"]) > 0)
        for day_data in data["daily_data"]:
            self.assertIn("date", day_data)
            self.assertIn("count", day_data)
            self.assertIn("average_duration", day_data)
            self.assertIn("total_oz", day_data)

    def test_feeding_trends_aggregates_correctly(self):
        """Should correctly count feedings per day."""
        now = timezone.now()
        today = now.date()

        # Create 5 feedings today
        for i in range(5):
            Feeding.objects.create(
                child=self.child,
                feeding_type=Feeding.FeedingType.BOTTLE,
                fed_at=now.replace(hour=6 + i),
                amount_oz=8.0,
            )

        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/"
        )

        data = response.json()

        # Find today's data
        today_data = None
        for day_data in data["daily_data"]:
            if day_data["date"] == str(today):
                today_data = day_data
                break

        self.assertIsNotNone(today_data)
        self.assertEqual(today_data["count"], 5)

    def test_feeding_trends_days_parameter(self):
        """Should respect days parameter."""
        # Create feedings over 60 days
        now = timezone.now()
        for i in range(60):
            Feeding.objects.create(
                child=self.child,
                feeding_type=Feeding.FeedingType.BOTTLE,
                fed_at=now - timedelta(days=i),
                amount_oz=8.0,
            )

        # Request last 30 days
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/?days=30"
        )

        data = response.json()
        self.assertEqual(len(data["daily_data"]), 30)

        # Request last 60 days
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/?days=60"
        )

        data = response.json()
        self.assertEqual(len(data["daily_data"]), 60)

    def test_feeding_trends_invalid_days_parameter(self):
        """Should reject invalid days parameter."""
        # days > 90
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/?days=91"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # days < 1
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/?days=0"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_feeding_trends_fills_missing_dates(self):
        """Should fill missing dates with zero counts."""
        # Create one feeding today
        now = timezone.now()
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=now,
            amount_oz=8.0,
        )

        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/?days=30"
        )

        data = response.json()

        # Should have 30 days of data
        self.assertEqual(len(data["daily_data"]), 30)

        # Should have at least 1 feeding (today's)
        total = sum(d["count"] for d in data["daily_data"])
        self.assertGreaterEqual(total, 1)


class DiaperPatternsTests(APITestCase):
    """Test diaper patterns endpoint."""

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="user@example.com",
            password="password123",
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name="Test Child",
            date_of_birth="2024-01-15",
        )

    def setUp(self):
        """Set up authentication."""
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_diaper_patterns_response_structure(self):
        """Response should have correct structure."""
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/diaper-patterns/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertIn("period", data)
        self.assertIn("child_id", data)
        self.assertIn("daily_data", data)
        self.assertIn("weekly_summary", data)
        self.assertIn("breakdown", data)
        self.assertIn("last_updated", data)

        self.assertIn("wet", data["breakdown"])
        self.assertIn("dirty", data["breakdown"])
        self.assertIn("both", data["breakdown"])

    def test_diaper_patterns_breakdown_counts(self):
        """Should correctly count diaper types."""
        now = timezone.now()

        # Create diaper changes
        DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=now,
        )
        DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=now - timedelta(hours=1),
        )
        DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.DIRTY,
            changed_at=now - timedelta(hours=2),
        )
        DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.BOTH,
            changed_at=now - timedelta(hours=3),
        )

        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/diaper-patterns/"
        )

        data = response.json()

        self.assertEqual(data["breakdown"]["wet"], 2)
        self.assertEqual(data["breakdown"]["dirty"], 1)
        self.assertEqual(data["breakdown"]["both"], 1)


class SleepSummaryTests(APITestCase):
    """Test sleep summary endpoint."""

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="user@example.com",
            password="password123",
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name="Test Child",
            date_of_birth="2024-01-15",
        )

    def setUp(self):
        """Set up authentication."""
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_sleep_summary_response_structure(self):
        """Response should have correct structure."""
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/sleep-summary/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertIn("period", data)
        self.assertIn("child_id", data)
        self.assertIn("daily_data", data)
        self.assertIn("weekly_summary", data)
        self.assertIn("last_updated", data)

    def test_sleep_summary_aggregates_correctly(self):
        """Should correctly count naps."""
        now = timezone.now()

        # Create 3 naps today
        for i in range(3):
            Nap.objects.create(
                child=self.child,
                napped_at=now.replace(hour=6 + i * 4),
            )

        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/sleep-summary/"
        )

        data = response.json()
        today = now.date()

        today_data = None
        for day_data in data["daily_data"]:
            if day_data["date"] == str(today):
                today_data = day_data
                break

        self.assertIsNotNone(today_data)
        self.assertEqual(today_data["count"], 3)


class TodaySummaryTests(APITestCase):
    """Test today's summary endpoint."""

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="user@example.com",
            password="password123",
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name="Test Child",
            date_of_birth="2024-01-15",
        )

    def setUp(self):
        """Set up authentication."""
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_today_summary_response_structure(self):
        """Response should have correct structure."""
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/today-summary/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertIn("child_id", data)
        self.assertIn("period", data)
        self.assertIn("feedings", data)
        self.assertIn("diapers", data)
        self.assertIn("sleep", data)
        self.assertIn("last_updated", data)

        self.assertEqual(data["period"], "today")

    def test_today_summary_correct_counts(self):
        """Should return correct counts for today."""
        now = timezone.now()

        # Create activity
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=now,
            amount_oz=8.0,
        )
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BREAST,
            fed_at=now - timedelta(hours=1),
            duration_minutes=15,
            side=Feeding.BreastSide.LEFT,
        )
        DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=now - timedelta(hours=2),
        )
        Nap.objects.create(
            child=self.child,
            napped_at=now - timedelta(hours=3),
        )

        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/today-summary/"
        )

        data = response.json()

        self.assertEqual(data["feedings"]["count"], 2)
        self.assertEqual(data["feedings"]["bottle"], 1)
        self.assertEqual(data["feedings"]["breast"], 1)
        self.assertEqual(data["diapers"]["count"], 1)
        self.assertEqual(data["diapers"]["wet"], 1)
        self.assertEqual(data["sleep"]["naps"], 1)


class WeeklySummaryTests(APITestCase):
    """Test weekly summary endpoint."""

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="user@example.com",
            password="password123",
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name="Test Child",
            date_of_birth="2024-01-15",
        )

    def setUp(self):
        """Set up authentication."""
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_weekly_summary_response_structure(self):
        """Response should have correct structure."""
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/weekly-summary/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertIn("child_id", data)
        self.assertIn("period", data)
        self.assertIn("feedings", data)
        self.assertIn("diapers", data)
        self.assertIn("sleep", data)
        self.assertIn("last_updated", data)

    def test_weekly_summary_aggregates_week(self):
        """Should aggregate data from last 7 days."""
        now = timezone.now()

        # Create activity over 7 days
        for i in range(7):
            Feeding.objects.create(
                child=self.child,
                feeding_type=Feeding.FeedingType.BOTTLE,
                fed_at=now - timedelta(days=i),
                amount_oz=8.0,
            )

        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/weekly-summary/"
        )

        data = response.json()

        self.assertEqual(data["feedings"]["count"], 7)


class CachingTests(APITestCase):
    """Test caching behavior."""

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="user@example.com",
            password="password123",
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name="Test Child",
            date_of_birth="2024-01-15",
        )

    def setUp(self):
        """Set up authentication."""
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_cache_invalidation_on_feeding_create(self):
        """Cache should invalidate when feeding is created."""
        # Get trends (populates cache)
        response1 = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/"
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Create a feeding (should invalidate cache via signal)
        now = timezone.now()
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=now,
            amount_oz=8.0,
        )

        # Get trends again (should recalculate from fresh data)
        response2 = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/"
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        data2 = response2.json()

        # Should have new data
        self.assertGreater(sum(d["count"] for d in data2["daily_data"]), 0)

    def test_cache_invalidation_on_diaper_create(self):
        """Cache should invalidate when diaper change is created."""
        # Get patterns (populates cache)
        response1 = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/diaper-patterns/"
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        data1 = response1.json()
        initial_wet_count = data1["breakdown"]["wet"]

        # Create a diaper change (should invalidate cache via signal)
        now = timezone.now()
        DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=now,
        )

        # Get patterns again (should recalculate with fresh data)
        response2 = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/diaper-patterns/"
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        data2 = response2.json()

        # Should have recorded the diaper change
        self.assertEqual(data2["breakdown"]["wet"], initial_wet_count + 1)

    def test_cache_invalidation_on_nap_create(self):
        """Cache should invalidate when nap is created."""
        # Get sleep summary (populates cache)
        response1 = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/sleep-summary/"
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        data1 = response1.json()
        initial_total = sum(d["count"] for d in data1["daily_data"])

        # Create a nap (should invalidate cache via signal)
        now = timezone.now()
        Nap.objects.create(
            child=self.child,
            napped_at=now,
        )

        # Get sleep summary again (should recalculate with fresh data)
        response2 = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/sleep-summary/"
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        data2 = response2.json()

        # Should have recorded the nap
        total_after = sum(d["count"] for d in data2["daily_data"])
        self.assertEqual(total_after, initial_total + 1)


class EmptyDataTests(APITestCase):
    """Test endpoints with no data."""

    @classmethod
    def setUpTestData(cls):
        """Create test data without any tracking records."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="user@example.com",
            password="password123",
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name="Test Child",
            date_of_birth="2024-01-15",
        )

    def setUp(self):
        """Set up authentication."""
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_feeding_trends_empty_data(self):
        """Should handle empty feeding data gracefully."""
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/feeding-trends/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should have 30 days with zero counts
        self.assertEqual(len(data["daily_data"]), 30)
        self.assertEqual(sum(d["count"] for d in data["daily_data"]), 0)
        self.assertEqual(data["weekly_summary"]["avg_per_day"], 0.0)

    def test_diaper_patterns_empty_data(self):
        """Should handle empty diaper data gracefully."""
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/diaper-patterns/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(sum(d["count"] for d in data["daily_data"]), 0)
        self.assertEqual(data["breakdown"]["wet"], 0)
        self.assertEqual(data["breakdown"]["dirty"], 0)
        self.assertEqual(data["breakdown"]["both"], 0)

    def test_today_summary_empty_data(self):
        """Should handle empty today data gracefully."""
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/today-summary/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["feedings"]["count"], 0)
        self.assertEqual(data["diapers"]["count"], 0)
        self.assertEqual(data["sleep"]["naps"], 0)


class ExportCSVTests(APITestCase):
    """Test CSV export endpoint."""

    @classmethod
    def setUpTestData(cls):
        """Create test data with tracking records."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="user@example.com",
            password="password123",
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name="Test Child",
            date_of_birth="2024-01-15",
        )

        # Create some test data
        now = timezone.now()
        for i in range(5):
            date_offset = now - timedelta(days=i)
            Feeding.objects.create(
                child=cls.child,
                fed_at=date_offset,
                amount_oz=5.0 + i,
                feeding_type="bottle",
            )
            DiaperChange.objects.create(
                child=cls.child,
                changed_at=date_offset,
                change_type="wet",
            )
            Nap.objects.create(
                child=cls.child,
                napped_at=date_offset,
            )

    def setUp(self):
        """Set up authentication."""
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_csv_export_success(self):
        """Should successfully export data as CSV."""
        response = self.client.post(
            f"/api/v1/analytics/children/{self.child.id}/export-csv/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("analytics-Test_Child", response["Content-Disposition"])

        # Parse CSV content
        csv_lines = response.content.decode().strip().split("\n")
        self.assertGreater(len(csv_lines), 1)  # Should have header + data rows

        # Check header
        header = csv_lines[0]
        self.assertIn("Date", header)
        self.assertIn("Feedings (count)", header)
        self.assertIn("Diaper Changes (count)", header)

    def test_csv_export_with_days_parameter(self):
        """Should respect days parameter in CSV export."""
        response = self.client.post(
            f"/api/v1/analytics/children/{self.child.id}/export-csv/?days=7"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        csv_lines = response.content.decode().strip().split("\n")

        # Should have 7 days of data + 1 header row
        self.assertLessEqual(len(csv_lines), 8)

    def test_csv_export_unauthorized(self):
        """Should deny CSV export to unauthorized users."""
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="password123",
        )
        token = Token.objects.create(user=other_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.post(
            f"/api/v1/analytics/children/{self.child.id}/export-csv/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_csv_export_coparent(self):
        """Should allow CSV export to co-parent."""
        coparent = User.objects.create_user(
            username="coparent",
            email="coparent@example.com",
            password="password123",
        )
        ChildShare.objects.create(
            child=self.child,
            user=coparent,
            role="CO",
        )

        token = Token.objects.create(user=coparent)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.post(
            f"/api/v1/analytics/children/{self.child.id}/export-csv/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_csv_export_invalid_days(self):
        """Should reject invalid days parameter."""
        response = self.client.post(
            f"/api/v1/analytics/children/{self.child.id}/export-csv/?days=100"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ExportPDFTests(APITestCase):
    """Test PDF export endpoints."""

    @classmethod
    def setUpTestData(cls):
        """Create test data with tracking records."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="user@example.com",
            password="password123",
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name="Test Child",
            date_of_birth="2024-01-15",
        )

        # Create some test data
        now = timezone.now()
        for i in range(5):
            date_offset = now - timedelta(days=i)
            Feeding.objects.create(
                child=cls.child,
                fed_at=date_offset,
                amount_oz=5.0 + i,
                feeding_type="bottle",
            )

    def setUp(self):
        """Set up authentication."""
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_pdf_export_queues_task(self):
        """Should queue PDF export task and return task ID."""
        response = self.client.post(
            f"/api/v1/analytics/children/{self.child.id}/export-pdf/"
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        data = response.json()

        self.assertIn("task_id", data)
        self.assertEqual(data["status"], "pending")
        self.assertIn("PDF export", data["message"])

    def test_pdf_export_unauthorized(self):
        """Should deny PDF export to unauthorized users."""
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="password123",
        )
        token = Token.objects.create(user=other_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.post(
            f"/api/v1/analytics/children/{self.child.id}/export-pdf/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_export_status_pending(self):
        """Should return task status for pending job."""
        # Queue task
        response = self.client.post(
            f"/api/v1/analytics/children/{self.child.id}/export-pdf/"
        )
        task_id = response.json()["task_id"]

        # Poll status
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/export-status/{task_id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["task_id"], task_id)
        # Status can be 'PENDING' or any other Celery status

    def test_export_status_returns_task_info(self):
        """Should return task information for valid task ID."""
        # Queue task
        response = self.client.post(
            f"/api/v1/analytics/children/{self.child.id}/export-pdf/"
        )
        task_id = response.json()["task_id"]

        # Get status multiple times
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/export-status/{task_id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["task_id"], task_id)
        self.assertIn("status", data)

    def test_export_status_always_includes_progress(self):
        """Should always include progress field in export status response."""
        # Queue task
        response = self.client.post(
            f"/api/v1/analytics/children/{self.child.id}/export-pdf/"
        )
        task_id = response.json()["task_id"]

        # Poll status immediately (task will be PENDING)
        response = self.client.get(
            f"/api/v1/analytics/children/{self.child.id}/export-status/{task_id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Progress field MUST be present for frontend display
        self.assertIn("progress", data, "Progress field must be present in export status response")

        # Progress should be a number between 0-100
        progress = data["progress"]
        self.assertIsInstance(progress, int, "Progress must be an integer")
        self.assertGreaterEqual(progress, 0, "Progress cannot be negative")
        self.assertLessEqual(progress, 100, "Progress cannot exceed 100")


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class GeneratePDFReportTaskTests(TestCase):
    """Test the generate_pdf_report Celery task renders correct table data."""

    @classmethod
    def setUpTestData(cls):
        """Create user and child for PDF generation."""
        cls.user = User.objects.create_user(
            username="pdftestuser",
            email="pdftest@example.com",
            password="password123",
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name="PDF Baby",
            date_of_birth="2024-06-15",
        )

    @staticmethod
    def _make_feeding_data(num_days):
        """Build mock feeding trend data."""
        start = date(2024, 1, 1)
        daily_data = [
            {
                "date": start + timedelta(days=i),
                "count": i % 5,
                "average_duration": 15.0 if i % 3 == 0 else None,
                "total_oz": 8.0 if i % 2 == 0 else None,
            }
            for i in range(num_days)
        ]
        return {
            "daily_data": daily_data,
            "weekly_summary": {"avg_per_day": 3.5, "trend": "stable", "variance": 1.2},
        }

    @staticmethod
    def _make_diaper_data(num_days):
        """Build mock diaper data with None values on gap-filled days."""
        start = date(2024, 1, 1)
        daily_data = []
        for i in range(num_days):
            if i % 5 == 0:
                daily_data.append(
                    {
                        "date": start + timedelta(days=i),
                        "count": 3,
                        "wet_count": 1,
                        "dirty_count": 1,
                        "both_count": 1,
                    }
                )
            else:
                # Mirrors _fill_date_gaps: keys exist with None values
                daily_data.append(
                    {
                        "date": start + timedelta(days=i),
                        "count": 0,
                        "wet_count": None,
                        "dirty_count": None,
                        "both_count": None,
                    }
                )
        return {
            "daily_data": daily_data,
            "breakdown": {"wet": 6, "dirty": 6, "both": 6},
            "weekly_summary": {"avg_per_day": 2.0, "trend": "stable", "variance": 0.5},
        }

    @staticmethod
    def _make_sleep_data(num_days):
        """Build mock sleep summary data."""
        start = date(2024, 1, 1)
        daily_data = [
            {
                "date": start + timedelta(days=i),
                "count": i % 3,
                "average_duration": 45.0 if i % 4 == 0 else None,
                "total_minutes": 90.0 if i % 4 == 0 else None,
            }
            for i in range(num_days)
        ]
        return {
            "daily_data": daily_data,
            "weekly_summary": {"avg_per_day": 2.0, "trend": "increasing"},
        }

    def _run_task_with_mocks(self, num_days):
        """Run generate_pdf_report with mocked analytics utils and ReportLab.

        Returns the list of calls to the Table constructor so tests can
        inspect the row data passed for each section.
        """
        with (
            patch("analytics.tasks.get_feeding_trends") as mock_feed,
            patch("analytics.tasks.get_diaper_patterns") as mock_diaper,
            patch("analytics.tasks.get_sleep_summary") as mock_sleep,
            patch("analytics.tasks.Table") as MockTable,
            patch("analytics.tasks.SimpleDocTemplate") as MockDoc,
            patch("analytics.tasks.default_storage"),
        ):
            mock_feed.return_value = self._make_feeding_data(num_days)
            mock_diaper.return_value = self._make_diaper_data(num_days)
            mock_sleep.return_value = self._make_sleep_data(num_days)
            MockDoc.return_value = MagicMock()

            generate_pdf_report.delay(self.child.id, self.user.id, num_days)

            return MockTable.call_args_list

    # ------------------------------------------------------------------
    # Truncation tests ([:10] removal)
    # ------------------------------------------------------------------

    def test_feeding_table_includes_all_days(self):
        """Feeding table must contain every day, not just the first 10."""
        table_calls = self._run_task_with_mocks(30)
        feeding_rows = table_calls[0][0][0]  # first Table() call, positional arg
        # 1 header row + 30 data rows
        self.assertEqual(len(feeding_rows), 31)

    def test_diaper_table_includes_all_days(self):
        """Diaper table must contain every day, not just the first 10."""
        table_calls = self._run_task_with_mocks(30)
        diaper_rows = table_calls[1][0][0]
        self.assertEqual(len(diaper_rows), 31)

    def test_sleep_table_includes_all_days(self):
        """Sleep table must contain every day, not just the first 10."""
        table_calls = self._run_task_with_mocks(30)
        sleep_rows = table_calls[2][0][0]
        self.assertEqual(len(sleep_rows), 31)

    def test_tables_include_all_days_for_short_range(self):
        """Even short ranges (< 10 days) should render every day."""
        table_calls = self._run_task_with_mocks(7)
        for idx, name in enumerate(["feeding", "diaper", "sleep"]):
            rows = table_calls[idx][0][0]
            self.assertEqual(
                len(rows), 8, f"{name} table should have 8 rows (1 header + 7 data)"
            )

    def test_tables_include_all_days_for_max_range(self):
        """90-day export should render all 90 data rows per table."""
        table_calls = self._run_task_with_mocks(90)
        for idx, name in enumerate(["feeding", "diaper", "sleep"]):
            rows = table_calls[idx][0][0]
            self.assertEqual(
                len(rows), 91, f"{name} table should have 91 rows (1 header + 90 data)"
            )

    # ------------------------------------------------------------------
    # None-coalescing tests (diaper "None" → "0")
    # ------------------------------------------------------------------

    def test_diaper_none_values_rendered_as_zero(self):
        """Gap-filled diaper rows must show '0', never 'None'."""
        table_calls = self._run_task_with_mocks(10)
        diaper_rows = table_calls[1][0][0]

        for row_idx, row in enumerate(diaper_rows[1:], start=1):
            wet, dirty, both = row[2], row[3], row[4]
            self.assertNotEqual(
                wet, "None", f"Row {row_idx}: wet_count is literal 'None'"
            )
            self.assertNotEqual(
                dirty, "None", f"Row {row_idx}: dirty_count is literal 'None'"
            )
            self.assertNotEqual(
                both, "None", f"Row {row_idx}: both_count is literal 'None'"
            )

    def test_diaper_gap_filled_rows_show_zero(self):
        """Days with no diaper data (None from _fill_date_gaps) should be '0'."""
        table_calls = self._run_task_with_mocks(10)
        diaper_rows = table_calls[1][0][0]

        # In our mock, rows at index 1,2,3,4 (day offsets 1-4) are gap-filled
        for gap_row_idx in [2, 3, 4, 5]:  # +1 for header offset
            row = diaper_rows[gap_row_idx]
            self.assertEqual(row[2], "0", f"Gap row {gap_row_idx}: wet should be '0'")
            self.assertEqual(row[3], "0", f"Gap row {gap_row_idx}: dirty should be '0'")
            self.assertEqual(row[4], "0", f"Gap row {gap_row_idx}: both should be '0'")

    def test_diaper_rows_with_data_show_actual_counts(self):
        """Days with actual diaper data should show real counts."""
        table_calls = self._run_task_with_mocks(10)
        diaper_rows = table_calls[1][0][0]

        # Day offset 0 and 5 have real data (count=3, wet=1, dirty=1, both=1)
        for data_row_idx in [1, 6]:  # +1 for header offset
            row = diaper_rows[data_row_idx]
            self.assertEqual(row[1], "3", f"Row {data_row_idx}: total count should be '3'")
            self.assertEqual(row[2], "1", f"Row {data_row_idx}: wet should be '1'")
            self.assertEqual(row[3], "1", f"Row {data_row_idx}: dirty should be '1'")
            self.assertEqual(row[4], "1", f"Row {data_row_idx}: both should be '1'")
