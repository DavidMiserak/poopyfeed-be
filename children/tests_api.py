"""API tests for children app."""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from django_project.test_constants import TEST_PASSWORD

from .models import Child, ChildShare, ShareInvite

TEST_COPARENT_EMAIL = "coparent@example.com"
TEST_BABY_NAME = "Test Baby"
API_CHILDREN_URL = "/api/v1/children/"
API_ACCEPT_INVITE_URL = "/api/v1/invites/accept/"


class ChildAPITests(APITestCase):
    """Tests for Child API endpoints."""

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(
            username="owner",
            email="owner@example.com",
            password=TEST_PASSWORD,
        )
        cls.coparent = user_model.objects.create_user(
            username="coparent",
            email=TEST_COPARENT_EMAIL,
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
            name=TEST_BABY_NAME,
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
        self.owner_token = Token.objects.create(user=self.owner)
        self.coparent_token = Token.objects.create(user=self.coparent)
        self.caregiver_token = Token.objects.create(user=self.caregiver)
        self.stranger_token = Token.objects.create(user=self.stranger)

    def test_list_children_requires_auth(self):
        """Unauthenticated requests should be denied."""
        response = self.client.get(API_CHILDREN_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_children_owner(self):
        """Owner sees their children."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(API_CHILDREN_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], TEST_BABY_NAME)
        self.assertEqual(response.data["results"][0]["user_role"], "owner")

    def test_list_children_coparent(self):
        """Co-parent sees shared children."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        response = self.client.get(API_CHILDREN_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["user_role"], "co-parent")

    def test_list_children_caregiver(self):
        """Caregiver sees shared children."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        response = self.client.get(API_CHILDREN_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["user_role"], "caregiver")

    def test_list_children_stranger(self):
        """Stranger sees no children."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        response = self.client.get(API_CHILDREN_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_create_child(self):
        """Authenticated user can create a child."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        data = {
            "name": "New Baby",
            "date_of_birth": "2025-06-01",
            "gender": "F",
        }
        response = self.client.post(API_CHILDREN_URL, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Baby")
        self.assertEqual(response.data["user_role"], "owner")

    def test_retrieve_child_owner(self):
        """Owner can retrieve child details."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(f"/api/v1/children/{self.child.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], TEST_BABY_NAME)

    def test_retrieve_child_stranger_denied(self):
        """Stranger cannot retrieve child details."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        response = self.client.get(f"/api/v1/children/{self.child.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_child_owner(self):
        """Owner can update child."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {"name": "Updated Baby", "date_of_birth": "2025-01-01"}
        response = self.client.put(f"/api/v1/children/{self.child.pk}/", data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Baby")

    def test_update_child_coparent(self):
        """Co-parent can update child."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        data = {"name": "Coparent Updated", "date_of_birth": "2025-01-01"}
        response = self.client.put(f"/api/v1/children/{self.child.pk}/", data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_child_caregiver_denied(self):
        """Caregiver cannot update child."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        data = {"name": "Caregiver Updated", "date_of_birth": "2025-01-01"}
        response = self.client.put(f"/api/v1/children/{self.child.pk}/", data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_child_owner(self):
        """Owner can delete child."""
        child = Child.objects.create(
            parent=self.owner,
            name="To Delete",
            date_of_birth="2025-01-01",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.delete(f"/api/v1/children/{child.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_child_coparent_denied(self):
        """Co-parent cannot delete child."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        response = self.client.delete(f"/api/v1/children/{self.child.pk}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SharingAPITests(APITestCase):
    """Tests for sharing management API endpoints."""

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(
            username="owner",
            email="owner@example.com",
            password=TEST_PASSWORD,
        )
        cls.coparent = user_model.objects.create_user(
            username="coparent",
            email=TEST_COPARENT_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.new_user = user_model.objects.create_user(
            username="newuser",
            email="newuser@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name=TEST_BABY_NAME,
            date_of_birth="2025-01-01",
        )
        cls.share = ChildShare.objects.create(
            child=cls.child,
            user=cls.coparent,
            role=ChildShare.Role.CO_PARENT,
            created_by=cls.owner,
        )

    def setUp(self):
        self.owner_token = Token.objects.create(user=self.owner)
        self.coparent_token = Token.objects.create(user=self.coparent)
        self.new_user_token = Token.objects.create(user=self.new_user)

    def test_list_shares_owner(self):
        """Owner can list shares."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(f"/api/v1/children/{self.child.pk}/shares/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["user_email"], TEST_COPARENT_EMAIL)

    def test_list_shares_coparent_denied(self):
        """Co-parent cannot list shares."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        response = self.client.get(f"/api/v1/children/{self.child.pk}/shares/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_revoke_share_owner(self):
        """Owner can revoke shares."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.delete(
            f"/api/v1/children/{self.child.pk}/shares/{self.share.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ChildShare.objects.filter(pk=self.share.pk).exists())

    def test_list_invites_owner(self):
        """Owner can list invites."""
        ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(f"/api/v1/children/{self.child.pk}/invites/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertIn("invite_url", response.data[0])

    def test_create_invite_owner(self):
        """Owner can create invites."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {"role": "caregiver"}
        response = self.client.post(f"/api/v1/children/{self.child.pk}/invites/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "caregiver")
        self.assertIn("token", response.data)

    def test_accept_invite(self):
        """User can accept invite via API."""
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.new_user_token.key}")
        response = self.client.post(API_ACCEPT_INVITE_URL, {"token": invite.token})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            ChildShare.objects.filter(child=self.child, user=self.new_user).exists()
        )

    def test_accept_invite_owner_rejected(self):
        """Owner cannot accept their own invite."""
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CO_PARENT,
            created_by=self.owner,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.post(API_ACCEPT_INVITE_URL, {"token": invite.token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_invite_invalid_token(self):
        """Invalid token returns error."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.new_user_token.key}")
        response = self.client.post(API_ACCEPT_INVITE_URL, {"token": "invalid"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_invite_already_shared(self):
        """Accepting invite when already shared returns 200."""
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        # coparent already has access
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        response = self.client.post(API_ACCEPT_INVITE_URL, {"token": invite.token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_toggle_invite_owner(self):
        """Owner can toggle invite active status."""
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
            is_active=True,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.patch(
            f"/api/v1/children/{self.child.pk}/invites/{invite.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])

        # Toggle back
        response = self.client.patch(
            f"/api/v1/children/{self.child.pk}/invites/{invite.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_active"])

    def test_toggle_invite_coparent_denied(self):
        """Co-parent cannot toggle invite."""
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        response = self.client.patch(
            f"/api/v1/children/{self.child.pk}/invites/{invite.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_invite_owner(self):
        """Owner can delete invite."""
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.delete(
            f"/api/v1/children/{self.child.pk}/invites/{invite.pk}/delete/"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ShareInvite.objects.filter(pk=invite.pk).exists())

    def test_delete_invite_coparent_denied(self):
        """Co-parent cannot delete invite."""
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        response = self.client.delete(
            f"/api/v1/children/{self.child.pk}/invites/{invite.pk}/delete/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invites_coparent_denied(self):
        """Co-parent cannot list invites."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        response = self.client.get(f"/api/v1/children/{self.child.pk}/invites/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_invite_coparent_denied(self):
        """Co-parent cannot create invites."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        response = self.client.post(
            f"/api/v1/children/{self.child.pk}/invites/", {"role": "CG"}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_revoke_share_coparent_denied(self):
        """Co-parent cannot revoke shares."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        response = self.client.delete(
            f"/api/v1/children/{self.child.pk}/shares/{self.share.pk}/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_child_partial_update(self):
        """Owner can partial update child."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.patch(
            f"/api/v1/children/{self.child.pk}/", {"name": "Patched Baby"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Patched Baby")

    def test_child_nonexistent(self):
        """Accessing nonexistent child returns 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get("/api/v1/children/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PermissionEdgeCaseTests(APITestCase):
    """Tests for permission edge cases."""

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(
            username="user",
            email="user@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name=TEST_BABY_NAME,
            date_of_birth="2025-01-01",
        )

    def setUp(self):
        self.token = Token.objects.create(user=self.user)

    def test_share_nonexistent_returns_404(self):
        """Revoking nonexistent share returns 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.delete(f"/api/v1/children/{self.child.pk}/shares/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_toggle_nonexistent_invite_returns_404(self):
        """Toggling nonexistent invite returns 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.patch(f"/api/v1/children/{self.child.pk}/invites/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_nonexistent_invite_returns_404(self):
        """Deleting nonexistent invite returns 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.delete(
            f"/api/v1/children/{self.child.pk}/invites/99999/delete/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_accept_inactive_invite(self):
        """Accepting inactive invite returns error."""
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.user,
            is_active=False,
        )
        other_user = get_user_model().objects.create_user(
            username="other",
            email="other@example.com",
            password=TEST_PASSWORD,
        )
        other_token = Token.objects.create(user=other_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {other_token.key}")
        response = self.client.post(API_ACCEPT_INVITE_URL, {"token": invite.token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CustomBottleValidationTests(APITestCase):
    """Tests for custom bottle amount validation in ChildSerializer."""

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(
            username="bottleuser",
            email="bottle@example.com",
            password=TEST_PASSWORD,
        )

    def setUp(self):
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def _create_child_data(self, **overrides):
        data = {
            "name": "Bottle Baby",
            "date_of_birth": "2025-06-01",
            "gender": "F",
        }
        data.update(overrides)
        return data

    def test_create_child_with_valid_custom_bottles(self):
        """Valid custom bottle amounts (low < mid < high) succeed."""
        data = self._create_child_data(
            custom_bottle_low_oz="2.0",
            custom_bottle_mid_oz="4.0",
            custom_bottle_high_oz="6.0",
        )
        response = self.client.post(API_CHILDREN_URL, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(response.data["custom_bottle_low_oz"]), Decimal("2.0"))

    def test_create_child_with_null_custom_bottles(self):
        """All null custom bottle amounts succeed (use age-based defaults)."""
        data = self._create_child_data()
        response = self.client.post(API_CHILDREN_URL, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["custom_bottle_low_oz"])

    def test_custom_bottle_low_out_of_range(self):
        """Low amount below 0.1 oz is rejected."""
        data = self._create_child_data(
            custom_bottle_low_oz="0.05",
            custom_bottle_mid_oz="4.0",
            custom_bottle_high_oz="6.0",
        )
        response = self.client.post(API_CHILDREN_URL, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_custom_bottle_low_above_range(self):
        """Low amount above 50 oz is rejected."""
        data = self._create_child_data(
            custom_bottle_low_oz="51.0",
            custom_bottle_mid_oz="52.0",
            custom_bottle_high_oz="53.0",
        )
        response = self.client.post(API_CHILDREN_URL, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_custom_bottle_mid_out_of_range(self):
        """Mid amount above 50 oz is rejected."""
        data = self._create_child_data(
            custom_bottle_low_oz="2.0",
            custom_bottle_mid_oz="55.0",
            custom_bottle_high_oz="60.0",
        )
        response = self.client.post(API_CHILDREN_URL, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_custom_bottle_high_out_of_range(self):
        """High amount above 50 oz is rejected."""
        data = self._create_child_data(
            custom_bottle_low_oz="2.0",
            custom_bottle_mid_oz="4.0",
            custom_bottle_high_oz="55.0",
        )
        response = self.client.post(API_CHILDREN_URL, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_custom_bottle_partial_set_rejected(self):
        """Setting only some custom bottle amounts is rejected."""
        data = self._create_child_data(
            custom_bottle_low_oz="2.0",
            custom_bottle_mid_oz="4.0",
            # high not set
        )
        response = self.client.post(API_CHILDREN_URL, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_custom_bottle_low_greater_than_mid(self):
        """Low >= mid is rejected."""
        data = self._create_child_data(
            custom_bottle_low_oz="5.0",
            custom_bottle_mid_oz="4.0",
            custom_bottle_high_oz="6.0",
        )
        response = self.client.post(API_CHILDREN_URL, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_custom_bottle_mid_greater_than_high(self):
        """Mid >= high is rejected."""
        data = self._create_child_data(
            custom_bottle_low_oz="2.0",
            custom_bottle_mid_oz="7.0",
            custom_bottle_high_oz="6.0",
        )
        response = self.client.post(API_CHILDREN_URL, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_custom_bottle_low_equal_mid(self):
        """Low == mid is rejected."""
        data = self._create_child_data(
            custom_bottle_low_oz="4.0",
            custom_bottle_mid_oz="4.0",
            custom_bottle_high_oz="6.0",
        )
        response = self.client.post(API_CHILDREN_URL, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AcceptInviteRaceConditionTests(APITestCase):
    """Tests for IntegrityError handling in accept invite."""

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(
            username="raceowner",
            email="raceowner@example.com",
            password=TEST_PASSWORD,
        )
        cls.acceptor = user_model.objects.create_user(
            username="raceacceptor",
            email="raceacceptor@example.com",
            password=TEST_PASSWORD,
        )

    def setUp(self):
        self.acceptor_token = Token.objects.create(user=self.acceptor)
        self.child = Child.objects.create(
            parent=self.owner,
            name="Race Baby",
            date_of_birth="2025-01-01",
        )
        self.invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )

    def test_accept_invite_race_condition_integrity_error(self):
        """IntegrityError during accept is handled gracefully."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {self.acceptor_token.key}"
        )

        # Create the share manually first (simulating the race condition)
        existing_share = ChildShare.objects.create(
            child=self.child,
            user=self.acceptor,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )

        # Mock get_or_create to raise IntegrityError then have get succeed
        original_get_or_create = ChildShare.objects.get_or_create

        def mock_get_or_create(**kwargs):
            raise IntegrityError("duplicate key")

        with patch.object(
            ChildShare.objects, "get_or_create", side_effect=mock_get_or_create
        ):
            response = self.client.post(
                API_ACCEPT_INVITE_URL, {"token": self.invite.token}
            )

        # Should return 200 OK (existing share found)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_accept_invite_create_invalid_role(self):
        """Accept invite with invalid role in serializer."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {self.acceptor_token.key}"
        )
        response = self.client.post(
            API_ACCEPT_INVITE_URL, {"token": "nonexistent-token-value"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class SerializerContextEdgeCaseTests(APITestCase):
    """Tests for serializer methods with missing request context."""

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(
            username="ctxuser",
            email="ctx@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name="Context Baby",
            date_of_birth="2025-01-01",
        )

    def test_serializer_without_request_context(self):
        """Serializer methods return defaults without request context."""
        from .api import ChildSerializer

        serializer = ChildSerializer(self.child, context={})
        self.assertIsNone(serializer.get_user_role(self.child))
        self.assertFalse(serializer.get_can_edit(self.child))
        self.assertFalse(serializer.get_can_manage_sharing(self.child))

    def test_user_role_for_user_with_no_share(self):
        """User with no share and not owner returns None for user_role."""
        from .api import ChildSerializer
        from rest_framework.test import APIRequestFactory

        user_model = get_user_model()
        stranger = user_model.objects.create_user(
            username="ctx_stranger",
            email="ctx_stranger@example.com",
            password=TEST_PASSWORD,
        )
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = stranger

        serializer = ChildSerializer(self.child, context={"request": request})
        self.assertIsNone(serializer.get_user_role(self.child))
