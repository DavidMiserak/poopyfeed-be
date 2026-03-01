"""Tests for children.datetime_utils (timezone and formatting helpers)."""

from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone as django_tz

from .datetime_utils import (
    format_child_age,
    format_datetime_user_tz,
    format_relative,
    naive_local_to_utc,
    now_in_user_tz_str,
    utc_to_local_datetime_local_str,
)


class DatetimeUtilsTestCase(TestCase):
    """Test datetime utility functions."""

    def test_utc_to_local_datetime_local_str_none(self):
        """None input returns empty string."""
        self.assertEqual(utc_to_local_datetime_local_str(None, "America/New_York"), "")

    def test_utc_to_local_datetime_local_str_with_tz(self):
        """Aware UTC datetime is converted to local string."""
        utc = datetime(2025, 2, 15, 18, 30, tzinfo=ZoneInfo("UTC"))
        result = utc_to_local_datetime_local_str(utc, "America/New_York")
        self.assertEqual(result, "2025-02-15T13:30")

    def test_utc_to_local_datetime_local_str_no_tz_uses_utc(self):
        """None tz_name defaults to UTC."""
        utc = datetime(2025, 2, 15, 18, 30, tzinfo=ZoneInfo("UTC"))
        result = utc_to_local_datetime_local_str(utc, None)
        self.assertEqual(result, "2025-02-15T18:30")

    def test_now_in_user_tz_str(self):
        """Current time is formatted in user timezone."""
        with patch.object(
            django_tz,
            "now",
            return_value=datetime(2025, 2, 15, 12, 0, tzinfo=ZoneInfo("UTC")),
        ):
            result = now_in_user_tz_str("Europe/London")
        self.assertEqual(result, "2025-02-15T12:00")

    def test_naive_local_to_utc_none(self):
        """None input returns None."""
        self.assertIsNone(naive_local_to_utc(None, "America/New_York"))

    def test_naive_local_to_utc_conversion(self):
        """Naive datetime in local tz is converted to aware UTC."""
        naive = datetime(2025, 2, 15, 13, 30)
        result = naive_local_to_utc(naive, "America/New_York")
        self.assertIsNotNone(result)
        self.assertEqual(result.tzinfo, ZoneInfo("UTC"))

    def test_format_datetime_user_tz_none(self):
        """None datetime returns empty string."""
        self.assertEqual(format_datetime_user_tz(None, "America/New_York"), "")

    def test_format_datetime_user_tz_with_fmt(self):
        """Datetime is formatted with given format."""
        utc = datetime(2025, 2, 15, 18, 30, tzinfo=ZoneInfo("UTC"))
        result = format_datetime_user_tz(utc, "America/New_York", fmt="%Y-%m-%d %H:%M")
        self.assertIn("2025-02-15", result)

    def test_format_relative_none(self):
        """None returns empty string."""
        self.assertEqual(format_relative(None), "")

    def test_format_relative_just_now(self):
        """Under 60 seconds returns 'just now'."""
        now = django_tz.now()
        past = now - timedelta(seconds=30)
        self.assertEqual(format_relative(past), "just now")

    def test_format_relative_one_minute(self):
        """Exactly 1 minute returns '1 min ago'."""
        now = django_tz.now()
        past = now - timedelta(minutes=1)
        self.assertEqual(format_relative(past), "1 min ago")

    def test_format_relative_multiple_minutes(self):
        """Multiple minutes returns 'N mins ago'."""
        now = django_tz.now()
        past = now - timedelta(minutes=5)
        self.assertEqual(format_relative(past), "5 mins ago")

    def test_format_relative_one_hour(self):
        """One hour returns '1 hour ago'."""
        now = django_tz.now()
        past = now - timedelta(hours=1)
        self.assertEqual(format_relative(past), "1 hour ago")

    def test_format_relative_multiple_hours(self):
        """Multiple hours returns 'N hours ago'."""
        now = django_tz.now()
        past = now - timedelta(hours=3)
        self.assertEqual(format_relative(past), "3 hours ago")

    def test_format_relative_days(self):
        """Days return 'N day(s) ago'."""
        now = django_tz.now()
        past_one = now - timedelta(days=1)
        past_many = now - timedelta(days=10)
        self.assertEqual(format_relative(past_one), "1 day ago")
        self.assertEqual(format_relative(past_many), "10 days ago")

    def test_format_relative_months(self):
        """~30-day range returns months."""
        now = django_tz.now()
        past_one = now - timedelta(days=31)
        past_many = now - timedelta(days=90)
        self.assertEqual(format_relative(past_one), "1 month ago")
        self.assertEqual(format_relative(past_many), "3 months ago")

    def test_format_relative_years(self):
        """Over ~365 days returns years."""
        now = django_tz.now()
        past_one = now - timedelta(days=400)
        past_many = now - timedelta(days=800)
        self.assertEqual(format_relative(past_one), "1 year ago")
        self.assertEqual(format_relative(past_many), "2 years ago")

    def test_format_child_age_none(self):
        """None dob returns empty string."""
        self.assertEqual(format_child_age(None, "UTC"), "")

    def test_format_child_age_date_days(self):
        """DOB within 60 days returns days old."""
        today = django_tz.now().astimezone(ZoneInfo("UTC")).date()
        dob = today - timedelta(days=30)
        result = format_child_age(dob, "UTC")
        self.assertEqual(result, "(30 days old)")

    def test_format_child_age_date_one_day(self):
        """One day old uses singular."""
        today = django_tz.now().astimezone(ZoneInfo("UTC")).date()
        dob = today - timedelta(days=1)
        result = format_child_age(dob, "UTC")
        self.assertEqual(result, "(1 day old)")

    def test_format_child_age_date_months(self):
        """DOB 60–729 days returns months old."""
        today = django_tz.now().astimezone(ZoneInfo("UTC")).date()
        dob = today - timedelta(days=120)
        result = format_child_age(dob, "UTC")
        self.assertEqual(result, "(4 months old)")

    def test_format_child_age_date_one_month(self):
        """Months branch singular: 60–89 days → 2 months (60//30=2); 30 days would be '1 month' but still in days branch."""
        today = django_tz.now().astimezone(ZoneInfo("UTC")).date()
        dob = today - timedelta(days=60)
        result = format_child_age(dob, "UTC")
        self.assertEqual(result, "(2 months old)")

    def test_format_child_age_date_years(self):
        """DOB 730+ days returns years old."""
        today = django_tz.now().astimezone(ZoneInfo("UTC")).date()
        dob = today - timedelta(days=800)
        result = format_child_age(dob, "UTC")
        self.assertIn("year", result)

    def test_format_child_age_datetime_converted_to_date(self):
        """datetime DOB is converted to date for age calculation."""
        today = django_tz.now().astimezone(ZoneInfo("UTC")).date()
        dob_dt = datetime.combine(
            today - timedelta(days=100), datetime.min.time(), tzinfo=ZoneInfo("UTC")
        )
        result = format_child_age(dob_dt, "UTC")
        self.assertIn("month", result)

    def test_format_child_age_one_year_singular(self):
        """Years branch: 730+ days uses years (730//365=2 → '2 years old')."""
        today = django_tz.now().astimezone(ZoneInfo("UTC")).date()
        dob = today - timedelta(days=730)
        result = format_child_age(dob, "UTC")
        self.assertEqual(result, "(2 years old)")
