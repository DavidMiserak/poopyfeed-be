from datetime import date

from django.contrib.admin.sites import site as admin_site
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from children.models import Child

from .forms import NapForm
from .models import Nap


class NapModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="testparent",
            email="parent@example.com",
            password="testpass123",
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


class NapViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="testparent",
            email="parent@example.com",
            password="testpass123",
        )
        cls.other_user = get_user_model().objects.create_user(
            username="otherparent",
            email="other@example.com",
            password="testpass123",
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
            reverse("naps:nap_list", kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_nap_list_only_own_child(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.get(
            reverse("naps:nap_list", kwargs={"child_pk": self.other_child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_nap_list_shows_naps(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.get(
            reverse("naps:nap_list", kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nap")

    def test_nap_create_requires_login(self):
        response = self.client.get(
            reverse("naps:nap_add", kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_nap_create_only_own_child(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.get(
            reverse("naps:nap_add", kwargs={"child_pk": self.other_child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_nap_create_adds_nap(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.post(
            reverse("naps:nap_add", kwargs={"child_pk": self.child.pk}),
            {"napped_at": "2026-02-01T14:00"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Nap.objects.filter(child=self.child).count(), 2)

    def test_nap_edit_requires_login(self):
        response = self.client.get(
            reverse(
                "naps:nap_edit", kwargs={"child_pk": self.child.pk, "pk": self.nap.pk}
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_nap_edit_only_own_nap(self):
        self.client.login(email="parent@example.com", password="testpass123")
        other_nap = Nap.objects.create(
            child=self.other_child,
            napped_at=timezone.now(),
        )
        response = self.client.get(
            reverse(
                "naps:nap_edit",
                kwargs={"child_pk": self.other_child.pk, "pk": other_nap.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_nap_edit_updates_nap(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.post(
            reverse(
                "naps:nap_edit", kwargs={"child_pk": self.child.pk, "pk": self.nap.pk}
            ),
            {"napped_at": "2026-02-01T15:00"},
        )
        self.assertEqual(response.status_code, 302)
        self.nap.refresh_from_db()
        self.assertEqual(self.nap.napped_at.hour, 15)

    def test_nap_delete_requires_login(self):
        response = self.client.get(
            reverse(
                "naps:nap_delete", kwargs={"child_pk": self.child.pk, "pk": self.nap.pk}
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_nap_delete_only_own_nap(self):
        self.client.login(email="parent@example.com", password="testpass123")
        other_nap = Nap.objects.create(
            child=self.other_child,
            napped_at=timezone.now(),
        )
        response = self.client.post(
            reverse(
                "naps:nap_delete",
                kwargs={"child_pk": self.other_child.pk, "pk": other_nap.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_nap_delete_deletes_nap(self):
        self.client.login(email="parent@example.com", password="testpass123")
        nap_pk = self.nap.pk
        response = self.client.post(
            reverse("naps:nap_delete", kwargs={"child_pk": self.child.pk, "pk": nap_pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Nap.objects.filter(pk=nap_pk).exists())
