from datetime import date

from django.contrib.admin.sites import site as admin_site
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from children.models import Child

from .forms import DiaperChangeForm
from .models import DiaperChange


class DiaperChangeModelTests(TestCase):
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

    def test_diaper_change_creation(self):
        change = DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.BOTH,
            changed_at=timezone.now(),
        )
        self.assertEqual(change.child, self.child)
        self.assertEqual(change.change_type, "both")

    def test_diaper_change_ordering(self):
        first_change = DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=timezone.now() - timezone.timedelta(hours=2),
        )
        second_change = DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.DIRTY,
            changed_at=timezone.now(),
        )
        changes = list(DiaperChange.objects.all())
        self.assertEqual(changes[0], second_change)
        self.assertEqual(changes[1], first_change)


class DiaperChangeAdminTests(TestCase):
    def test_diaper_change_admin_registered(self):
        self.assertIn(DiaperChange, admin_site._registry)


class DiaperChangeFormTests(TestCase):
    def test_valid_form(self):
        form = DiaperChangeForm(
            data={
                "change_type": DiaperChange.ChangeType.WET,
                "changed_at": "2026-02-01T10:30",
            }
        )
        self.assertTrue(form.is_valid())


class DiaperChangeViewTests(TestCase):
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
        cls.change = DiaperChange.objects.create(
            child=cls.child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=timezone.now(),
        )

    def test_diaper_list_requires_login(self):
        response = self.client.get(
            reverse("diapers:diaper_list", kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_diaper_list_only_own_child(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.get(
            reverse("diapers:diaper_list", kwargs={"child_pk": self.other_child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_diaper_create_requires_login(self):
        response = self.client.get(
            reverse("diapers:diaper_add", kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_diaper_create_adds_change(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.post(
            reverse("diapers:diaper_add", kwargs={"child_pk": self.child.pk}),
            {"change_type": "dirty", "changed_at": "2026-02-01T10:30"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            DiaperChange.objects.filter(
                child=self.child, change_type=DiaperChange.ChangeType.DIRTY
            ).exists()
        )

    def test_diaper_edit_only_own_change(self):
        self.client.login(email="parent@example.com", password="testpass123")
        other_change = DiaperChange.objects.create(
            child=self.other_child,
            change_type=DiaperChange.ChangeType.BOTH,
            changed_at=timezone.now(),
        )
        response = self.client.get(
            reverse(
                "diapers:diaper_edit",
                kwargs={"child_pk": self.other_child.pk, "pk": other_change.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_diaper_delete_only_own_change(self):
        self.client.login(email="parent@example.com", password="testpass123")
        other_change = DiaperChange.objects.create(
            child=self.other_child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=timezone.now(),
        )
        response = self.client.post(
            reverse(
                "diapers:diaper_delete",
                kwargs={"child_pk": self.other_child.pk, "pk": other_change.pk},
            )
        )
        self.assertEqual(response.status_code, 404)
