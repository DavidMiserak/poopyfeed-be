from datetime import date

from django.contrib.admin.sites import site as admin_site
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import ChildForm, DiaperChangeForm, NapForm
from .models import Child, DiaperChange, Nap


class ChildModelTests(TestCase):
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
            gender=Child.Gender.FEMALE,
        )

    def test_child_creation(self):
        self.assertEqual(self.child.name, "Baby Jane")
        self.assertEqual(self.child.date_of_birth, date(2025, 6, 15))
        self.assertEqual(self.child.gender, "F")
        self.assertEqual(self.child.parent, self.user)

    def test_child_str(self):
        self.assertEqual(str(self.child), "Baby Jane")

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
            password="testpass123",
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
                "name": "Baby Test",
                "date_of_birth": "2025-06-15",
                "gender": "M",
            }
        )
        self.assertTrue(form.is_valid())

    def test_valid_form_without_gender(self):
        form = ChildForm(
            data={
                "name": "Baby Test",
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
                "name": "Baby Test",
                "date_of_birth": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("date_of_birth", form.errors)


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


class DiaperChangeFormTests(TestCase):
    def test_valid_form(self):
        form = DiaperChangeForm(
            data={
                "change_type": DiaperChange.ChangeType.WET,
                "changed_at": "2026-02-01T10:30",
            }
        )
        self.assertTrue(form.is_valid())


class ChildViewTests(TestCase):
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

    def test_list_view_requires_login(self):
        response = self.client.get(reverse("children:child_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts/login", response.url)

    def test_list_view_shows_only_own_children(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.get(reverse("children:child_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Baby Jane")
        self.assertNotContains(response, "Other Baby")

    def test_create_view_requires_login(self):
        response = self.client.get(reverse("children:child_add"))
        self.assertEqual(response.status_code, 302)

    def test_create_view_adds_child(self):
        self.client.login(email="parent@example.com", password="testpass123")
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
            reverse("children:child_edit", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_update_view_only_own_child(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.get(
            reverse("children:child_edit", kwargs={"pk": self.other_child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_update_view_updates_child(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.post(
            reverse("children:child_edit", kwargs={"pk": self.child.pk}),
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
            reverse("children:child_delete", kwargs={"pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_delete_view_only_own_child(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.post(
            reverse("children:child_delete", kwargs={"pk": self.other_child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_view_deletes_child(self):
        self.client.login(email="parent@example.com", password="testpass123")
        child_pk = self.child.pk
        response = self.client.post(
            reverse("children:child_delete", kwargs={"pk": child_pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Child.objects.filter(pk=child_pk).exists())


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
            reverse("children:diaper_list", kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_diaper_list_only_own_child(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.get(
            reverse("children:diaper_list", kwargs={"child_pk": self.other_child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_diaper_create_requires_login(self):
        response = self.client.get(
            reverse("children:diaper_add", kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_diaper_create_adds_change(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.post(
            reverse("children:diaper_add", kwargs={"child_pk": self.child.pk}),
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
            reverse("children:diaper_edit", kwargs={"pk": other_change.pk})
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
            reverse("children:diaper_delete", kwargs={"pk": other_change.pk})
        )
        self.assertEqual(response.status_code, 404)


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
            reverse("children:nap_list", kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_nap_list_only_own_child(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.get(
            reverse("children:nap_list", kwargs={"child_pk": self.other_child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_nap_list_shows_naps(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.get(
            reverse("children:nap_list", kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nap")

    def test_nap_create_requires_login(self):
        response = self.client.get(
            reverse("children:nap_add", kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_nap_create_only_own_child(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.get(
            reverse("children:nap_add", kwargs={"child_pk": self.other_child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_nap_create_adds_nap(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.post(
            reverse("children:nap_add", kwargs={"child_pk": self.child.pk}),
            {"napped_at": "2026-02-01T14:00"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Nap.objects.filter(child=self.child).count(), 2)

    def test_nap_edit_requires_login(self):
        response = self.client.get(
            reverse("children:nap_edit", kwargs={"pk": self.nap.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_nap_edit_only_own_nap(self):
        self.client.login(email="parent@example.com", password="testpass123")
        other_nap = Nap.objects.create(
            child=self.other_child,
            napped_at=timezone.now(),
        )
        response = self.client.get(
            reverse("children:nap_edit", kwargs={"pk": other_nap.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_nap_edit_updates_nap(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.post(
            reverse("children:nap_edit", kwargs={"pk": self.nap.pk}),
            {"napped_at": "2026-02-01T15:00"},
        )
        self.assertEqual(response.status_code, 302)
        self.nap.refresh_from_db()
        self.assertEqual(self.nap.napped_at.hour, 15)

    def test_nap_delete_requires_login(self):
        response = self.client.get(
            reverse("children:nap_delete", kwargs={"pk": self.nap.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_nap_delete_only_own_nap(self):
        self.client.login(email="parent@example.com", password="testpass123")
        other_nap = Nap.objects.create(
            child=self.other_child,
            napped_at=timezone.now(),
        )
        response = self.client.post(
            reverse("children:nap_delete", kwargs={"pk": other_nap.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_nap_delete_deletes_nap(self):
        self.client.login(email="parent@example.com", password="testpass123")
        nap_pk = self.nap.pk
        response = self.client.post(
            reverse("children:nap_delete", kwargs={"pk": nap_pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Nap.objects.filter(pk=nap_pk).exists())
