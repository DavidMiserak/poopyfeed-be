"""API tests for feedings app."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from children.models import Child, ChildShare

from .models import Feeding


class FeedingAPITests(APITestCase):
    """Tests for Feeding API endpoints."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="testpass123",
        )
        cls.caregiver = User.objects.create_user(
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

    def setUp(self):
        self.owner_token = Token.objects.create(user=self.owner)
        self.caregiver_token = Token.objects.create(user=self.caregiver)

    def test_create_bottle_feeding(self):
        """Can create bottle feeding with amount."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {
            "feeding_type": "bottle",
            "fed_at": "2025-01-15T10:00:00Z",
            "amount_oz": "4.5",
        }
        response = self.client.post(f"/api/v1/children/{self.child.pk}/feedings/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["feeding_type"], "bottle")
        self.assertEqual(response.data["amount_oz"], "4.5")

    def test_create_bottle_feeding_missing_amount(self):
        """Bottle feeding requires amount."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {
            "feeding_type": "bottle",
            "fed_at": "2025-01-15T10:00:00Z",
        }
        response = self.client.post(f"/api/v1/children/{self.child.pk}/feedings/", data)
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
        response = self.client.post(f"/api/v1/children/{self.child.pk}/feedings/", data)
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
        response = self.client.post(f"/api/v1/children/{self.child.pk}/feedings/", data)
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
        response = self.client.post(f"/api/v1/children/{self.child.pk}/feedings/", data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("side", response.data)

    def test_list_feedings(self):
        """Can list feedings."""
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at="2025-01-15T10:00:00Z",
            amount_oz=4,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(f"/api/v1/children/{self.child.pk}/feedings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_caregiver_can_create(self):
        """Caregiver can create feedings."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        data = {
            "feeding_type": "bottle",
            "fed_at": "2025-01-15T18:00:00Z",
            "amount_oz": "3.0",
        }
        response = self.client.post(f"/api/v1/children/{self.child.pk}/feedings/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_caregiver_cannot_update(self):
        """Caregiver cannot update feedings."""
        feeding = Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at="2025-01-15T20:00:00Z",
            amount_oz=4,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        data = {
            "feeding_type": "bottle",
            "fed_at": "2025-01-15T20:00:00Z",
            "amount_oz": "5.0",
        }
        response = self.client.put(
            f"/api/v1/children/{self.child.pk}/feedings/{feeding.pk}/", data
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_caregiver_cannot_delete(self):
        """Caregiver cannot delete feedings."""
        feeding = Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at="2025-01-15T22:00:00Z",
            amount_oz=4,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        response = self.client.delete(
            f"/api/v1/children/{self.child.pk}/feedings/{feeding.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_delete(self):
        """Owner can delete feedings."""
        feeding = Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at="2025-01-16T08:00:00Z",
            amount_oz=4,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.delete(
            f"/api/v1/children/{self.child.pk}/feedings/{feeding.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_partial_update_feeding(self):
        """Owner can partial update feeding."""
        feeding = Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at="2025-01-16T10:00:00Z",
            amount_oz=4,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.patch(
            f"/api/v1/children/{self.child.pk}/feedings/{feeding.pk}/",
            {"amount_oz": "5.5"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["amount_oz"], "5.5")

    def test_retrieve_feeding(self):
        """Can retrieve single feeding."""
        feeding = Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at="2025-01-16T12:00:00Z",
            amount_oz=4,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(
            f"/api/v1/children/{self.child.pk}/feedings/{feeding.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["feeding_type"], "bottle")

    def test_nonexistent_child_returns_empty(self):
        """Accessing feedings for nonexistent child returns empty list."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get("/api/v1/children/99999/feedings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)
