"""API tests for naps app."""

from datetime import datetime

from django.utils import timezone
from rest_framework import status

from children.tests_tracking_base import BaseTrackingAPITests

from .models import Nap

# Test data constants for API calls (ISO format strings)
TEST_NAPPED_AT_STR = "2025-01-15T13:00:00Z"
TEST_NAPPED_AT_ALT_STR = "2025-01-15T14:00:00Z"
TEST_NAPPED_AT_CREATE_STR = "2025-01-15T17:00:00Z"
TEST_ENDED_AT_STR = "2025-01-15T14:30:00Z"

# Test data constants for model creation (timezone-aware datetimes)
TEST_NAPPED_AT = timezone.make_aware(datetime(2025, 1, 15, 13, 0, 0))
TEST_NAPPED_AT_ALT = timezone.make_aware(datetime(2025, 1, 15, 14, 0, 0))
TEST_ENDED_AT = timezone.make_aware(datetime(2025, 1, 15, 14, 30, 0))


class NapAPITests(BaseTrackingAPITests):
    """Tests for Nap API endpoints."""

    model = Nap
    app_name = "naps"

    def get_create_data(self):
        """Return data for creating a nap."""
        return {"napped_at": TEST_NAPPED_AT_CREATE_STR}

    def create_test_record(self):
        """Create and return a test nap."""
        return Nap.objects.create(
            child=self.child,
            napped_at=TEST_NAPPED_AT,
        )

    # Naps-specific tests
    def test_list_naps(self):
        """Can list naps."""
        Nap.objects.create(
            child=self.child,
            napped_at=TEST_NAPPED_AT,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(self.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_create_nap(self):
        """Owner can create nap."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.post(self.get_list_url(), self.get_create_data())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_owner_can_update(self):
        """Owner can update naps."""
        nap = self.create_test_record()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.put(
            self.get_detail_url(nap.pk),
            {"napped_at": TEST_NAPPED_AT_ALT_STR},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_nap_with_ended_at(self):
        """Can create nap with ended_at."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.post(
            self.get_list_url(),
            {
                "napped_at": TEST_NAPPED_AT_STR,
                "ended_at": TEST_ENDED_AT_STR,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["ended_at"], "2025-01-15T14:30:00Z")
        self.assertAlmostEqual(response.data["duration_minutes"], 90.0)

    def test_create_nap_without_ended_at(self):
        """Can create nap without ended_at (ongoing nap)."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.post(
            self.get_list_url(),
            {"napped_at": TEST_NAPPED_AT_STR},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["ended_at"])
        self.assertIsNone(response.data["duration_minutes"])

    def test_ended_at_before_napped_at_rejected(self):
        """Ended_at before napped_at is rejected."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.post(
            self.get_list_url(),
            {
                "napped_at": TEST_NAPPED_AT_ALT_STR,
                "ended_at": TEST_NAPPED_AT_STR,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_includes_ended_at_and_duration(self):
        """List response includes ended_at and duration_minutes."""
        Nap.objects.create(
            child=self.child,
            napped_at=TEST_NAPPED_AT,
            ended_at=TEST_ENDED_AT,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(self.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nap_data = response.data["results"][0]
        self.assertIn("ended_at", nap_data)
        self.assertIn("duration_minutes", nap_data)
        self.assertAlmostEqual(nap_data["duration_minutes"], 90.0)

    def test_pagination_applied(self):
        """Verify pagination is applied to list endpoints (PAGE_SIZE=50)."""
        for _ in range(60):
            Nap.objects.create(
                child=self.child,
                napped_at=TEST_NAPPED_AT,
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
