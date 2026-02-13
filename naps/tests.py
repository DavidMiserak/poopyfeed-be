from datetime import date, timedelta

from django.contrib.admin.sites import site as admin_site
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from children.models import Child, ChildShare
from django_project.test_constants import TEST_PASSWORD

from .forms import NapForm
from .models import Nap

TEST_PARENT_EMAIL = "parent@example.com"
URL_NAP_LIST = "naps:nap_list"
URL_NAP_ADD = "naps:nap_add"
URL_NAP_EDIT = "naps:nap_edit"
URL_NAP_DELETE = "naps:nap_delete"


class NapModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="testparent",
            email=TEST_PARENT_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name="Baby Jane",
            date_of_birth=date(2025, 6, 15),
        )

    def test_nap_creation(self):
        nap = Nap.objects.create(
            child=self.child,
            napped_at=timezone.now(),
        )
        self.assertEqual(nap.child, self.child)

    def test_nap_str(self):
        nap = Nap.objects.create(
            child=self.child,
            napped_at=timezone.now(),
        )
        self.assertEqual(str(nap), "Baby Jane - Nap")

    def test_nap_ordering(self):
        first_nap = Nap.objects.create(
            child=self.child,
            napped_at=timezone.now() - timezone.timedelta(hours=2),
        )
        second_nap = Nap.objects.create(
            child=self.child,
            napped_at=timezone.now(),
        )
        naps = list(Nap.objects.all())
        self.assertEqual(naps[0], second_nap)
        self.assertEqual(naps[1], first_nap)

    def test_nap_related_name(self):
        nap = Nap.objects.create(
            child=self.child,
            napped_at=timezone.now(),
        )
        self.assertIn(nap, self.child.naps.all())

    def test_nap_cascade_delete(self):
        Nap.objects.create(
            child=self.child,
            napped_at=timezone.now(),
        )
        nap_count_before = Nap.objects.count()
        self.child.delete()
        self.assertEqual(Nap.objects.count(), nap_count_before - 1)

    def test_nap_timestamps(self):
        nap = Nap.objects.create(
            child=self.child,
            napped_at=timezone.now(),
        )
        self.assertIsNotNone(nap.created_at)
        self.assertIsNotNone(nap.updated_at)

    def test_nap_with_ended_at(self):
        now = timezone.now()
        nap = Nap.objects.create(
            child=self.child,
            napped_at=now,
            ended_at=now + timedelta(hours=1),
        )
        self.assertEqual(nap.ended_at, now + timedelta(hours=1))

    def test_nap_ended_at_nullable(self):
        nap = Nap.objects.create(
            child=self.child,
            napped_at=timezone.now(),
        )
        self.assertIsNone(nap.ended_at)

    def test_duration_minutes_property(self):
        now = timezone.now()
        nap = Nap.objects.create(
            child=self.child,
            napped_at=now,
            ended_at=now + timedelta(minutes=90),
        )
        self.assertAlmostEqual(nap.duration_minutes, 90.0)

    def test_duration_none_without_ended_at(self):
        nap = Nap.objects.create(
            child=self.child,
            napped_at=timezone.now(),
        )
        self.assertIsNone(nap.duration_minutes)

    def test_check_constraint_ended_before_start(self):
        now = timezone.now()
        with self.assertRaises(IntegrityError):
            Nap.objects.create(
                child=self.child,
                napped_at=now,
                ended_at=now - timedelta(hours=1),
            )


class NapAdminTests(TestCase):
    def test_nap_admin_registered(self):
        self.assertIn(Nap, admin_site._registry)


class NapFormTests(TestCase):
    def test_valid_form(self):
        form = NapForm(
            data={
                "napped_at": "2026-02-01T10:30",
            }
        )
        self.assertTrue(form.is_valid())

    def test_invalid_form_missing_napped_at(self):
        form = NapForm(
            data={
                "napped_at": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("napped_at", form.errors)

    def test_form_converts_local_time_to_utc(self):
        form = NapForm(
            data={
                "napped_at": "2026-02-01T14:00",
                "tz_offset": -330,  # UTC+5:30 (IST)
            }
        )
        self.assertTrue(form.is_valid())
        # 14:00 local - 330 minutes = 08:30 UTC
        self.assertEqual(form.cleaned_data["napped_at"].hour, 8)
        self.assertEqual(form.cleaned_data["napped_at"].minute, 30)

    def test_valid_form_with_ended_at(self):
        form = NapForm(
            data={
                "napped_at": "2026-02-01T10:00",
                "ended_at": "2026-02-01T11:30",
            }
        )
        self.assertTrue(form.is_valid())

    def test_form_ended_at_optional(self):
        form = NapForm(
            data={
                "napped_at": "2026-02-01T10:00",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertIsNone(form.cleaned_data.get("ended_at"))

    def test_form_ended_at_before_napped_at_invalid(self):
        form = NapForm(
            data={
                "napped_at": "2026-02-01T12:00",
                "ended_at": "2026-02-01T10:00",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("ended_at", form.errors)

    def test_form_converts_ended_at_to_utc(self):
        form = NapForm(
            data={
                "napped_at": "2026-02-01T14:00",
                "ended_at": "2026-02-01T15:30",
                "tz_offset": -330,  # UTC+5:30 (IST)
            }
        )
        self.assertTrue(form.is_valid())
        # 15:30 local - 330 minutes = 10:00 UTC
        self.assertEqual(form.cleaned_data["ended_at"].hour, 10)
        self.assertEqual(form.cleaned_data["ended_at"].minute, 0)


class NapViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="testparent",
            email=TEST_PARENT_EMAIL,
            password=TEST_PASSWORD,
        )
        cls.other_user = get_user_model().objects.create_user(
            username="otherparent",
            email="other@example.com",
            password=TEST_PASSWORD,
        )
        cls.child = Child.objects.create(
            parent=cls.user,
            name="Baby Jane",
            date_of_birth=date(2025, 6, 15),
        )
        cls.other_child = Child.objects.create(
            parent=cls.other_user,
            name="Other Baby",
            date_of_birth=date(2025, 1, 1),
        )
        cls.nap = Nap.objects.create(
            child=cls.child,
            napped_at=timezone.now(),
        )

    def test_nap_list_requires_login(self):
        response = self.client.get(
            reverse(URL_NAP_LIST, kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_nap_list_only_own_child(self):
        self.client.login(email=TEST_PARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_NAP_LIST, kwargs={"child_pk": self.other_child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_nap_list_shows_naps(self):
        self.client.login(email=TEST_PARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_NAP_LIST, kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nap")

    def test_nap_create_requires_login(self):
        response = self.client.get(
            reverse(URL_NAP_ADD, kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_nap_create_only_own_child(self):
        self.client.login(email=TEST_PARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_NAP_ADD, kwargs={"child_pk": self.other_child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_nap_create_adds_nap(self):
        self.client.login(email=TEST_PARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.post(
            reverse(URL_NAP_ADD, kwargs={"child_pk": self.child.pk}),
            {"napped_at": "2026-02-01T14:00"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Nap.objects.filter(child=self.child).count(), 2)

    def test_nap_edit_requires_login(self):
        response = self.client.get(
            reverse(URL_NAP_EDIT, kwargs={"child_pk": self.child.pk, "pk": self.nap.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_nap_edit_only_own_nap(self):
        self.client.login(email=TEST_PARENT_EMAIL, password=TEST_PASSWORD)
        other_nap = Nap.objects.create(
            child=self.other_child,
            napped_at=timezone.now(),
        )
        response = self.client.get(
            reverse(
                URL_NAP_EDIT,
                kwargs={"child_pk": self.other_child.pk, "pk": other_nap.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_nap_edit_updates_nap(self):
        self.client.login(email=TEST_PARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.post(
            reverse(
                URL_NAP_EDIT, kwargs={"child_pk": self.child.pk, "pk": self.nap.pk}
            ),
            {"napped_at": "2026-02-01T15:00"},
        )
        self.assertEqual(response.status_code, 302)
        self.nap.refresh_from_db()
        self.assertEqual(self.nap.napped_at.hour, 15)

    def test_nap_delete_requires_login(self):
        response = self.client.get(
            reverse(
                URL_NAP_DELETE, kwargs={"child_pk": self.child.pk, "pk": self.nap.pk}
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_nap_delete_only_own_nap(self):
        self.client.login(email=TEST_PARENT_EMAIL, password=TEST_PASSWORD)
        other_nap = Nap.objects.create(
            child=self.other_child,
            napped_at=timezone.now(),
        )
        response = self.client.post(
            reverse(
                URL_NAP_DELETE,
                kwargs={"child_pk": self.other_child.pk, "pk": other_nap.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_nap_delete_deletes_nap(self):
        self.client.login(email=TEST_PARENT_EMAIL, password=TEST_PASSWORD)
        nap_pk = self.nap.pk
        response = self.client.post(
            reverse(URL_NAP_DELETE, kwargs={"child_pk": self.child.pk, "pk": nap_pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Nap.objects.filter(pk=nap_pk).exists())

    def test_nap_edit_get_shows_context(self):
        self.client.login(email=TEST_PARENT_EMAIL, password=TEST_PASSWORD)
        response = self.client.get(
            reverse(URL_NAP_EDIT, kwargs={"child_pk": self.child.pk, "pk": self.nap.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["child"], self.child)

    def test_coparent_can_edit_nap(self):
        coparent = get_user_model().objects.create_user(
            username="coparent",
            email="coparent@example.com",
            password=TEST_PASSWORD,
        )
        ChildShare.objects.create(
            child=self.child,
            user=coparent,
            role=ChildShare.Role.CO_PARENT,
            created_by=self.user,
        )
        self.client.login(email="coparent@example.com", password=TEST_PASSWORD)
        response = self.client.post(
            reverse(
                URL_NAP_EDIT, kwargs={"child_pk": self.child.pk, "pk": self.nap.pk}
            ),
            {"napped_at": "2026-02-01T16:00"},
        )
        self.assertRedirects(
            response,
            reverse(URL_NAP_LIST, kwargs={"child_pk": self.child.pk}),
        )

    def test_coparent_can_delete_nap(self):
        coparent = get_user_model().objects.create_user(
            username="coparent2",
            email="coparent2@example.com",
            password=TEST_PASSWORD,
        )
        ChildShare.objects.create(
            child=self.child,
            user=coparent,
            role=ChildShare.Role.CO_PARENT,
            created_by=self.user,
        )
        nap = Nap.objects.create(
            child=self.child,
            napped_at=timezone.now(),
        )
        self.client.login(email="coparent2@example.com", password=TEST_PASSWORD)
        response = self.client.post(
            reverse(URL_NAP_DELETE, kwargs={"child_pk": self.child.pk, "pk": nap.pk})
        )
        self.assertRedirects(
            response,
            reverse(URL_NAP_LIST, kwargs={"child_pk": self.child.pk}),
        )
