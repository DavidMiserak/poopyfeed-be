from datetime import date

from django.contrib.admin.sites import site as admin_site
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from children.models import Child

from .forms import FeedingForm
from .models import Feeding


class FeedingModelTests(TestCase):
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

    def test_bottle_feeding_creation(self):
        feeding = Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=timezone.now(),
            amount_oz=4.5,
        )
        self.assertEqual(feeding.child, self.child)
        self.assertEqual(feeding.feeding_type, "bottle")
        self.assertEqual(feeding.amount_oz, 4.5)

    def test_breast_feeding_creation(self):
        feeding = Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BREAST,
            fed_at=timezone.now(),
            duration_minutes=15,
            side=Feeding.BreastSide.LEFT,
        )
        self.assertEqual(feeding.child, self.child)
        self.assertEqual(feeding.feeding_type, "breast")
        self.assertEqual(feeding.duration_minutes, 15)
        self.assertEqual(feeding.side, "left")

    def test_feeding_str_bottle(self):
        feeding = Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=timezone.now(),
            amount_oz=3.0,
        )
        self.assertEqual(str(feeding), "Baby Jane - Bottle")

    def test_feeding_str_breast(self):
        feeding = Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BREAST,
            fed_at=timezone.now(),
            duration_minutes=10,
            side=Feeding.BreastSide.RIGHT,
        )
        self.assertEqual(str(feeding), "Baby Jane - Breast")

    def test_feeding_ordering(self):
        first_feeding = Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=timezone.now() - timezone.timedelta(hours=2),
            amount_oz=4.0,
        )
        second_feeding = Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BREAST,
            fed_at=timezone.now(),
            duration_minutes=10,
            side=Feeding.BreastSide.BOTH,
        )
        feedings = list(Feeding.objects.all())
        self.assertEqual(feedings[0], second_feeding)
        self.assertEqual(feedings[1], first_feeding)

    def test_feeding_related_name(self):
        feeding = Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=timezone.now(),
            amount_oz=5.0,
        )
        self.assertIn(feeding, self.child.feedings.all())

    def test_feeding_cascade_delete(self):
        Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=timezone.now(),
            amount_oz=4.0,
        )
        feeding_count_before = Feeding.objects.count()
        self.child.delete()
        self.assertEqual(Feeding.objects.count(), feeding_count_before - 1)

    def test_feeding_timestamps(self):
        feeding = Feeding.objects.create(
            child=self.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=timezone.now(),
            amount_oz=3.5,
        )
        self.assertIsNotNone(feeding.created_at)
        self.assertIsNotNone(feeding.updated_at)

    def test_feeding_type_choices(self):
        self.assertEqual(Feeding.FeedingType.BOTTLE, "bottle")
        self.assertEqual(Feeding.FeedingType.BREAST, "breast")

    def test_breast_side_choices(self):
        self.assertEqual(Feeding.BreastSide.LEFT, "left")
        self.assertEqual(Feeding.BreastSide.RIGHT, "right")
        self.assertEqual(Feeding.BreastSide.BOTH, "both")


class FeedingAdminTests(TestCase):
    def test_feeding_admin_registered(self):
        self.assertIn(Feeding, admin_site._registry)


class FeedingFormTests(TestCase):
    def test_valid_bottle_form(self):
        form = FeedingForm(
            data={
                "feeding_type": Feeding.FeedingType.BOTTLE,
                "fed_at": "2026-02-01T10:30",
                "amount_oz": "4.5",
            }
        )
        self.assertTrue(form.is_valid())

    def test_valid_breast_form(self):
        form = FeedingForm(
            data={
                "feeding_type": Feeding.FeedingType.BREAST,
                "fed_at": "2026-02-01T10:30",
                "duration_minutes": "15",
                "side": Feeding.BreastSide.LEFT,
            }
        )
        self.assertTrue(form.is_valid())

    def test_bottle_form_requires_amount(self):
        form = FeedingForm(
            data={
                "feeding_type": Feeding.FeedingType.BOTTLE,
                "fed_at": "2026-02-01T10:30",
                "amount_oz": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("amount_oz", form.errors)

    def test_breast_form_requires_duration(self):
        form = FeedingForm(
            data={
                "feeding_type": Feeding.FeedingType.BREAST,
                "fed_at": "2026-02-01T10:30",
                "duration_minutes": "",
                "side": Feeding.BreastSide.RIGHT,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("duration_minutes", form.errors)

    def test_breast_form_requires_side(self):
        form = FeedingForm(
            data={
                "feeding_type": Feeding.FeedingType.BREAST,
                "fed_at": "2026-02-01T10:30",
                "duration_minutes": "10",
                "side": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("side", form.errors)

    def test_bottle_form_clears_breast_fields(self):
        form = FeedingForm(
            data={
                "feeding_type": Feeding.FeedingType.BOTTLE,
                "fed_at": "2026-02-01T10:30",
                "amount_oz": "4.0",
                "duration_minutes": "15",
                "side": Feeding.BreastSide.LEFT,
            }
        )
        self.assertTrue(form.is_valid())
        self.assertIsNone(form.cleaned_data["duration_minutes"])
        self.assertEqual(form.cleaned_data["side"], "")

    def test_breast_form_clears_bottle_fields(self):
        form = FeedingForm(
            data={
                "feeding_type": Feeding.FeedingType.BREAST,
                "fed_at": "2026-02-01T10:30",
                "duration_minutes": "10",
                "side": Feeding.BreastSide.BOTH,
                "amount_oz": "4.0",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertIsNone(form.cleaned_data["amount_oz"])

    def test_invalid_form_missing_fed_at(self):
        form = FeedingForm(
            data={
                "feeding_type": Feeding.FeedingType.BOTTLE,
                "fed_at": "",
                "amount_oz": "4.0",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("fed_at", form.errors)

    def test_invalid_form_missing_feeding_type(self):
        form = FeedingForm(
            data={
                "feeding_type": "",
                "fed_at": "2026-02-01T10:30",
                "amount_oz": "4.0",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("feeding_type", form.errors)


class FeedingViewTests(TestCase):
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
        cls.feeding = Feeding.objects.create(
            child=cls.child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=timezone.now(),
            amount_oz=4.0,
        )

    def test_feeding_list_requires_login(self):
        response = self.client.get(
            reverse("feedings:feeding_list", kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_feeding_list_only_own_child(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.get(
            reverse("feedings:feeding_list", kwargs={"child_pk": self.other_child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_feeding_list_shows_feedings(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.get(
            reverse("feedings:feeding_list", kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bottle")
        self.assertContains(response, "4.0 oz")

    def test_feeding_create_requires_login(self):
        response = self.client.get(
            reverse("feedings:feeding_add", kwargs={"child_pk": self.child.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_feeding_create_only_own_child(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.get(
            reverse("feedings:feeding_add", kwargs={"child_pk": self.other_child.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_feeding_create_adds_bottle_feeding(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.post(
            reverse("feedings:feeding_add", kwargs={"child_pk": self.child.pk}),
            {
                "feeding_type": "bottle",
                "fed_at": "2026-02-01T10:30",
                "amount_oz": "5.0",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Feeding.objects.filter(
                child=self.child,
                feeding_type=Feeding.FeedingType.BOTTLE,
                amount_oz=5.0,
            ).exists()
        )

    def test_feeding_create_adds_breast_feeding(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.post(
            reverse("feedings:feeding_add", kwargs={"child_pk": self.child.pk}),
            {
                "feeding_type": "breast",
                "fed_at": "2026-02-01T11:00",
                "duration_minutes": "20",
                "side": "left",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Feeding.objects.filter(
                child=self.child,
                feeding_type=Feeding.FeedingType.BREAST,
                duration_minutes=20,
                side=Feeding.BreastSide.LEFT,
            ).exists()
        )

    def test_feeding_edit_requires_login(self):
        response = self.client.get(
            reverse(
                "feedings:feeding_edit",
                kwargs={"child_pk": self.child.pk, "pk": self.feeding.pk},
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_feeding_edit_only_own_feeding(self):
        self.client.login(email="parent@example.com", password="testpass123")
        other_feeding = Feeding.objects.create(
            child=self.other_child,
            feeding_type=Feeding.FeedingType.BOTTLE,
            fed_at=timezone.now(),
            amount_oz=3.0,
        )
        response = self.client.get(
            reverse(
                "feedings:feeding_edit",
                kwargs={"child_pk": self.other_child.pk, "pk": other_feeding.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_feeding_edit_updates_feeding(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.post(
            reverse(
                "feedings:feeding_edit",
                kwargs={"child_pk": self.child.pk, "pk": self.feeding.pk},
            ),
            {
                "feeding_type": "bottle",
                "fed_at": "2026-02-01T15:00",
                "amount_oz": "6.0",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.feeding.refresh_from_db()
        self.assertEqual(self.feeding.amount_oz, 6.0)

    def test_feeding_delete_requires_login(self):
        response = self.client.get(
            reverse(
                "feedings:feeding_delete",
                kwargs={"child_pk": self.child.pk, "pk": self.feeding.pk},
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_feeding_delete_only_own_feeding(self):
        self.client.login(email="parent@example.com", password="testpass123")
        other_feeding = Feeding.objects.create(
            child=self.other_child,
            feeding_type=Feeding.FeedingType.BREAST,
            fed_at=timezone.now(),
            duration_minutes=15,
            side=Feeding.BreastSide.RIGHT,
        )
        response = self.client.post(
            reverse(
                "feedings:feeding_delete",
                kwargs={"child_pk": self.other_child.pk, "pk": other_feeding.pk},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_feeding_delete_deletes_feeding(self):
        self.client.login(email="parent@example.com", password="testpass123")
        feeding_pk = self.feeding.pk
        response = self.client.post(
            reverse(
                "feedings:feeding_delete",
                kwargs={"child_pk": self.child.pk, "pk": feeding_pk},
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Feeding.objects.filter(pk=feeding_pk).exists())

    def test_child_list_shows_last_feeding(self):
        self.client.login(email="parent@example.com", password="testpass123")
        response = self.client.get(reverse("children:child_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Feedings")
