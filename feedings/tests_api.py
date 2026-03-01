"""API tests for feedings app."""

from django.utils import timezone
from rest_framework import status

from children.tests_tracking_base import BaseTrackingAPITests

from .models import Feeding

TEST_DATETIME = "2025-01-15T10:00:00Z"


class FeedingAPITests(BaseTrackingAPITests):
    """Tests for Feeding API endpoints."""

    model = Feeding
    app_name = "feedings"

    def get_create_data(self):
        """Return data for creating a bottle feeding."""
        return {
            "feeding_type": "bottle",
            "fed_at": TEST_DATETIME,
            "amount_oz": "4.5",
        }

    def create_test_record(self):
        """Create and return a test feeding."""
        return Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=TEST_DATETIME,
            amount_oz=4,
        )

    # Feedings-specific validation tests
    def test_get_update_data_returns_create_data(self):
        """Base get_update_data() returns get_create_data() when not overridden."""
        self.assertEqual(self.get_update_data(), self.get_create_data())

    def test_base_get_create_data_raises_not_implemented(self):
        """Base get_create_data() raises NotImplementedError when called on base."""
        with self.assertRaises(NotImplementedError) as ctx:
            BaseTrackingAPITests.get_create_data(self)
        self.assertIn("get_create_data", str(ctx.exception))

    def test_base_create_test_record_raises_not_implemented(self):
        """Base create_test_record() raises NotImplementedError when called on base."""
        with self.assertRaises(NotImplementedError) as ctx:
            BaseTrackingAPITests.create_test_record(self)
        self.assertIn("create_test_record", str(ctx.exception))

    def test_create_bottle_feeding(self):
        """Can create bottle feeding with amount."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.post(self.get_list_url(), self.get_create_data())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["feeding_type"], "bottle")
        self.assertEqual(response.data["amount_oz"], "4.5")

    def test_create_bottle_feeding_missing_amount(self):
        """Bottle feeding requires amount."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {"feeding_type": "bottle", "fed_at": TEST_DATETIME}
        response = self.client.post(self.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount_oz", response.data)

    def test_create_breast_feeding(self):
        """Can create breast feeding with duration and side."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {
            "feeding_type": "breast",
            "fed_at": "2025-01-15T12:00:00Z",
            "duration_minutes": 15,
            "side": "left",
        }
        response = self.client.post(self.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["feeding_type"], "breast")
        self.assertEqual(response.data["duration_minutes"], 15)
        self.assertEqual(response.data["side"], "left")

    def test_create_breast_feeding_missing_duration(self):
        """Breast feeding requires duration."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {
            "feeding_type": "breast",
            "fed_at": "2025-01-15T14:00:00Z",
            "side": "right",
        }
        response = self.client.post(self.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("duration_minutes", response.data)

    def test_create_breast_feeding_missing_side(self):
        """Breast feeding requires side."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {
            "feeding_type": "breast",
            "fed_at": "2025-01-15T16:00:00Z",
            "duration_minutes": 10,
        }
        response = self.client.post(self.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("side", response.data)

    def test_list_feedings(self):
        """Can list feedings."""
        self.create_test_record()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(self.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_list_feedings_filtered_by_date_range(self):
        """Date range filters exclude feedings outside the window."""
        now = timezone.now()
        two_hours_ago = now - timezone.timedelta(hours=2)
        five_hours_ago = now - timezone.timedelta(hours=5)
        four_hours_ago = now - timezone.timedelta(hours=4)

        # Create one feeding within 4h window
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=two_hours_ago,
            amount_oz=4,
        )
        # Create one feeding outside 4h window
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=five_hours_ago,
            amount_oz=3,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(
            self.get_list_url(),
            {
                "fed_at__gte": four_hours_ago.isoformat(),
                "fed_at__lt": now.isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["amount_oz"], "4.0")

    def test_list_feedings_no_filter_returns_all(self):
        """Without date filters, all feedings are returned."""
        now = timezone.now()
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=now - timezone.timedelta(hours=2),
            amount_oz=4,
        )
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=now - timezone.timedelta(hours=25),
            amount_oz=3,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(self.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_pagination_applied(self):
        """Verify pagination is applied to list endpoints (PAGE_SIZE=50)."""
        for _ in range(60):
            Feeding.objects.create(
                child=self.child,
                feeding_type=Feeding.FeedingType.BOTTLE,
                fed_at=TEST_DATETIME,
                amount_oz=4,
            )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(self.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertEqual(len(response.data["results"]), 50)
        self.assertEqual(response.data["count"], 60)
        self.assertIsNotNone(response.data["next"])
        self.assertIsNone(response.data["previous"])

        response_page2 = self.client.get(response.data["next"])
        self.assertEqual(len(response_page2.data["results"]), 10)
        self.assertIsNone(response_page2.data["next"])
        self.assertIsNotNone(response_page2.data["previous"])
