"""Base test class for tracking app API tests.

This class consolidates common test patterns across diapers, feedings, and naps
API tests to eliminate duplication.
"""

from abc import ABC

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from children.models import Child, ChildShare
from django_project.test_constants import TEST_PASSWORD


class BaseTrackingAPITests(ABC, APITestCase):
    """Base class for tracking API tests (diapers, feedings, naps).

    This is an abstract base class and will not be run by Django's test runner.

    Subclasses must set:
        model: The tracking model class (e.g., DiaperChange, Feeding, Nap)
        app_name: The app name for URL routing (e.g., "diapers", "feedings", "naps")

    Subclasses should override:
        get_create_data(): Return dict of data for creating a record
        get_update_data(): Return dict of data for updating a record (optional)
        create_test_record(): Create a test record and return it
    """

    model: type | None = None  # Must be set by subclass
    app_name: str | None = None  # Must be set by subclass

    @classmethod
    def __subclasshook__(cls, subclass):
        """Make this class abstract - won't be collected as a test class."""
        return NotImplemented

    @classmethod
    def setUpTestData(cls):
        """Create users, child, and shares for testing."""
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(
            username="owner",
            email="owner@example.com",
            password=TEST_PASSWORD,
        )
        cls.coparent = user_model.objects.create_user(
            username="coparent",
            email="coparent@example.com",
            password=TEST_PASSWORD,
        )
        cls.caregiver = user_model.objects.create_user(
            username="caregiver",
            email="caregiver@example.com",
            password=TEST_PASSWORD,
        )
        cls.stranger = user_model.objects.create_user(
            username="stranger",
            email="stranger@example.com",
            password=TEST_PASSWORD,
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

    def setUp(self):
        """Create auth tokens for each user."""
        # Skip if this is the base class itself (not a subclass)
        if self.__class__ == BaseTrackingAPITests:
            self.skipTest("Base class should not be run directly")
        self.owner_token = Token.objects.create(user=self.owner)
        self.coparent_token = Token.objects.create(user=self.coparent)
        self.caregiver_token = Token.objects.create(user=self.caregiver)
        self.stranger_token = Token.objects.create(user=self.stranger)

    def get_list_url(self):
        """Get the list/create URL for this tracking app."""
        return f"/api/v1/children/{self.child.pk}/{self.app_name}/"

    def get_detail_url(self, pk):
        """Get the retrieve/update/delete URL for a specific record."""
        return f"/api/v1/children/{self.child.pk}/{self.app_name}/{pk}/"

    def get_create_data(self):
        """Override in subclass to return data for creating a record."""
        raise NotImplementedError("Subclass must implement get_create_data()")

    def get_update_data(self):
        """Override in subclass to return data for updating a record."""
        return self.get_create_data()

    def create_test_record(self):
        """Override in subclass to create and return a test record."""
        raise NotImplementedError("Subclass must implement create_test_record()")

    # Common test methods
    def test_caregiver_can_create(self):
        """Caregiver can create records."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        response = self.client.post(self.get_list_url(), self.get_create_data())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_caregiver_cannot_update(self):
        """Caregiver cannot update records."""
        record = self.create_test_record()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        response = self.client.put(
            self.get_detail_url(record.pk), self.get_update_data()
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_caregiver_cannot_delete(self):
        """Caregiver cannot delete records."""
        record = self.create_test_record()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        response = self.client.delete(self.get_detail_url(record.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_delete(self):
        """Owner can delete records."""
        record = self.create_test_record()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.delete(self.get_detail_url(record.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_partial_update(self):
        """Owner can partial update record."""
        record = self.create_test_record()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.patch(
            self.get_detail_url(record.pk), self.get_create_data()
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve(self):
        """Can retrieve single record."""
        record = self.create_test_record()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(self.get_detail_url(record.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_nonexistent_child_returns_empty(self):
        """Accessing records for nonexistent child returns empty list."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(f"/api/v1/children/99999/{self.app_name}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_stranger_cannot_create(self):
        """Stranger cannot create records."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        response = self.client.post(self.get_list_url(), self.get_create_data())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TrackingBaseContractTests(TestCase):
    """Tests for BaseTrackingAPITests contract (subclasshook, etc.)."""

    def test_subclasshook_returns_not_implemented_for_non_subclass(self):
        """__subclasshook__ returns NotImplemented for non-subclass."""
        # Called as class method: cls is bound, pass only the candidate subclass
        result = BaseTrackingAPITests.__subclasshook__(object)
        self.assertIs(result, NotImplemented)
