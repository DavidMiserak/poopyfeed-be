from datetime import date

from django.contrib.admin.sites import site as admin_site
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from children.models import Child, ChildShare

from .forms import DiaperChangeForm
from .models import DiaperChange

TEST_PARENT_EMAIL = "parent@example.com"
TEST_DATETIME = "2026-02-01T10:30"
URL_DIAPER_LIST = "diapers:diaper_list"
URL_DIAPER_EDIT = "diapers:diaper_edit"
URL_DIAPER_DELETE = "diapers:diaper_delete"


class DiaperChangeModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="testparent",
            email=TEST_PARENT_EMAIL,
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

    def test_diaper_change_str(self):
        change = DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=timezone.now(),
        )
        self.assertEqual(str(change), "Baby Jane - Wet")


class DiaperChangeAdminTests(TestCase):
    def test_diaper_change_admin_registered(self):
        self.assertIn(DiaperChange, admin_site._registry)


class DiaperChangeFormTests(TestCase):
    def test_valid_form(self):
        form = DiaperChangeForm(
            data={
                "change_type": DiaperChange.ChangeType.WET,
                "changed_at": TEST_DATETIME,
            }
        )
        self.assertTrue(form.is_valid())

    def test_form_converts_local_time_to_utc(self):
        form = DiaperChangeForm(
            data={
                "change_type": DiaperChange.ChangeType.WET,
                "changed_at": TEST_DATETIME,
                "tz_offset": 300,  # UTC-5 (EST)
            }
        )
        self.assertTrue(form.is_valid())
        # 10:30 local + 300 minutes = 15:30 UTC
        self.assertEqual(form.cleaned_data["changed_at"].hour, 15)
        self.assertEqual(form.cleaned_data["changed_at"].minute, 30)


class DiaperChangeViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="testparent",
            email=TEST_PARENT_EMAIL,
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
            reverse(URL_DIAPER_LIST, kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_diaper_list_only_own_child(self):
        self.client.login(email=TEST_PARENT_EMAIL, password="testpass123")
        response = self.client.get(
            reverse(URL_DIAPER_LIST, kwargs={"child_pk": self.other_child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_diaper_create_requires_login(self):
        response = self.client.get(
            reverse("diapers:diaper_add", kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_diaper_create_adds_change(self):
        self.client.login(email=TEST_PARENT_EMAIL, password="testpass123")
        response = self.client.post(
            reverse("diapers:diaper_add", kwargs={"child_pk": self.child.pk}),
            {"change_type": "dirty", "changed_at": TEST_DATETIME},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            DiaperChange.objects.filter(
                child=self.child, change_type=DiaperChange.ChangeType.DIRTY
            ).exists()
        )

    def test_diaper_edit_only_own_change(self):
        self.client.login(email=TEST_PARENT_EMAIL, password="testpass123")
        other_change = DiaperChange.objects.create(
            child=self.other_child,
            change_type=DiaperChange.ChangeType.BOTH,
            changed_at=timezone.now(),
        )
        response = self.client.get(
            reverse(
                URL_DIAPER_EDIT,
                kwargs={"child_pk": self.other_child.pk, "pk": other_change.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_diaper_delete_only_own_change(self):
        self.client.login(email=TEST_PARENT_EMAIL, password="testpass123")
        other_change = DiaperChange.objects.create(
            child=self.other_child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=timezone.now(),
        )
        response = self.client.post(
            reverse(
                URL_DIAPER_DELETE,
                kwargs={"child_pk": self.other_child.pk, "pk": other_change.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_diaper_list_shows_changes(self):
        self.client.login(email=TEST_PARENT_EMAIL, password="testpass123")
        response = self.client.get(
            reverse(URL_DIAPER_LIST, kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wet")

    def test_diaper_edit_success(self):
        self.client.login(email=TEST_PARENT_EMAIL, password="testpass123")
        response = self.client.post(
            reverse(
                URL_DIAPER_EDIT,
                kwargs={"child_pk": self.child.pk, "pk": self.change.pk},
            ),
            {"change_type": "dirty", "changed_at": "2026-02-01T11:00"},
        )
        self.assertRedirects(
            response,
            reverse(URL_DIAPER_LIST, kwargs={"child_pk": self.child.pk}),
        )
        self.change.refresh_from_db()
        self.assertEqual(self.change.change_type, DiaperChange.ChangeType.DIRTY)

    def test_diaper_edit_get_shows_context(self):
        self.client.login(email=TEST_PARENT_EMAIL, password="testpass123")
        response = self.client.get(
            reverse(
                URL_DIAPER_EDIT,
                kwargs={"child_pk": self.child.pk, "pk": self.change.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["child"], self.child)

    def test_diaper_delete_success(self):
        self.client.login(email=TEST_PARENT_EMAIL, password="testpass123")
        change_pk = self.change.pk
        response = self.client.post(
            reverse(
                URL_DIAPER_DELETE,
                kwargs={"child_pk": self.child.pk, "pk": change_pk},
            )
        )
        self.assertRedirects(
            response,
            reverse(URL_DIAPER_LIST, kwargs={"child_pk": self.child.pk}),
        )
        self.assertFalse(DiaperChange.objects.filter(pk=change_pk).exists())

    def test_coparent_can_edit_diaper(self):
        coparent = get_user_model().objects.create_user(
            username="coparent",
            email="coparent@example.com",
            password="testpass123",
        )
        ChildShare.objects.create(
            child=self.child,
            user=coparent,
            role=ChildShare.Role.CO_PARENT,
            created_by=self.user,
        )
        self.client.login(email="coparent@example.com", password="testpass123")
        response = self.client.post(
            reverse(
                URL_DIAPER_EDIT,
                kwargs={"child_pk": self.child.pk, "pk": self.change.pk},
            ),
            {"change_type": "both", "changed_at": "2026-02-01T12:00"},
        )
        self.assertRedirects(
            response,
            reverse(URL_DIAPER_LIST, kwargs={"child_pk": self.child.pk}),
        )

    def test_coparent_can_delete_diaper(self):
        coparent = get_user_model().objects.create_user(
            username="coparent2",
            email="coparent2@example.com",
            password="testpass123",
        )
        ChildShare.objects.create(
            child=self.child,
            user=coparent,
            role=ChildShare.Role.CO_PARENT,
            created_by=self.user,
        )
        change = DiaperChange.objects.create(
            child=self.child,
            change_type=DiaperChange.ChangeType.WET,
            changed_at=timezone.now(),
        )
        self.client.login(email="coparent2@example.com", password="testpass123")
        response = self.client.post(
            reverse(
                URL_DIAPER_DELETE,
                kwargs={"child_pk": self.child.pk, "pk": change.pk},
            )
        )
        self.assertRedirects(
            response,
            reverse(URL_DIAPER_LIST, kwargs={"child_pk": self.child.pk}),
        )

    def test_caregiver_cannot_edit_diaper(self):
        caregiver = get_user_model().objects.create_user(
            username="caregiver",
            email="caregiver@example.com",
            password="testpass123",
        )
        ChildShare.objects.create(
            child=self.child,
            user=caregiver,
            role=ChildShare.Role.CAREGIVER,
            created_by=self.user,
        )
        self.client.login(email="caregiver@example.com", password="testpass123")
        response = self.client.get(
            reverse(
                URL_DIAPER_EDIT,
                kwargs={"child_pk": self.child.pk, "pk": self.change.pk},
            )
        )
        self.assertEqual(response.status_code, 404)
