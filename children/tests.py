from datetime import date

from django.contrib.admin.sites import site as admin_site
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import ChildForm
from .models import Child


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
