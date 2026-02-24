"""Unit tests for TrackingViewSet base class edge cases."""

from unittest.mock import MagicMock, PropertyMock

from django.test import TestCase

from diapers.api import DiaperChangeViewSet
from diapers.models import DiaperChange

from .tracking_api import TrackingViewSet


class TrackingViewSetSerializerClassTests(TestCase):
    """Test get_serializer_class edge cases."""

    def test_nested_route_without_nested_serializer_raises(self):
        """NotImplementedError if nested_serializer_class not set."""
        view = TrackingViewSet()
        view.kwargs = {"child_pk": 1}
        view.nested_serializer_class = None
        with self.assertRaises(NotImplementedError):
            view.get_serializer_class()

    def test_non_nested_route_returns_serializer_class(self):
        """Non-nested route returns default serializer_class."""
        view = TrackingViewSet()
        view.kwargs = {}  # No child_pk
        view.serializer_class = "DefaultSerializer"
        result = view.get_serializer_class()
        self.assertEqual(result, "DefaultSerializer")


class TrackingViewSetDateFilterTests(TestCase):
    """Test _apply_datetime_filters edge cases."""

    def test_apply_datetime_filters_no_field_set(self):
        """When datetime_filter_field is None, queryset is returned unchanged."""
        from diapers.models import DiaperChange

        view = TrackingViewSet()
        view.datetime_filter_field = None
        qs = DiaperChange.objects.none()
        result = view._apply_datetime_filters(qs)
        self.assertEqual(result.count(), 0)  # Same queryset returned


class TrackingViewSetTopLevelRouteTests(TestCase):
    """Test top-level route queryset and perform_create paths."""

    def test_get_queryset_top_level_route(self):
        """Top-level route returns all accessible children's records."""
        from django.contrib.auth import get_user_model

        from django_project.test_constants import TEST_PASSWORD

        from .models import Child

        user = get_user_model().objects.create_user(
            username="topleveluser",
            email="toplevel@example.com",
            password=TEST_PASSWORD,
        )
        child = Child.objects.create(
            parent=user, name="TopLevel Baby", date_of_birth="2025-01-01"
        )

        # Set up the ViewSet as if handling a top-level route
        view = DiaperChangeViewSet()
        view.kwargs = {}  # No child_pk = top-level route
        view.request = MagicMock()
        view.request.user = user
        view.request.query_params = {}

        qs = view.get_queryset()
        # Should return empty (no diapers yet) but not error
        self.assertEqual(qs.count(), 0)

    def test_perform_create_top_level_route(self):
        """Top-level route perform_create calls serializer.save() without child."""
        view = TrackingViewSet()
        view.kwargs = {}  # No child_pk
        view.request = MagicMock()

        mock_serializer = MagicMock()
        view.perform_create(mock_serializer)
        mock_serializer.save.assert_called_once_with()
