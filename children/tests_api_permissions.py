"""Tests for API permission edge cases."""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from django_project.test_constants import TEST_PASSWORD

from .api_permissions import CanEditChild, CanManageSharing, HasChildAccess
from .models import Child


class PermissionGetChildNoneTests(TestCase):
    """Tests for _get_child returning None with non-Child objects."""

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(
            username="permuser",
            email="perm@example.com",
            password=TEST_PASSWORD,
        )

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get("/")
        self.request.user = self.user

    def test_has_child_access_with_unrelated_object(self):
        """HasChildAccess returns False for objects without child attribute."""
        permission = HasChildAccess()
        obj = object()  # No .child attribute
        self.assertFalse(permission.has_object_permission(self.request, None, obj))

    def test_can_edit_child_with_unrelated_object(self):
        """CanEditChild returns False for objects without child attribute."""
        permission = CanEditChild()
        obj = object()
        self.assertFalse(permission.has_object_permission(self.request, None, obj))

    def test_can_manage_sharing_with_unrelated_object(self):
        """CanManageSharing returns False for objects without child attribute."""
        permission = CanManageSharing()
        obj = object()
        self.assertFalse(permission.has_object_permission(self.request, None, obj))

    def test_has_child_access_with_child_attribute(self):
        """HasChildAccess works with objects that have a child attribute."""
        child = Child.objects.create(
            parent=self.user,
            name="Perm Baby",
            date_of_birth="2025-01-01",
        )
        permission = HasChildAccess()

        class FakeTrackingRecord:
            pass

        record = FakeTrackingRecord()
        record.child = child
        self.assertTrue(permission.has_object_permission(self.request, None, record))
