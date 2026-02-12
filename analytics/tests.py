"""Comprehensive test suite for analytics endpoints.

Tests permission checking, data aggregation accuracy, caching behavior,
and error handling for all analytics endpoints.
"""

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from children.models import Child, ChildShare
from diapers.models import DiaperChange
from feedings.models import Feeding
from naps.models import Nap

from .cache import invalidate_child_analytics

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
