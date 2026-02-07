"""API tests for children app."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

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
            password="testpass123",
        )
        cls.coparent = user_model.objects.create_user(
            username="coparent",
            email=TEST_COPARENT_EMAIL,
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
        self.assertEqual(response.data["results"][0]["user_role"], "co")

    def test_list_children_caregiver(self):
        """Caregiver sees shared children."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.caregiver_token.key}")
        response = self.client.get(API_CHILDREN_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["user_role"], "cg")

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
            password="testpass123",
        )
        cls.coparent = user_model.objects.create_user(
            username="coparent",
            email=TEST_COPARENT_EMAIL,
            password="testpass123",
        )
        cls.new_user = user_model.objects.create_user(
            username="newuser",
            email="newuser@example.com",
            password="testpass123",
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
        data = {"role": "CG"}
        response = self.client.post(f"/api/v1/children/{self.child.pk}/invites/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "CG")
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
            password="testpass123",
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
            password="testpass123",
        )
        other_token = Token.objects.create(user=other_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {other_token.key}")
        response = self.client.post(API_ACCEPT_INVITE_URL, {"token": invite.token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
