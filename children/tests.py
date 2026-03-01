from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.admin.sites import site as admin_site
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from django_project.test_constants import TEST_PASSWORD

from .forms import ChildForm, LocalDateTimeFormMixin
from .models import Child, ChildShare, ShareInvite

TEST_PARENT_EMAIL = "parent@example.com"
TEST_OWNER_EMAIL = "owner@example.com"
TEST_OTHER_EMAIL = "other@example.com"
TEST_SHARED_EMAIL = "shared@example.com"
TEST_COPARENT_EMAIL = "coparent@example.com"
TEST_CAREGIVER_EMAIL = "caregiver@example.com"
TEST_NEW_EMAIL = "new@example.com"
TEST_BABY_NAME = "Baby Jane"
TEST_BABY_NAME_ALT = "Baby Test"
URL_CHILD_LIST = "children:child_list"
URL_CHILD_EDIT = "children:child_edit"
URL_CHILD_DELETE = "children:child_delete"
URL_CHILD_SHARING = "children:child_sharing"
URL_CREATE_INVITE = "children:create_invite"
URL_ACCEPT_INVITE = "children:accept_invite"


class ChildModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="testparent",
            email=TEST_PARENT_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
            gender=Child.Gender.FEMALE,
        )

    def test_child_creation(self):
        self.assertEqual(self.child.name, TEST_BABY_NAME)
        self.assertEqual(self.child.date_of_birth, date(2025, 6, 15))
        self.assertEqual(self.child.gender, "F")
        self.assertEqual(self.child.parent, self.user)

    def test_child_str(self):
        self.assertEqual(str(self.child), TEST_BABY_NAME)

    def test_child_ordering(self):
        older_child = Child.objects.create(
            parent=self.user,
            name="Older Sibling",
            date_of_birth=date(2023, 1, 1),
        )
        children = list(Child.objects.all())
        self.assertEqual(children[0], self.child)
        self.assertEqual(children[1], older_child)

    def test_gender_optional(self):
        child_no_gender = Child.objects.create(
            parent=self.user,
            name="Baby Alex",
            date_of_birth=date(2025, 8, 1),
        )
        self.assertEqual(child_no_gender.gender, "")

    def test_gender_choices(self):
        self.assertEqual(Child.Gender.MALE, "M")
        self.assertEqual(Child.Gender.FEMALE, "F")
        self.assertEqual(Child.Gender.OTHER, "O")

    def test_parent_related_name(self):
        self.assertIn(self.child, self.user.children.all())

    def test_cascade_delete(self):
        user = get_user_model().objects.create_user(
            username="tempparent",
            email="temp@example.com",
            password=TEST_PASSWORD,
        )
        Child.objects.create(
            parent=user,
            name="Temp Baby",
            date_of_birth=date(2025, 1, 1),
        )
        child_count_before = Child.objects.count()
        user.delete()
        self.assertEqual(Child.objects.count(), child_count_before - 1)

    def test_timestamps(self):
        self.assertIsNotNone(self.child.created_at)
        self.assertIsNotNone(self.child.updated_at)


class ChildAdminTests(TestCase):
    def test_child_admin_registered(self):
        self.assertIn(Child, admin_site._registry)


class ChildFormTests(TestCase):
    def test_valid_form(self):
        form = ChildForm(
            data={
                "name": TEST_BABY_NAME_ALT,
                "date_of_birth": "2025-06-15",
                "gender": "M",
            }
        )
        self.assertTrue(form.is_valid())

    def test_valid_form_without_gender(self):
        form = ChildForm(
            data={
                "name": TEST_BABY_NAME_ALT,
                "date_of_birth": "2025-06-15",
                "gender": "",
            }
        )
        self.assertTrue(form.is_valid())

    def test_invalid_form_missing_name(self):
        form = ChildForm(
            data={
                "name": "",
                "date_of_birth": "2025-06-15",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_invalid_form_missing_dob(self):
        form = ChildForm(
            data={
                "name": TEST_BABY_NAME_ALT,
                "date_of_birth": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("date_of_birth", form.errors)


class ChildViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="testparent",
            email=TEST_PARENT_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.other_user = get_user_model().objects.create_user(
            username="otherparent",
            email=TEST_OTHER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )
        cls.other_child = Child.objects.create(
            parent=cls.other_user,
            name="Other Baby",
            date_of_birth=date(2025, 1, 1),
        )

    def test_list_view_requires_login(self):
        response = self.client.get(reverse(URL_CHILD_LIST))
        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts/login", response.url)

    def test_list_view_shows_only_own_children(self):
        self.client.login(email=TEST_PARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(reverse(URL_CHILD_LIST))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, TEST_BABY_NAME)
        self.assertNotContains(response, "Other Baby")

    def test_create_view_requires_login(self):
        response = self.client.get(reverse("children:child_add"))
        self.assertEqual(response.status_code, 302)

    def test_create_view_adds_child(self):
        self.client.login(email=TEST_PARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.post(
            reverse("children:child_add"),
            {
                "name": "New Baby",
                "date_of_birth": "2025-12-01",
                "gender": "F",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Child.objects.filter(name="New Baby", parent=self.user).exists()
        )

    def test_update_view_requires_login(self):
        response = self.client.get(
            reverse(URL_CHILD_EDIT, kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_update_view_only_own_child(self):
        self.client.login(email=TEST_PARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_CHILD_EDIT, kwargs={"pk": self.other_child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_update_view_updates_child(self):
        self.client.login(email=TEST_PARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.post(
            reverse(URL_CHILD_EDIT, kwargs={"pk": self.child.pk}),
            {
                "name": "Updated Name",
                "date_of_birth": "2025-06-15",
                "gender": "F",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.child.refresh_from_db()
        self.assertEqual(self.child.name, "Updated Name")

    def test_delete_view_requires_login(self):
        response = self.client.get(
            reverse(URL_CHILD_DELETE, kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_delete_view_only_own_child(self):
        self.client.login(email=TEST_PARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.post(
            reverse(URL_CHILD_DELETE, kwargs={"pk": self.other_child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_view_deletes_child(self):
        self.client.login(email=TEST_PARENT_EMAIL, password=TEST_PASSWORD)
        child_pk = self.child.pk
        response = self.client.post(reverse(URL_CHILD_DELETE, kwargs={"pk": child_pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Child.objects.filter(pk=child_pk).exists())


class ChildShareModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="owner",
            email=TEST_OWNER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.shared_user = get_user_model().objects.create_user(
            username="shared",
            email=TEST_SHARED_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_childshare_creation(self):
        share = ChildShare.objects.create(
            child=self.child,
            user=self.shared_user,
            role=ChildShare.Role.CO_PARENT,
            created_by=self.owner,
        )
        self.assertEqual(share.child, self.child)
        self.assertEqual(share.user, self.shared_user)
        self.assertEqual(share.role, ChildShare.Role.CO_PARENT)

    def test_childshare_str(self):
        share = ChildShare.objects.create(
            child=self.child,
            user=self.shared_user,
            role=ChildShare.Role.CO_PARENT,
        )
        self.assertIn(self.shared_user.email, str(share))
        self.assertIn(self.child.name, str(share))

    def test_childshare_unique_together(self):
        ChildShare.objects.create(
            child=self.child,
            user=self.shared_user,
            role=ChildShare.Role.CO_PARENT,
        )
        with self.assertRaises(Exception):
            ChildShare.objects.create(
                child=self.child,
                user=self.shared_user,
                role=ChildShare.Role.CAREGIVER,
            )

    def test_childshare_cascade_delete_child(self):
        ChildShare.objects.create(
            child=self.child,
            user=self.shared_user,
            role=ChildShare.Role.CO_PARENT,
        )
        self.child.delete()
        self.assertEqual(ChildShare.objects.count(), 0)

    def test_childshare_cascade_delete_user(self):
        share_user = get_user_model().objects.create_user(
            username="temp",
            email="temp@example.com",
            password=TEST_PASSWORD,
        )
        share = ChildShare.objects.create(
            child=self.child,
            user=share_user,
            role=ChildShare.Role.CO_PARENT,
        )
        share_pk = share.pk
        share_user.delete()
        # Verify share was deleted via cascade
        self.assertFalse(ChildShare.objects.filter(pk=share_pk).exists())


class ShareInviteModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="owner",
            email=TEST_OWNER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_shareinvite_creation(self):
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        self.assertEqual(invite.child, self.child)
        self.assertEqual(invite.role, ChildShare.Role.CAREGIVER)
        self.assertTrue(invite.is_active)

    def test_shareinvite_token_auto_generated(self):
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        self.assertIsNotNone(invite.token)
        self.assertGreater(len(invite.token), 20)

    def test_shareinvite_token_unique(self):
        invite1 = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        invite2 = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CO_PARENT,
            created_by=self.owner,
        )
        self.assertNotEqual(invite1.token, invite2.token)

    def test_shareinvite_str(self):
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        self.assertIn(self.child.name, str(invite))


class ChildSharingMethodTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="owner",
            email=TEST_OWNER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.coparent = get_user_model().objects.create_user(
            username="coparent",
            email=TEST_COPARENT_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.caregiver = get_user_model().objects.create_user(
            username="caregiver",
            email=TEST_CAREGIVER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.stranger = get_user_model().objects.create_user(
            username="stranger",
            email="stranger@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )
        ChildShare.objects.create(
            child=cls.child,
            user=cls.coparent,
            role=ChildShare.Role.CO_PARENT,
        )
        ChildShare.objects.create(
            child=cls.child,
            user=cls.caregiver,
            role=ChildShare.Role.CAREGIVER,
        )

    def test_has_access_owner(self):
        self.assertTrue(self.child.has_access(self.owner))

    def test_has_access_coparent(self):
        self.assertTrue(self.child.has_access(self.coparent))

    def test_has_access_caregiver(self):
        self.assertTrue(self.child.has_access(self.caregiver))

    def test_has_access_stranger(self):
        self.assertFalse(self.child.has_access(self.stranger))

    def test_get_user_role_owner(self):
        self.assertEqual(self.child.get_user_role(self.owner), "owner")

    def test_get_user_role_coparent(self):
        self.assertEqual(self.child.get_user_role(self.coparent), "co-parent")

    def test_get_user_role_caregiver(self):
        self.assertEqual(self.child.get_user_role(self.caregiver), "caregiver")

    def test_get_user_role_stranger(self):
        self.assertIsNone(self.child.get_user_role(self.stranger))

    def test_can_edit_owner(self):
        self.assertTrue(self.child.can_edit(self.owner))

    def test_can_edit_coparent(self):
        self.assertTrue(self.child.can_edit(self.coparent))

    def test_can_edit_caregiver(self):
        self.assertFalse(self.child.can_edit(self.caregiver))

    def test_can_edit_stranger(self):
        self.assertFalse(self.child.can_edit(self.stranger))

    def test_can_manage_sharing_owner(self):
        self.assertTrue(self.child.can_manage_sharing(self.owner))

    def test_can_manage_sharing_coparent(self):
        self.assertFalse(self.child.can_manage_sharing(self.coparent))

    def test_can_manage_sharing_caregiver(self):
        self.assertFalse(self.child.can_manage_sharing(self.caregiver))

    def test_for_user_owner(self):
        children = Child.for_user(self.owner)
        self.assertIn(self.child, children)

    def test_for_user_coparent(self):
        children = Child.for_user(self.coparent)
        self.assertIn(self.child, children)

    def test_for_user_caregiver(self):
        children = Child.for_user(self.caregiver)
        self.assertIn(self.child, children)

    def test_for_user_stranger(self):
        children = Child.for_user(self.stranger)
        self.assertNotIn(self.child, children)


class ChildSharingViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="owner",
            email=TEST_OWNER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.coparent = get_user_model().objects.create_user(
            username="coparent",
            email=TEST_COPARENT_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.other_user = get_user_model().objects.create_user(
            username="other",
            email=TEST_OTHER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_sharing_view_requires_login(self):
        response = self.client.get(
            reverse(URL_CHILD_SHARING, kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_sharing_view_owner_access(self):
        self.client.login(email=TEST_OWNER_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_CHILD_SHARING, kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Share")
        self.assertContains(response, self.child.name)

    def test_sharing_view_non_owner_denied(self):
        self.client.login(email=TEST_OTHER_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_CHILD_SHARING, kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_sharing_view_coparent_denied(self):
        ChildShare.objects.create(
            child=self.child,
            user=self.coparent,
            role=ChildShare.Role.CO_PARENT,
        )
        self.client.login(email=TEST_COPARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_CHILD_SHARING, kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 404)


class CreateInviteViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="owner",
            email=TEST_OWNER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.other_user = get_user_model().objects.create_user(
            username="other",
            email=TEST_OTHER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_create_invite_owner(self):
        self.client.login(email=TEST_OWNER_EMAIL, password=TEST_PASSWORD)
        response = self.client.post(
            reverse(URL_CREATE_INVITE, kwargs={"pk": self.child.pk}),
            {"role": ChildShare.Role.CAREGIVER},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ShareInvite.objects.count(), 1)
        invite = ShareInvite.objects.first()
        self.assertEqual(invite.child, self.child)
        self.assertEqual(invite.role, ChildShare.Role.CAREGIVER)

    def test_create_invite_coparent_role(self):
        self.client.login(email=TEST_OWNER_EMAIL, password=TEST_PASSWORD)
        self.client.post(
            reverse(URL_CREATE_INVITE, kwargs={"pk": self.child.pk}),
            {"role": ChildShare.Role.CO_PARENT},
        )
        invite = ShareInvite.objects.first()
        self.assertEqual(invite.role, ChildShare.Role.CO_PARENT)

    def test_create_invite_non_owner_denied(self):
        self.client.login(email=TEST_OTHER_EMAIL, password=TEST_PASSWORD)
        response = self.client.post(
            reverse(URL_CREATE_INVITE, kwargs={"pk": self.child.pk}),
            {"role": ChildShare.Role.CAREGIVER},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ShareInvite.objects.count(), 0)

    def test_create_invite_invalid_role_defaults_to_caregiver(self):
        self.client.login(email=TEST_OWNER_EMAIL, password=TEST_PASSWORD)
        self.client.post(
            reverse(URL_CREATE_INVITE, kwargs={"pk": self.child.pk}),
            {"role": "INVALID"},
        )
        invite = ShareInvite.objects.first()
        self.assertEqual(invite.role, ChildShare.Role.CAREGIVER)


class AcceptInviteViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="owner",
            email=TEST_OWNER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.new_user = get_user_model().objects.create_user(
            username="newuser",
            email=TEST_NEW_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_accept_invite_requires_login(self):
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        response = self.client.get(
            reverse(URL_ACCEPT_INVITE, kwargs={"token": invite.token})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts/login", response.url)

    def test_accept_invite_creates_share(self):
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        self.client.login(email=TEST_NEW_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_ACCEPT_INVITE, kwargs={"token": invite.token})
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ChildShare.objects.filter(child=self.child, user=self.new_user).exists()
        )
        share = ChildShare.objects.get(child=self.child, user=self.new_user)
        self.assertEqual(share.role, ChildShare.Role.CAREGIVER)

    def test_accept_invite_coparent_role(self):
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CO_PARENT,
            created_by=self.owner,
        )
        self.client.login(email=TEST_NEW_EMAIL, password=TEST_PASSWORD)
        self.client.get(reverse(URL_ACCEPT_INVITE, kwargs={"token": invite.token}))
        share = ChildShare.objects.get(child=self.child, user=self.new_user)
        self.assertEqual(share.role, ChildShare.Role.CO_PARENT)

    def test_accept_invite_owner_rejected(self):
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        self.client.login(email=TEST_OWNER_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_ACCEPT_INVITE, kwargs={"token": invite.token})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ChildShare.objects.filter(child=self.child, user=self.owner).exists()
        )

    def test_accept_invite_already_shared(self):
        ChildShare.objects.create(
            child=self.child,
            user=self.new_user,
            role=ChildShare.Role.CAREGIVER,
        )
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CO_PARENT,
            created_by=self.owner,
        )
        self.client.login(email=TEST_NEW_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_ACCEPT_INVITE, kwargs={"token": invite.token})
        )
        self.assertEqual(response.status_code, 302)
        # Should not change role since already shared
        share = ChildShare.objects.get(child=self.child, user=self.new_user)
        self.assertEqual(share.role, ChildShare.Role.CAREGIVER)

    def test_accept_invite_inactive_denied(self):
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
            is_active=False,
        )
        self.client.login(email=TEST_NEW_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_ACCEPT_INVITE, kwargs={"token": invite.token})
        )
        self.assertEqual(response.status_code, 404)

    def test_accept_invite_invalid_token(self):
        self.client.login(email=TEST_NEW_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_ACCEPT_INVITE, kwargs={"token": "invalid-token"})
        )
        self.assertEqual(response.status_code, 404)


class RevokeAccessViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="owner",
            email=TEST_OWNER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.shared_user = get_user_model().objects.create_user(
            username="shared",
            email=TEST_SHARED_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_revoke_access_owner(self):
        share = ChildShare.objects.create(
            child=self.child,
            user=self.shared_user,
            role=ChildShare.Role.CAREGIVER,
        )
        self.client.login(email=TEST_OWNER_EMAIL, password=TEST_PASSWORD)
        response = self.client.post(
            reverse(
                "children:revoke_access",
                kwargs={"pk": self.child.pk, "share_pk": share.pk},
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ChildShare.objects.filter(pk=share.pk).exists())

    def test_revoke_access_non_owner_denied(self):
        share = ChildShare.objects.create(
            child=self.child,
            user=self.shared_user,
            role=ChildShare.Role.CAREGIVER,
        )
        self.client.login(email=TEST_SHARED_EMAIL, password=TEST_PASSWORD)
        response = self.client.post(
            reverse(
                "children:revoke_access",
                kwargs={"pk": self.child.pk, "share_pk": share.pk},
            )
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ChildShare.objects.filter(pk=share.pk).exists())


class ToggleInviteViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="owner",
            email=TEST_OWNER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_toggle_invite_deactivate(self):
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
            is_active=True,
        )
        self.client.login(email=TEST_OWNER_EMAIL, password=TEST_PASSWORD)
        response = self.client.post(
            reverse(
                "children:toggle_invite",
                kwargs={"pk": self.child.pk, "invite_pk": invite.pk},
            )
        )
        self.assertEqual(response.status_code, 302)
        invite.refresh_from_db()
        self.assertFalse(invite.is_active)

    def test_toggle_invite_activate(self):
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
            is_active=False,
        )
        self.client.login(email=TEST_OWNER_EMAIL, password=TEST_PASSWORD)
        self.client.post(
            reverse(
                "children:toggle_invite",
                kwargs={"pk": self.child.pk, "invite_pk": invite.pk},
            )
        )
        invite.refresh_from_db()
        self.assertTrue(invite.is_active)


class DeleteInviteViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="owner",
            email=TEST_OWNER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.other_user = get_user_model().objects.create_user(
            username="other",
            email=TEST_OTHER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_delete_invite_owner(self):
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        self.client.login(email=TEST_OWNER_EMAIL, password=TEST_PASSWORD)
        response = self.client.post(
            reverse(
                "children:delete_invite",
                kwargs={"pk": self.child.pk, "invite_pk": invite.pk},
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ShareInvite.objects.filter(pk=invite.pk).exists())

    def test_delete_invite_non_owner_denied(self):
        invite = ShareInvite.objects.create(
            child=self.child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        self.client.login(email=TEST_OTHER_EMAIL, password=TEST_PASSWORD)
        response = self.client.post(
            reverse(
                "children:delete_invite",
                kwargs={"pk": self.child.pk, "invite_pk": invite.pk},
            )
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ShareInvite.objects.filter(pk=invite.pk).exists())


class SharedChildListViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="owner",
            email=TEST_OWNER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.coparent = get_user_model().objects.create_user(
            username="coparent",
            email=TEST_COPARENT_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.caregiver = get_user_model().objects.create_user(
            username="caregiver",
            email=TEST_CAREGIVER_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.owner,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )
        ChildShare.objects.create(
            child=cls.child,
            user=cls.coparent,
            role=ChildShare.Role.CO_PARENT,
        )
        ChildShare.objects.create(
            child=cls.child,
            user=cls.caregiver,
            role=ChildShare.Role.CAREGIVER,
        )

    def test_shared_child_appears_in_coparent_list(self):
        self.client.login(email=TEST_COPARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(reverse(URL_CHILD_LIST))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, TEST_BABY_NAME)
        self.assertContains(response, "Co-parent")

    def test_shared_child_appears_in_caregiver_list(self):
        self.client.login(email=TEST_CAREGIVER_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(reverse(URL_CHILD_LIST))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, TEST_BABY_NAME)
        self.assertContains(response, "Caregiver")

    def test_coparent_can_edit_child(self):
        self.client.login(email=TEST_COPARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_CHILD_EDIT, kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_child_edit_context_has_notification_preference(self):
        """Child edit page includes notification preference form when editing."""
        self.client.login(email=TEST_OWNER_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_CHILD_EDIT, kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("notification_preference", response.context)
        self.assertIn("notification_preference_form", response.context)
        self.assertContains(response, "Notification alerts")

    def test_child_edit_post_notification_preference_invalid_rerenders_form(self):
        """Invalid notification preference form re-renders edit page with form errors."""
        from unittest.mock import patch

        self.client.login(email=TEST_OWNER_EMAIL, password=TEST_PASSWORD)
        # Ensure pref exists (GET edit page)
        self.client.get(reverse(URL_CHILD_EDIT, kwargs={"pk": self.child.pk}))
        with patch(
            "notifications.forms.NotificationPreferenceForm.is_valid",
            return_value=False,
        ):
            response = self.client.post(
                reverse(URL_CHILD_EDIT, kwargs={"pk": self.child.pk}),
                {"action": "notification_preference"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("notification_preference_form", response.context)

    def test_child_edit_post_notification_preference_no_pref_redirects_to_list(self):
        """When user has no NotificationPreference for child, POST redirects to child list."""
        from notifications.models import NotificationPreference

        # Use a coparent who has never loaded edit page (no pref). Create fresh child + user.
        coparent2 = get_user_model().objects.create_user(
            username="coparent2",
            email="coparent2@example.com",
            password=TEST_PASSWORD,
        )
        child2 = Child.objects.create(
            parent=self.owner,
            name="Baby No Pref",
            date_of_birth=date(2025, 1, 1),
        )
        ChildShare.objects.create(
            child=child2,
            user=coparent2,
            role=ChildShare.Role.CO_PARENT,
            created_by=self.owner,
        )
        self.assertFalse(
            NotificationPreference.objects.filter(user=coparent2, child=child2).exists()
        )
        self.client.login(email="coparent2@example.com", password=TEST_PASSWORD)
        response = self.client.post(
            reverse(URL_CHILD_EDIT, kwargs={"pk": child2.pk}),
            {"action": "notification_preference"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse(URL_CHILD_LIST))

    def test_child_edit_post_notification_preference_valid_redirects_with_saved(self):
        """Valid notification preference save redirects with notifications_saved=1."""
        self.client.login(email=TEST_OWNER_EMAIL, password=TEST_PASSWORD)
        self.client.get(reverse(URL_CHILD_EDIT, kwargs={"pk": self.child.pk}))
        response = self.client.post(
            reverse(URL_CHILD_EDIT, kwargs={"pk": self.child.pk}),
            {
                "action": "notification_preference",
                "notify_feedings": "on",
                "notify_diapers": "on",
                "notify_naps": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("notifications_saved=1", response["Location"])

    def test_caregiver_cannot_edit_child(self):
        self.client.login(email=TEST_CAREGIVER_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_CHILD_EDIT, kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_coparent_cannot_delete_child(self):
        self.client.login(email=TEST_COPARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.post(
            reverse(URL_CHILD_DELETE, kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_caregiver_cannot_delete_child(self):
        self.client.login(email=TEST_CAREGIVER_EMAIL, password=TEST_PASSWORD)
        response = self.client.post(
            reverse(URL_CHILD_DELETE, kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_share_button_not_on_child_list(self):
        """Child list does not show share icon; sharing is from child dashboard."""
        self.client.login(email=TEST_OWNER_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(reverse(URL_CHILD_LIST))
        self.assertNotContains(response, "fa-share-nodes")

    def test_share_button_hidden_for_coparent(self):
        self.client.login(email=TEST_COPARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(reverse(URL_CHILD_LIST))
        self.assertNotContains(response, "fa-share-nodes")

    def test_child_list_has_no_cache_headers(self):
        """Verify child list response has cache-control headers to prevent browser caching.

        Browser caching (especially BFCache - Back/Forward Cache) can cause
        users to see stale "Last Activity" timestamps after logging tracking
        records. These headers force browsers to always fetch fresh HTML.
        """
        self.client.login(email=TEST_OWNER_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(reverse(URL_CHILD_LIST))
        self.assertEqual(response.status_code, 200)

        # Verify cache-control headers prevent browser caching
        self.assertEqual(
            response["Cache-Control"], "no-cache, no-store, must-revalidate"
        )
        self.assertEqual(response["Pragma"], "no-cache")
        self.assertEqual(response["Expires"], "0")


class ChildFormFutureDateTests(TestCase):
    """Test ChildForm future date of birth validation."""

    def test_future_date_of_birth_rejected(self):
        """Date of birth in the future is rejected."""
        future_date = (timezone.now() + timedelta(days=30)).date()
        form = ChildForm(
            data={
                "name": "Future Baby",
                "date_of_birth": future_date.isoformat(),
                "gender": "F",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("date_of_birth", form.errors)


class LocalDateTimeFormMixinTests(TestCase):
    """Test LocalDateTimeFormMixin timezone conversion and future validation."""

    def test_initial_datetime_set_to_now_when_no_instance(self):
        """Create form with request and no instance sets initial to now in user TZ."""
        from django import forms as django_forms
        from django.test import RequestFactory

        class TestForm(LocalDateTimeFormMixin, django_forms.Form):
            datetime_field_name = "test_dt"
            test_dt = django_forms.DateTimeField()

        user = get_user_model().objects.create_user(
            username="tzinitial",
            email="tzinitial@example.com",
            password=TEST_PASSWORD,
            timezone="America/New_York",
        )
        request = RequestFactory().get("/")
        request.user = user
        form = TestForm(request=request)
        self.assertIn("test_dt", form.initial)
        self.assertIsNotNone(form.initial["test_dt"])

    def test_mixin_early_return_when_no_datetime_field_name(self):
        """When datetime_field_name is None, __init__ returns without setting initial."""
        from django import forms as django_forms
        from django.test import RequestFactory

        class NoFieldForm(LocalDateTimeFormMixin, django_forms.Form):
            datetime_field_name = None

        request = RequestFactory().get("/")
        request.user = get_user_model().objects.create_user(
            username="nofield",
            email="nofield@example.com",
            password=TEST_PASSWORD,
            timezone="UTC",
        )
        form = NoFieldForm(request=request)
        self.assertEqual(form.initial, {})

    def test_future_utc_datetime_rejected(self):
        """Datetime in the future (in user TZ) is rejected."""
        from django import forms as django_forms
        from django.test import RequestFactory

        class TestForm(LocalDateTimeFormMixin, django_forms.Form):
            datetime_field_name = "test_dt"
            test_dt = django_forms.DateTimeField()

        user = get_user_model().objects.create_user(
            username="utcfuture",
            email="utcfuture@example.com",
            password=TEST_PASSWORD,
            timezone="UTC",
        )
        request = RequestFactory().get("/")
        request.user = user
        future_local = timezone.now() + timedelta(hours=2)
        form = TestForm(
            request=request,
            data={
                "test_dt": future_local.strftime("%Y-%m-%dT%H:%M"),
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn("test_dt", form.errors)


class AcceptInviteViewRaceConditionTests(TestCase):
    """Test AcceptInviteView IntegrityError handling in web UI."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="raceowner2",
            email="raceowner2@example.com",
            password=TEST_PASSWORD,
        )
        cls.acceptor = get_user_model().objects.create_user(
            username="raceacceptor2",
            email="raceacceptor2@example.com",
            password=TEST_PASSWORD,
        )

    def test_accept_invite_integrity_error_handled(self):
        """IntegrityError during web accept invite is handled gracefully."""
        child = Child.objects.create(
            parent=self.owner,
            name="Race Baby 2",
            date_of_birth=date(2025, 1, 1),
        )
        invite = ShareInvite.objects.create(
            child=child,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )
        # Pre-create the share (simulating race condition)
        ChildShare.objects.create(
            child=child,
            user=self.acceptor,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.owner,
        )

        self.client.login(email="raceacceptor2@example.com", password=TEST_PASSWORD)

        # Mock get_or_create to raise IntegrityError
        with patch.object(
            ChildShare.objects,
            "get_or_create",
            side_effect=IntegrityError("duplicate key"),
        ):
            response = self.client.get(
                reverse("children:accept_invite", kwargs={"token": invite.token})
            )

        # Should redirect (302) without crashing
        self.assertEqual(response.status_code, 302)


class ChildDashboardViewTests(TestCase):
    """Tests for child dashboard (template parity)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="dashboarduser",
            email="dashboard@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(
            reverse("children:child_dashboard", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_dashboard_200_for_owner(self):
        self.client.login(email="dashboard@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_dashboard", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("today_summary", response.context)
        self.assertIn("recent_activities", response.context)
        self.assertIn("pattern_alerts", response.context)
        self.assertTrue(response.context["can_manage_sharing"])

    def test_dashboard_404_for_no_access(self):
        other = get_user_model().objects.create_user(
            username="other",
            email="other@example.com",
            password=TEST_PASSWORD,
        )
        self.client.login(email="other@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_dashboard", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_dashboard_recent_activities_includes_nap_duration_display(self):
        """Dashboard recent_activities includes naps with duration_display when ended_at set."""
        from diapers.models import DiaperChange
        from feedings.models import Feeding
        from naps.models import Nap

        now = timezone.now()
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=now,
            amount_oz=4.0,
        )
        DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=now,
        )
        Nap.objects.create(
            child=self.child,
            napped_at=now - timedelta(hours=1),
            ended_at=now,
        )
        self.client.login(email="dashboard@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_dashboard", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)
        activities = response.context["recent_activities"]
        self.assertGreater(len(activities), 0)
        nap_activities = [a for a in activities if a.get("type") == "nap"]
        if nap_activities:
            self.assertIn("duration_display", nap_activities[0].get("obj", {}))


class ChildAdvancedViewTests(TestCase):
    """Tests for advanced tools hub (template parity)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="advanceduser",
            email="advanced@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_advanced_requires_login(self):
        response = self.client.get(
            reverse("children:child_advanced", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_advanced_200_for_owner(self):
        self.client.login(email="advanced@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_advanced", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["child"], self.child)
        self.assertTrue(response.context["can_manage_sharing"])

    def test_advanced_404_for_no_access(self):
        other = get_user_model().objects.create_user(
            username="otheradv",
            email="otheradv@example.com",
            password=TEST_PASSWORD,
        )
        self.client.login(email="otheradv@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_advanced", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 404)


class ChildPediatricianSummaryViewTests(TestCase):
    """Tests for pediatrician summary (template parity)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="peduser",
            email="ped@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_pediatrician_summary_requires_login(self):
        response = self.client.get(
            reverse(
                "children:child_pediatrician_summary",
                kwargs={"pk": self.child.pk},
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_pediatrician_summary_200_for_owner(self):
        self.client.login(email="ped@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse(
                "children:child_pediatrician_summary",
                kwargs={"pk": self.child.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["child"], self.child)
        self.assertIn("summary", response.context)
        self.assertIn("feedings_per_day", response.context)


class ChildTimelineViewTests(TestCase):
    """Tests for child timeline (template parity)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="timelineuser",
            email="timeline@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_timeline_requires_login(self):
        response = self.client.get(
            reverse("children:child_timeline", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_timeline_200_for_owner(self):
        self.client.login(email="timeline@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_timeline", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("page_obj", response.context)

    def test_timeline_date_header_uses_user_timezone_at_utc_midnight_boundary(self):
        """Timeline date headers use the user's timezone, not UTC (midnight boundary).

        An event at 04:00 UTC is 23:00 previous day in America/New_York. It must
        appear under the user's local date (e.g. Sunday, Feb 25), not UTC date
        (Thursday, Feb 26).
        """
        from feedings.models import Feeding

        self.user.timezone = "America/New_York"
        self.user.save(update_fields=["timezone"])

        # 04:00 UTC on 2024-02-26 = 23:00 ET on 2024-02-25 (Sunday)
        fed_at_utc = datetime(2024, 2, 26, 4, 0, 0, tzinfo=ZoneInfo("UTC"))
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=fed_at_utc,
            amount_oz=4.0,
        )

        self.client.login(email="timeline@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_timeline", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()
        # User's local date: Sunday, Feb 25 (not UTC Thursday, Feb 26)
        self.assertIn("Sunday, Feb 25", content)
        self.assertNotIn("Thursday, Feb 26", content)

    def test_timeline_nap_with_ended_at_has_duration_display(self):
        """Timeline includes nap duration_display when nap has ended_at."""
        from naps.models import Nap

        now = timezone.now()
        Nap.objects.create(
            child=self.child,
            napped_at=now - timedelta(hours=1),
            ended_at=now,
        )
        self.client.login(email="timeline@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_timeline", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertGreater(len(page_obj.object_list), 0)
        nap_items = [x for x in page_obj.object_list if x.get("type") == "nap"]
        self.assertEqual(len(nap_items), 1)
        self.assertIn("duration_display", nap_items[0]["obj"])

    def test_timeline_includes_diaper_and_nap_in_merged_list(self):
        """Timeline merge loop includes both diaper and nap when present."""
        from diapers.models import DiaperChange
        from naps.models import Nap

        now = timezone.now()
        DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=now,
        )
        Nap.objects.create(
            child=self.child,
            napped_at=now - timedelta(hours=1),
            ended_at=now,
        )
        self.client.login(email="timeline@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_timeline", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        types = [x.get("type") for x in page_obj.object_list]
        self.assertIn("diaper", types)
        self.assertIn("nap", types)


class ChildAnalyticsViewTests(TestCase):
    """Tests for child analytics (template parity)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="analyticsuser",
            email="analytics@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_analytics_requires_login(self):
        response = self.client.get(
            reverse("children:child_analytics", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_analytics_200_with_days_param(self):
        self.client.login(email="analytics@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_analytics", kwargs={"pk": self.child.pk}),
            {"days": "7"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["days"], 7)
        self.assertIn("feeding_trends", response.context)

    def test_analytics_invalid_days_defaults_to_30(self):
        """days not in (7, 14, 30) falls back to 30."""
        self.client.login(email="analytics@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_analytics", kwargs={"pk": self.child.pk}),
            {"days": "99"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["days"], 30)


class ChildExportViewTests(TestCase):
    """Tests for child export (template parity)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="exportuser",
            email="export@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_export_get_200(self):
        self.client.login(email="export@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_export", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_export_post_csv_returns_attachment(self):
        self.client.login(email="export@example.com", password=TEST_PASSWORD)
        response = self.client.post(
            reverse("children:child_export", kwargs={"pk": self.child.pk}),
            {"format": "csv", "days": "30"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment", response["Content-Disposition"])

    def test_export_post_invalid_days_defaults_to_30(self):
        """Invalid days (non-int or not 7/14/30) uses 30."""
        self.client.login(email="export@example.com", password=TEST_PASSWORD)
        response = self.client.post(
            reverse("children:child_export", kwargs={"pk": self.child.pk}),
            {"format": "csv", "days": "abc"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")

    def test_export_post_days_99_defaults_to_30(self):
        """days=99 not in (7,14,30) falls back to 30."""
        self.client.login(email="export@example.com", password=TEST_PASSWORD)
        response = self.client.post(
            reverse("children:child_export", kwargs={"pk": self.child.pk}),
            {"format": "csv", "days": "99"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")

    def test_export_post_pdf_redirects_to_status(self):
        self.client.login(email="export@example.com", password=TEST_PASSWORD)
        response = self.client.post(
            reverse("children:child_export", kwargs={"pk": self.child.pk}),
            {"format": "pdf", "days": "30"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("export/status/", response["Location"])

    def test_export_post_invalid_format_warning_and_redirect(self):
        """Invalid format shows warning and redirects back to export page."""
        from django.contrib.messages import get_messages

        self.client.login(email="export@example.com", password=TEST_PASSWORD)
        response = self.client.post(
            reverse("children:child_export", kwargs={"pk": self.child.pk}),
            {"format": "invalid", "days": "30"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("children:child_export", kwargs={"pk": self.child.pk}),
        )
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(
            any("CSV" in str(m) and "PDF" in str(m) for m in messages),
            msg="Expected warning about choosing CSV or PDF",
        )


class ChildCatchUpViewTests(TestCase):
    """Tests for child catch-up (template parity)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="catchupuser",
            email="catchup@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_catchup_requires_login(self):
        response = self.client.get(
            reverse("children:child_catchup", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_catchup_200_with_default_dates(self):
        self.client.login(email="catchup@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_catchup", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("events", response.context)
        self.assertIn("start", response.context)
        self.assertIn("end", response.context)

    def test_catchup_invalid_date_range_uses_defaults(self):
        """Invalid or missing start/end params use default last-7-days range."""
        self.client.login(email="catchup@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_catchup", kwargs={"pk": self.child.pk}),
            {"start": "not-a-date", "end": "also-bad"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("events", response.context)
        self.assertIn("start", response.context)
        self.assertIn("end", response.context)

    def test_catchup_valid_date_range_uses_params(self):
        """Valid start/end query params are used for date range."""
        self.client.login(email="catchup@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_catchup", kwargs={"pk": self.child.pk}),
            {"start": "2025-01-01", "end": "2025-01-07"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["start"], "2025-01-01")
        self.assertEqual(response.context["end"], "2025-01-07")

    def test_catchup_events_include_nap_duration_display(self):
        """Catch-up events include nap duration_display when ended_at set."""
        from naps.models import Nap

        now = timezone.now()
        Nap.objects.create(
            child=self.child,
            napped_at=now - timedelta(hours=1),
            ended_at=now,
        )
        self.client.login(email="catchup@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_catchup", kwargs={"pk": self.child.pk}),
            {
                "start": (now.date() - timedelta(days=1)).isoformat(),
                "end": (now.date() + timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        events = response.context["events"]
        nap_events = [e for e in events if e["type"] == "nap"]
        self.assertEqual(len(nap_events), 1)
        self.assertIn("duration_display", nap_events[0]["obj"])

    def test_catchup_events_include_diaper_and_nap(self):
        """Catch-up events list includes both diaper and nap when present in range."""
        from diapers.models import DiaperChange
        from naps.models import Nap

        now = timezone.now()
        DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=now,
        )
        Nap.objects.create(
            child=self.child,
            napped_at=now - timedelta(hours=1),
            ended_at=now,
        )
        self.client.login(email="catchup@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_catchup", kwargs={"pk": self.child.pk}),
            {
                "start": (now.date() - timedelta(days=1)).isoformat(),
                "end": (now.date() + timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        events = response.context["events"]
        types = [e["type"] for e in events]
        self.assertIn("diaper", types)
        self.assertIn("nap", types)

    def test_catchup_events_include_feedings_in_range(self):
        """Catch-up events list includes feedings when present in date range."""
        from feedings.models import Feeding

        now = timezone.now()
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=now,
            amount_oz=4.0,
        )
        self.client.login(email="catchup@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse("children:child_catchup", kwargs={"pk": self.child.pk}),
            {
                "start": (now.date() - timedelta(days=1)).isoformat(),
                "end": (now.date() + timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        events = response.context["events"]
        feeding_events = [e for e in events if e["type"] == "feeding"]
        self.assertEqual(len(feeding_events), 1)
        self.assertIn("obj", feeding_events[0])


class ChildExportStatusViewTests(TestCase):
    """Tests for PDF export status page."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="statususer",
            email="status@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name=TEST_BABY_NAME,
            date_of_birth=date(2025, 6, 15),
        )

    def test_export_status_200_with_task_id(self):
        """Status page renders with task_id and status in context."""
        self.client.login(email="status@example.com", password=TEST_PASSWORD)
        response = self.client.get(
            reverse(
                "children:child_export_status",
                kwargs={"pk": self.child.pk, "task_id": "fake-task-id"},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("task_id", response.context)
        self.assertEqual(response.context["task_id"], "fake-task-id")
        self.assertIn("status", response.context)

    def test_export_status_successful_task_shows_download(self):
        """When task is successful with dict result, context has filename and download_url."""
        from unittest.mock import MagicMock, patch

        with patch("celery.result.AsyncResult") as mock_async:
            mock_result = MagicMock()
            mock_result.successful.return_value = True
            mock_result.failed.return_value = False
            mock_result.result = {
                "filename": "report.pdf",
                "download_url": "/media/exports/report.pdf",
            }
            mock_async.return_value = mock_result

            self.client.login(email="status@example.com", password=TEST_PASSWORD)
            response = self.client.get(
                reverse(
                    "children:child_export_status",
                    kwargs={"pk": self.child.pk, "task_id": "any-id"},
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context.get("filename"), "report.pdf")
        self.assertEqual(
            response.context.get("download_url"), "/media/exports/report.pdf"
        )

    def test_export_status_failed_task_shows_error(self):
        """When task has failed, context has error message."""
        from unittest.mock import MagicMock, patch

        with patch("celery.result.AsyncResult") as mock_async:
            mock_result = MagicMock()
            mock_result.successful.return_value = False
            mock_result.failed.return_value = True
            mock_result.info = "Worker timeout"
            mock_async.return_value = mock_result

            self.client.login(email="status@example.com", password=TEST_PASSWORD)
            response = self.client.get(
                reverse(
                    "children:child_export_status",
                    kwargs={"pk": self.child.pk, "task_id": "any-id"},
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context.get("error"), "Worker timeout")
