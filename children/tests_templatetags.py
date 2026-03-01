"""Tests for children.templatetags.poopyfeed_dt filters."""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.template import Context, Template
from django.test import TestCase


class PoopyfeedDtFiltersTestCase(TestCase):
    """Test format_relative_tz, format_exact_tz, format_child_age_tz with None and values."""

    def test_format_relative_tz_none_returns_empty(self):
        """Filter with None value returns empty string (covers line 27)."""
        t = Template("{% load poopyfeed_dt %}{{ value|format_relative_tz:tz }}")
        result = t.render(Context({"value": None, "tz": "America/New_York"}))
        self.assertEqual(result.strip(), "")

    def test_format_relative_tz_with_value(self):
        """Filter with datetime returns relative string."""
        t = Template("{% load poopyfeed_dt %}{{ value|format_relative_tz:tz }}")
        value = datetime(2025, 2, 1, 12, 0, tzinfo=ZoneInfo("UTC"))
        result = t.render(Context({"value": value, "tz": "UTC"}))
        self.assertIn("ago", result)

    def test_format_exact_tz_none_returns_empty(self):
        """Filter with None value returns empty string (covers line 38)."""
        t = Template("{% load poopyfeed_dt %}{{ value|format_exact_tz:tz }}")
        result = t.render(Context({"value": None, "tz": "America/New_York"}))
        self.assertEqual(result.strip(), "")

    def test_format_exact_tz_with_value(self):
        """Filter with datetime returns formatted string."""
        t = Template("{% load poopyfeed_dt %}{{ value|format_exact_tz:tz }}")
        value = datetime(2025, 2, 15, 14, 30, tzinfo=ZoneInfo("UTC"))
        result = t.render(Context({"value": value, "tz": "UTC"}))
        self.assertIn("Feb", result)

    def test_format_child_age_tz_none_returns_empty(self):
        """Filter with None dob returns empty string (covers line 49)."""
        t = Template("{% load poopyfeed_dt %}{{ dob|format_child_age_tz:tz }}")
        result = t.render(Context({"dob": None, "tz": "America/New_York"}))
        self.assertEqual(result.strip(), "")

    def test_format_child_age_tz_with_date(self):
        """Filter with date returns age string."""
        t = Template("{% load poopyfeed_dt %}{{ dob|format_child_age_tz:tz }}")
        from datetime import date, timedelta

        from django.utils import timezone

        today = timezone.now().astimezone(ZoneInfo("UTC")).date()
        dob = today - timedelta(days=100)
        result = t.render(Context({"dob": dob, "tz": "UTC"}))
        self.assertIn("month", result)

    def test_tz_arg_normalizes_empty_to_utc(self):
        """Empty or whitespace tz_name is normalized to UTC (covers _tz_arg branches)."""
        t = Template("{% load poopyfeed_dt %}{{ value|format_exact_tz:tz }}")
        value = datetime(2025, 2, 15, 14, 30, tzinfo=ZoneInfo("UTC"))
        result_empty = t.render(Context({"value": value, "tz": ""}))
        result_whitespace = t.render(Context({"value": value, "tz": "  "}))
        self.assertIn("Feb", result_empty)
        self.assertIn("Feb", result_whitespace)
