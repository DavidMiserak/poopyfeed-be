"""API tests for diapers app."""

from rest_framework import status

from children.tests_tracking_base import BaseTrackingAPITests

from .models import DiaperChange

TEST_DATETIME = "2025-01-15T10:00:00Z"


class DiaperChangeAPITests(BaseTrackingAPITests):
    """Tests for DiaperChange API endpoints."""

    model = DiaperChange
    app_name = "diapers"

    def get_create_data(self):
        """Return data for creating a diaper change."""
        return {
            "change_type": "wet",
            "changed_at": TEST_DATETIME,
        }

    def create_test_record(self):
        """Create and return a test diaper change."""
        return DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=TEST_DATETIME,
        )

    # Diapers-specific tests
    def test_list_diapers_owner(self):
        """Owner can list diaper changes."""
        self.create_test_record()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(self.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["change_type"], "wet")

    def test_list_diapers_caregiver(self):
        """Caregiver can list diaper changes."""
        self.create_test_record()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        response = self.client.get(self.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_list_diapers_stranger_denied(self):
        """Stranger cannot list diaper changes."""
        self.create_test_record()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        response = self.client.get(self.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_create_diaper_owner(self):
        """Owner can create diaper change."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {"change_type": "dirty", "changed_at": "2025-01-15T12:00:00Z"}
        response = self.client.post(self.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["change_type"], "dirty")

    def test_update_diaper_owner(self):
        """Owner can update diaper change."""
        diaper = self.create_test_record()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {"change_type": "both", "changed_at": TEST_DATETIME}
        response = self.client.put(self.get_detail_url(diaper.pk), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["change_type"], "both")

    def test_update_diaper_coparent(self):
        """Co-parent can update diaper change."""
        diaper = self.create_test_record()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        data = {"change_type": "dirty", "changed_at": TEST_DATETIME}
        response = self.client.put(self.get_detail_url(diaper.pk), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_nonexistent_diaper(self):
        """Updating nonexistent diaper returns 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {"change_type": "wet", "changed_at": TEST_DATETIME}
        response = self.client.put(
            f"/api/v1/children/{self.child.pk}/diapers/99999/", data
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
