"""API tests for naps app."""

from rest_framework import status

from children.tests_tracking_base import BaseTrackingAPITests

from .models import Nap


class NapAPITests(BaseTrackingAPITests):
    """Tests for Nap API endpoints."""

    model = Nap
    app_name = "naps"

    def get_create_data(self):
        """Return data for creating a nap."""
        return {"napped_at": "2025-01-15T17:00:00Z"}

    def create_test_record(self):
        """Create and return a test nap."""
        return Nap.objects.create(
            child=self.child,
            napped_at="2025-01-15T13:00:00Z",
        )

    # Naps-specific tests
    def test_list_naps(self):
        """Can list naps."""
        Nap.objects.create(child=self.child, napped_at="2025-01-15T13:00:00Z")
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
            {"napped_at": "2025-01-15T14:00:00Z"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
