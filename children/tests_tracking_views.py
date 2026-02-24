"""Tests for tracking_views.py base class edge cases."""

from unittest.mock import MagicMock

from django.test import TestCase

from .tracking_views import TrackingCreateView, TrackingDeleteView, TrackingUpdateView


class TrackingViewSuccessUrlTests(TestCase):
    """Test get_success_url raises NotImplementedError without success_url_name."""

    def _make_view(self, view_class):
        """Create a view instance with mocked attributes."""
        view = view_class()
        view.success_url_name = None  # Not set
        view.child = MagicMock()
        view.child.pk = 1
        view.object = MagicMock()
        view.object.child.pk = 1
        return view

    def test_create_view_missing_success_url_name(self):
        """TrackingCreateView.get_success_url raises without success_url_name."""
        view = self._make_view(TrackingCreateView)
        with self.assertRaises(NotImplementedError):
            view.get_success_url()

    def test_update_view_missing_success_url_name(self):
        """TrackingUpdateView.get_success_url raises without success_url_name."""
        view = self._make_view(TrackingUpdateView)
        with self.assertRaises(NotImplementedError):
            view.get_success_url()

    def test_delete_view_missing_success_url_name(self):
        """TrackingDeleteView.get_success_url raises without success_url_name."""
        view = self._make_view(TrackingDeleteView)
        with self.assertRaises(NotImplementedError):
            view.get_success_url()
