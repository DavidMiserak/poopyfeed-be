"""API tests for naps app."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from children.models import Child, ChildShare

from .models import Nap


class NapAPITests(APITestCase):
    """Tests for Nap API endpoints."""

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="testpass123",
        )
        cls.caregiver = user_model.objects.create_user(
            username="caregiver",
            email="caregiver@example.com",
            password="testpass123",
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name="Test Baby",
            date_of_birth="2025-01-01",
        )
        ChildShare.objects.create(
            child=cls.child,
            user=cls.caregiver,
            role=ChildShare.Role.CAREGIVER,
            created_by=cls.owner,
        )
        cls.nap = Nap.objects.create(
            child=cls.child,
            napped_at="2025-01-15T13:00:00Z",
        )

    def setUp(self):
        self.owner_token = Token.objects.create(user=self.owner)
        self.caregiver_token = Token.objects.create(user=self.caregiver)

    def test_list_naps(self):
        """Can list naps."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(f"/api/v1/children/{self.child.pk}/naps/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_create_nap(self):
        """Can create nap."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {"napped_at": "2025-01-15T15:00:00Z"}
        response = self.client.post(f"/api/v1/children/{self.child.pk}/naps/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_caregiver_can_create(self):
        """Caregiver can create naps."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        data = {"napped_at": "2025-01-15T17:00:00Z"}
        response = self.client.post(f"/api/v1/children/{self.child.pk}/naps/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_caregiver_cannot_delete(self):
        """Caregiver cannot delete naps."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        response = self.client.delete(
            f"/api/v1/children/{self.child.pk}/naps/{self.nap.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_delete(self):
        """Owner can delete naps."""
        nap = Nap.objects.create(
            child=self.child,
            napped_at="2025-01-15T19:00:00Z",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.delete(
            f"/api/v1/children/{self.child.pk}/naps/{nap.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_owner_can_update(self):
        """Owner can update naps."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.put(
            f"/api/v1/children/{self.child.pk}/naps/{self.nap.pk}/",
            {"napped_at": "2025-01-15T14:00:00Z"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_caregiver_cannot_update(self):
        """Caregiver cannot update naps."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        response = self.client.put(
            f"/api/v1/children/{self.child.pk}/naps/{self.nap.pk}/",
            {"napped_at": "2025-01-15T14:00:00Z"},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_partial_update_nap(self):
        """Owner can partial update nap."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.patch(
            f"/api/v1/children/{self.child.pk}/naps/{self.nap.pk}/",
            {"napped_at": "2025-01-15T14:30:00Z"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_nap(self):
        """Can retrieve single nap."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(
            f"/api/v1/children/{self.child.pk}/naps/{self.nap.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_nonexistent_child_returns_empty(self):
        """Accessing naps for nonexistent child returns empty list."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get("/api/v1/children/99999/naps/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_stranger_cannot_create(self):
        """Stranger cannot create naps."""
        user_model = get_user_model()
        stranger = user_model.objects.create_user(
            username="stranger",
            email="stranger@example.com",
            password="testpass123",
        )
        stranger_token = Token.objects.create(user=stranger)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {stranger_token.key}")
        response = self.client.post(
            f"/api/v1/children/{self.child.pk}/naps/",
            {"napped_at": "2025-01-15T21:00:00Z"},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
