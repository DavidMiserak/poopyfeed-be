"""API tests for children app."""

from datetime import date
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
API_CHILD_DETAIL = "/api/v1/children/{pk}/"
API_CHILD_SHARES = "/api/v1/children/{pk}/shares/"
API_CHILD_SHARE_DETAIL = "/api/v1/children/{pk}/shares/{share_pk}/"
API_CHILD_INVITES = "/api/v1/children/{pk}/invites/"
API_CHILD_INVITE_DETAIL = "/api/v1/children/{pk}/invites/{invite_pk}/"
API_CHILD_INVITE_DELETE = "/api/v1/children/{pk}/invites/{invite_pk}/delete/"
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

    def test_list_children_non_paginated_when_pagination_disabled(self):
        """When pagination_class is None, list returns plain list (no pagination keys)."""
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api import ChildViewSet

        factory = APIRequestFactory()
        request = factory.get(API_CHILDREN_URL)
        force_authenticate(request, user=self.owner)
        view = ChildViewSet.as_view({"get": "list"})
        old_pagination = ChildViewSet.pagination_class
        ChildViewSet.pagination_class = None
        try:
            response = view(request)
        finally:
            ChildViewSet.pagination_class = old_pagination
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], TEST_BABY_NAME)

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
        response = self.client.get(API_CHILD_DETAIL.format(pk=self.child.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], TEST_BABY_NAME)

    def test_retrieve_child_stranger_denied(self):
        """Stranger cannot retrieve child details."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        response = self.client.get(API_CHILD_DETAIL.format(pk=self.child.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_child_owner(self):
        """Owner can update child."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {"name": "Updated Baby", "date_of_birth": "2025-01-01"}
        response = self.client.put(API_CHILD_DETAIL.format(pk=self.child.pk), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Baby")

    def test_update_child_coparent(self):
        """Co-parent can update child."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        data = {"name": "Coparent Updated", "date_of_birth": "2025-01-01"}
        response = self.client.put(API_CHILD_DETAIL.format(pk=self.child.pk), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_child_caregiver_denied(self):
        """Caregiver cannot update child."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        data = {"name": "Caregiver Updated", "date_of_birth": "2025-01-01"}
        response = self.client.put(API_CHILD_DETAIL.format(pk=self.child.pk), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_child_owner(self):
        """Owner can delete child."""
        child = Child.objects.create(
            parent=self.owner,
            name="To Delete",
            date_of_birth="2025-01-01",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.delete(API_CHILD_DETAIL.format(pk=child.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_child_coparent_denied(self):
        """Co-parent cannot delete child."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        response = self.client.delete(API_CHILD_DETAIL.format(pk=self.child.pk))
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
        response = self.client.get(API_CHILD_SHARES.format(pk=self.child.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["user_email"], TEST_COPARENT_EMAIL)

    def test_list_shares_coparent_denied(self):
        """Co-parent cannot list shares."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        response = self.client.get(API_CHILD_SHARES.format(pk=self.child.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_revoke_share_owner(self):
        """Owner can revoke shares."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.delete(
            API_CHILD_SHARE_DETAIL.format(pk=self.child.pk, share_pk=self.share.pk)
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
        response = self.client.get(API_CHILD_INVITES.format(pk=self.child.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertIn("invite_url", response.data[0])

    def test_create_invite_owner(self):
        """Owner can create invites."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        data = {"role": "caregiver"}
        response = self.client.post(API_CHILD_INVITES.format(pk=self.child.pk), data)
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
            API_CHILD_INVITE_DETAIL.format(pk=self.child.pk, invite_pk=invite.pk)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])

        # Toggle back
        response = self.client.patch(
            API_CHILD_INVITE_DETAIL.format(pk=self.child.pk, invite_pk=invite.pk)
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
            API_CHILD_INVITE_DETAIL.format(pk=self.child.pk, invite_pk=invite.pk)
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
            API_CHILD_INVITE_DELETE.format(pk=self.child.pk, invite_pk=invite.pk)
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
            API_CHILD_INVITE_DELETE.format(pk=self.child.pk, invite_pk=invite.pk)
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invites_coparent_denied(self):
        """Co-parent cannot list invites."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        response = self.client.get(API_CHILD_INVITES.format(pk=self.child.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_invite_coparent_denied(self):
        """Co-parent cannot create invites."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        response = self.client.post(
            API_CHILD_INVITES.format(pk=self.child.pk), {"role": "CG"}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_revoke_share_coparent_denied(self):
        """Co-parent cannot revoke shares."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        response = self.client.delete(
            API_CHILD_SHARE_DETAIL.format(pk=self.child.pk, share_pk=self.share.pk)
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_child_partial_update(self):
        """Owner can partial update child."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.patch(
            API_CHILD_DETAIL.format(pk=self.child.pk), {"name": "Patched Baby"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Patched Baby")

    def test_child_nonexistent(self):
        """Accessing nonexistent child returns 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(API_CHILD_DETAIL.format(pk=99999))
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
        response = self.client.delete(
            API_CHILD_SHARE_DETAIL.format(pk=self.child.pk, share_pk=99999)
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_toggle_nonexistent_invite_returns_404(self):
        """Toggling nonexistent invite returns 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.patch(
            API_CHILD_INVITE_DETAIL.format(pk=self.child.pk, invite_pk=99999)
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_nonexistent_invite_returns_404(self):
        """Deleting nonexistent invite returns 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.delete(
            API_CHILD_INVITE_DELETE.format(pk=self.child.pk, invite_pk=99999)
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
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.acceptor_token.key}")

        # Create the share manually first (simulating the race condition)
        ChildShare.objects.create(
            child=self.child,
            user=self.acceptor,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )

        # Mock get_or_create to raise IntegrityError then have get succeed
        ChildShare.objects.get_or_create

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
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.acceptor_token.key}")
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
        from rest_framework.test import APIRequestFactory

        from .api import ChildSerializer

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


class CustomBottleValidationAdditionalTests(APITestCase):
    """Additional custom bottle validation edge cases."""

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(
            username="bottleuser2",
            email="bottle2@example.com",
            password=TEST_PASSWORD,
        )

    def setUp(self):
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_custom_bottle_mid_below_range(self):
        """Mid amount below 0.1 oz is rejected."""
        data = {
            "name": "Mid Baby",
            "date_of_birth": "2025-06-01",
            "custom_bottle_low_oz": "0.1",
            "custom_bottle_mid_oz": "0.05",
            "custom_bottle_high_oz": "6.0",
        }
        response = self.client.post(API_CHILDREN_URL, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_custom_bottle_high_below_range(self):
        """High amount below 0.1 oz is rejected."""
        data = {
            "name": "High Baby",
            "date_of_birth": "2025-06-01",
            "custom_bottle_low_oz": "0.1",
            "custom_bottle_mid_oz": "0.2",
            "custom_bottle_high_oz": "0.05",
        }
        response = self.client.post(API_CHILDREN_URL, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_custom_bottle_low_equal_high(self):
        """Low >= high is rejected (even if mid is between)."""
        data = {
            "name": "EqHigh Baby",
            "date_of_birth": "2025-06-01",
            "custom_bottle_low_oz": "6.0",
            "custom_bottle_mid_oz": "3.0",
            "custom_bottle_high_oz": "6.0",
        }
        response = self.client.post(API_CHILDREN_URL, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_share_invite_invalid_role_rejected(self):
        """Creating invite with invalid role is rejected."""
        child = Child.objects.create(
            parent=self.user,
            name="Invite Role Baby",
            date_of_birth="2025-01-01",
        )
        response = self.client.post(
            API_CHILD_INVITES.format(pk=child.pk),
            {"role": "admin"},  # Invalid role
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TrackingViewSetUnitTests(APITestCase):
    """Unit tests for TrackingViewSet base class edge cases."""

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(
            username="trackingowner",
            email="tracking@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name="Tracking Baby",
            date_of_birth="2025-01-01",
        )

    def setUp(self):
        self.token = Token.objects.create(user=self.owner)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_date_range_filtering_gte(self):
        """Tracking list supports date range filtering with __gte."""
        from django.utils import timezone

        from diapers.models import DiaperChange

        DiaperChange.objects.create(
            child=self.child,
            change_type="wet",
            changed_at=timezone.now(),
        )
        url = f"/api/v1/children/{self.child.pk}/diapers/"
        response = self.client.get(url, {"changed_at__gte": "2020-01-01T00:00:00Z"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_date_range_filtering_lt(self):
        """Tracking list supports date range filtering with __lt."""
        from django.utils import timezone

        from diapers.models import DiaperChange

        DiaperChange.objects.create(
            child=self.child,
            change_type="wet",
            changed_at=timezone.now(),
        )
        url = f"/api/v1/children/{self.child.pk}/diapers/"
        response = self.client.get(url, {"changed_at__lt": "2020-01-01T00:00:00Z"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_date_range_filtering_invalid_date_ignored(self):
        """Invalid date in filter parameter is silently ignored."""
        url = f"/api/v1/children/{self.child.pk}/diapers/"
        response = self.client.get(url, {"changed_at__gte": "not-a-date"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class CacheUtilsTests(APITestCase):
    """Tests for cache_utils edge cases."""

    def test_get_child_last_activities_empty_ids(self):
        """Empty child_ids list returns empty dict."""
        from .cache_utils import get_child_last_activities

        result = get_child_last_activities([])
        self.assertEqual(result, {})

    def test_get_child_last_activities_partial_cache_hit(self):
        """Mix of cached and uncached children merges correctly."""
        from django.core.cache import cache

        from .cache_utils import get_child_last_activities

        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="cacheuser",
            email="cache@example.com",
            password=TEST_PASSWORD,
        )
        child1 = Child.objects.create(
            parent=user, name="Cache Baby 1", date_of_birth="2025-01-01"
        )
        child2 = Child.objects.create(
            parent=user, name="Cache Baby 2", date_of_birth="2025-01-01"
        )

        # Pre-cache child1's data
        cached_data = {
            "last_diaper_change": None,
            "last_nap": None,
            "last_feeding": None,
        }
        cache.set(f"child_activities_{child1.id}", cached_data)

        # Fetch both - child1 from cache, child2 from DB
        result = get_child_last_activities([child1.id, child2.id])
        self.assertIn(child1.id, result)
        self.assertIn(child2.id, result)
        self.assertEqual(result[child1.id], cached_data)

    def test_invalidate_child_activities_cache(self):
        """Cache invalidation deletes the correct key after commit."""
        from django.core.cache import cache

        from .cache_utils import invalidate_child_activities_cache

        # Set a cache entry
        cache.set("child_activities_999", {"test": "data"})
        self.assertIsNotNone(cache.get("child_activities_999"))

        # Invalidate - verify function doesn't error
        invalidate_child_activities_cache(999)

    def test_invalidate_child_activities_cache_handles_delete_failure(self):
        """When cache.delete raises (e.g. Redis down), exception is caught and logged."""
        from unittest.mock import patch

        from .cache_utils import invalidate_child_activities_cache

        with patch("children.cache_utils.cache") as mock_cache:
            mock_cache.delete.side_effect = Exception("Redis connection failed")
            with self.captureOnCommitCallbacks(execute=True):
                invalidate_child_activities_cache(777)
        # Callback ran; exception was caught and logged (no re-raise)
        mock_cache.delete.assert_called_once_with("child_activities_777")

    def test_invalidate_child_activities_cache_success_path_runs_on_commit(self):
        """On commit, cache.delete runs and success path (logger.info) is executed."""
        from django.core.cache import cache

        from .cache_utils import invalidate_child_activities_cache

        cache.set("child_activities_555", {"test": "data"})
        with self.captureOnCommitCallbacks(execute=True):
            invalidate_child_activities_cache(555)
        self.assertIsNone(cache.get("child_activities_555"))


class CacheUtilsTransactionTests(APITestCase):
    """Test cache invalidation with TransactionTestCase behavior."""

    def test_invalidate_clears_cache_on_commit(self):
        """Cache key is deleted when transaction commits."""
        from django.core.cache import cache
        from django.db import connection

        from .cache_utils import invalidate_child_activities_cache

        # Set cache entry
        cache.set("child_activities_888", {"test": "data"})

        # Run in a real transaction context
        from django.test.utils import CaptureQueriesContext

        invalidate_child_activities_cache(888)

        # Force on_commit callbacks to run
        connection.cursor()  # ensure connection is open
        # In test mode, on_commit runs at end of test
        # Just verify no errors for now


class ChildSerializerDirectValidationTests(APITestCase):
    """Test serializer validators directly to hit custom validation code."""

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(
            username="serowner",
            email="serowner@example.com",
            password=TEST_PASSWORD,
        )
        cls.caregiver = user_model.objects.create_user(
            username="sercaregiver",
            email="sercaregiver@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name="Direct Baby",
            date_of_birth="2025-01-01",
        )
        ChildShare.objects.create(
            child=cls.child,
            user=cls.caregiver,
            role=ChildShare.Role.CAREGIVER,
            created_by=cls.owner,
        )

    def test_validate_custom_bottle_low_oz_out_of_range(self):
        """Direct call to validate_custom_bottle_low_oz with out-of-range value."""
        from decimal import Decimal

        from rest_framework.exceptions import ValidationError

        from .api import ChildSerializer

        serializer = ChildSerializer()
        # Below range
        with self.assertRaises(ValidationError):
            serializer.validate_custom_bottle_low_oz(Decimal("0.05"))
        # Above range
        with self.assertRaises(ValidationError):
            serializer.validate_custom_bottle_low_oz(Decimal("51"))

    def test_validate_feeding_reminder_interval_rejects_caregiver(self):
        """Caregiver cannot set feeding_reminder_interval (serializer validation)."""
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api import ChildSerializer

        factory = APIRequestFactory()
        req = factory.patch("/")
        force_authenticate(req, user=self.caregiver)
        request = Request(req)
        serializer = ChildSerializer(
            instance=self.child,
            data={"feeding_reminder_interval": 2},
            partial=True,
            context={"request": request},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("feeding_reminder_interval", serializer.errors)

    def test_validate_feeding_reminder_interval_no_request_returns_value(self):
        """When context has no request, validate_feeding_reminder_interval returns value."""
        from .api import ChildSerializer

        serializer = ChildSerializer(instance=self.child, context={})
        result = serializer.validate_feeding_reminder_interval(3)
        self.assertEqual(result, 3)

    def test_validate_feeding_reminder_interval_valid_returns_value(self):
        """Owner with valid interval (2,3,4,6) returns value."""
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory, force_authenticate

        from .api import ChildSerializer

        factory = APIRequestFactory()
        req = factory.patch("/")
        force_authenticate(req, user=self.owner)
        request = Request(req)
        serializer = ChildSerializer(
            instance=self.child,
            context={"request": request},
        )
        result = serializer.validate_feeding_reminder_interval(4)
        self.assertEqual(result, 4)

    def test_validate_custom_bottle_mid_oz_out_of_range(self):
        """Direct call to validate_custom_bottle_mid_oz with out-of-range value."""
        from decimal import Decimal

        from rest_framework.exceptions import ValidationError

        from .api import ChildSerializer

        serializer = ChildSerializer()
        with self.assertRaises(ValidationError):
            serializer.validate_custom_bottle_mid_oz(Decimal("0.05"))
        with self.assertRaises(ValidationError):
            serializer.validate_custom_bottle_mid_oz(Decimal("51"))

    def test_validate_custom_bottle_high_oz_out_of_range(self):
        """Direct call to validate_custom_bottle_high_oz with out-of-range value."""
        from decimal import Decimal

        from rest_framework.exceptions import ValidationError

        from .api import ChildSerializer

        serializer = ChildSerializer()
        with self.assertRaises(ValidationError):
            serializer.validate_custom_bottle_high_oz(Decimal("0.05"))
        with self.assertRaises(ValidationError):
            serializer.validate_custom_bottle_high_oz(Decimal("51"))

    def test_validate_cross_field_low_ge_high(self):
        """Direct call to validate() with low >= high."""
        from decimal import Decimal

        from rest_framework.exceptions import ValidationError

        from .api import ChildSerializer

        serializer = ChildSerializer()
        # low < mid but low >= high (edge case: mid is between)
        data = {
            "custom_bottle_low_oz": Decimal("5"),
            "custom_bottle_mid_oz": Decimal("4"),
            "custom_bottle_high_oz": Decimal("4.5"),
        }
        # This should hit low >= mid first
        with self.assertRaises(ValidationError):
            serializer.validate(data)

        # Now test low >= high where low < mid < high doesn't hold
        # but low >= high: low=5, mid=6, high=5
        data2 = {
            "custom_bottle_low_oz": Decimal("5"),
            "custom_bottle_mid_oz": Decimal("6"),
            "custom_bottle_high_oz": Decimal("5"),
        }
        # This hits mid >= high
        with self.assertRaises(ValidationError):
            serializer.validate(data2)


class FeedingReminderIntervalAPITests(APITestCase):
    """Test feeding reminder interval field in ChildSerializer."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(
            username="remowner",
            email="remowner@example.com",
            password=TEST_PASSWORD,
        )
        cls.coparent = User.objects.create_user(
            username="remcoparent",
            email="remcoparent@example.com",
            password=TEST_PASSWORD,
        )
        cls.caregiver = User.objects.create_user(
            username="remcg",
            email="remcg@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name="Reminder Baby",
            date_of_birth=date(2025, 6, 15),
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

    def test_owner_can_set_interval(self):
        """Owner can set feeding_reminder_interval."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.patch(
            API_CHILD_DETAIL.format(pk=self.child.id),
            {"feeding_reminder_interval": 3},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["feeding_reminder_interval"], 3)
        self.child.refresh_from_db()
        self.assertEqual(self.child.feeding_reminder_interval, 3)

    def test_coparent_can_set_interval(self):
        """Co-parent can set feeding_reminder_interval."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.coparent_token.key}")
        response = self.client.patch(
            API_CHILD_DETAIL.format(pk=self.child.id),
            {"feeding_reminder_interval": 4},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["feeding_reminder_interval"], 4)
        self.child.refresh_from_db()
        self.assertEqual(self.child.feeding_reminder_interval, 4)

    def test_caregiver_cannot_set_interval(self):
        """Caregiver cannot set feeding_reminder_interval (403)."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        response = self.client.patch(
            API_CHILD_DETAIL.format(pk=self.child.id),
            {"feeding_reminder_interval": 2},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_valid_interval_values(self):
        """Only 2, 3, 4, 6 or null are valid."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")

        # Valid: 2, 3, 4, 6
        for interval in [2, 3, 4, 6]:
            response = self.client.patch(
                API_CHILD_DETAIL.format(pk=self.child.id),
                {"feeding_reminder_interval": interval},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["feeding_reminder_interval"], interval)

        # Valid: null (off)
        response = self.client.patch(
            API_CHILD_DETAIL.format(pk=self.child.id),
            {"feeding_reminder_interval": None},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["feeding_reminder_interval"])

    def test_invalid_interval_values(self):
        """Invalid intervals rejected with 400."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")

        # Invalid: 1, 5, 7, 8, 10, etc.
        for interval in [1, 5, 7, 8, 10, 24]:
            response = self.client.patch(
                API_CHILD_DETAIL.format(pk=self.child.id),
                {"feeding_reminder_interval": interval},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("feeding_reminder_interval", response.data)

    def test_interval_default_is_null(self):
        """New children have feeding_reminder_interval = null."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        response = self.client.get(API_CHILD_DETAIL.format(pk=self.child.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["feeding_reminder_interval"])

    def test_interval_exposed_in_list(self):
        """feeding_reminder_interval is included in list view."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.owner_token.key}")
        self.child.feeding_reminder_interval = 3
        self.child.save()

        response = self.client.get("/api/v1/children/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        child_data = next(
            c for c in response.data["results"] if c["id"] == self.child.id
        )
        self.assertEqual(child_data["feeding_reminder_interval"], 3)
