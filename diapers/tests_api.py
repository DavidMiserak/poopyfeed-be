"""API tests for diapers app."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from children.models import Child, ChildShare

from .models import DiaperChange

TEST_DATETIME = "2025-01-15T10:00:00Z"


class DiaperChangeAPITests(APITestCase):
    """Tests for DiaperChange API endpoints."""

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="testpass123",
        )
        cls.coparent = user_model.objects.create_user(
            username="coparent",
            email="coparent@example.com",
            password="testpass123",
        )
        cls.caregiver = user_model.objects.create_user(
            username="caregiver",
            email="caregiver@example.com",
            password="testpass123",
        )
        cls.stranger = user_model.objects.create_user(
            username="stranger",
            email="stranger@example.com",
            password="testpass123",
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name="Test Baby",
            date_of_birth="2025-01-01",
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
        cls.diaper = DiaperChange.objects.create(
            child=cls.child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=TEST_DATETIME,
        )

    def setUp(self):
        self.owner_token = Token.objects.create(user=self.owner)
        self.coparent_token = Token.objects.create(user=self.coparent)
        self.caregiver_token = Token.objects.create(user=self.caregiver)
        self.stranger_token = Token.objects.create(user=self.stranger)

    def test_list_diapers_owner(self):
        """Owner can list diaper changes."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(f"/api/v1/children/{self.child.pk}/diapers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["change_type"], "wet")

    def test_list_diapers_caregiver(self):
        """Caregiver can list diaper changes."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        response = self.client.get(f"/api/v1/children/{self.child.pk}/diapers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_list_diapers_stranger_denied(self):
        """Stranger cannot list diaper changes."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        response = self.client.get(f"/api/v1/children/{self.child.pk}/diapers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_create_diaper_owner(self):
        """Owner can create diaper change."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {
            "change_type": "dirty",
            "changed_at": "2025-01-15T12:00:00Z",
        }
        response = self.client.post(f"/api/v1/children/{self.child.pk}/diapers/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["change_type"], "dirty")

    def test_create_diaper_caregiver(self):
        """Caregiver can create diaper change."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        data = {
            "change_type": "both",
            "changed_at": "2025-01-15T14:00:00Z",
        }
        response = self.client.post(f"/api/v1/children/{self.child.pk}/diapers/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_diaper_stranger_denied(self):
        """Stranger cannot create diaper change."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        data = {
            "change_type": "wet",
            "changed_at": "2025-01-15T16:00:00Z",
        }
        response = self.client.post(f"/api/v1/children/{self.child.pk}/diapers/", data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_diaper_owner(self):
        """Owner can update diaper change."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {
            "change_type": "both",
            "changed_at": TEST_DATETIME,
        }
        response = self.client.put(
            f"/api/v1/children/{self.child.pk}/diapers/{self.diaper.pk}/", data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["change_type"], "both")

    def test_update_diaper_coparent(self):
        """Co-parent can update diaper change."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        data = {
            "change_type": "dirty",
            "changed_at": TEST_DATETIME,
        }
        response = self.client.put(
            f"/api/v1/children/{self.child.pk}/diapers/{self.diaper.pk}/", data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_diaper_caregiver_denied(self):
        """Caregiver cannot update diaper change."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        data = {
            "change_type": "dirty",
            "changed_at": TEST_DATETIME,
        }
        response = self.client.put(
            f"/api/v1/children/{self.child.pk}/diapers/{self.diaper.pk}/", data
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_diaper_owner(self):
        """Owner can delete diaper change."""
        diaper = DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at="2025-01-15T18:00:00Z",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.delete(
            f"/api/v1/children/{self.child.pk}/diapers/{diaper.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_diaper_caregiver_denied(self):
        """Caregiver cannot delete diaper change."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        response = self.client.delete(
            f"/api/v1/children/{self.child.pk}/diapers/{self.diaper.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_partial_update_diaper(self):
        """Owner can partial update diaper change."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.patch(
            f"/api/v1/children/{self.child.pk}/diapers/{self.diaper.pk}/",
            {"change_type": "dirty"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["change_type"], "dirty")

    def test_retrieve_diaper(self):
        """Can retrieve single diaper change."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(
            f"/api/v1/children/{self.child.pk}/diapers/{self.diaper.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["change_type"], "wet")

    def test_nonexistent_child_returns_empty(self):
        """Accessing diapers for nonexistent child returns empty list."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get("/api/v1/children/99999/diapers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_update_nonexistent_diaper(self):
        """Updating nonexistent diaper returns 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.put(
            f"/api/v1/children/{self.child.pk}/diapers/99999/",
            {"change_type": "wet", "changed_at": TEST_DATETIME},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
