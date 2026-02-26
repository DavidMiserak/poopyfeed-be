"""Template filters for datetime display in the user's timezone (pure Django, no JS)."""

from django import template
from django.utils import timezone as django_tz

from children.datetime_utils import (
    format_child_age,
    format_datetime_user_tz,
    format_relative,
)

register = template.Library()


def _tz_arg(tz_name):
    """Normalize timezone argument from template (default UTC)."""
    return (tz_name or "UTC").strip() or "UTC"


@register.filter
def format_relative_tz(value, tz_name):
    """Format an aware UTC datetime as relative time (e.g. '2 hours ago').

    Usage: {{ obj.fed_at|format_relative_tz:user.timezone }}
    """
    if value is None:
        return ""
    return format_relative(value)


@register.filter
def format_exact_tz(value, tz_name):
    """Format an aware UTC datetime in the user's timezone (e.g. 'Jan 15, 02:30 PM').

    Usage: {{ obj.fed_at|format_exact_tz:user.timezone }}
    """
    if value is None:
        return ""
    return format_datetime_user_tz(value, _tz_arg(tz_name))


@register.filter
def format_child_age_tz(dob, tz_name):
    """Format a date of birth as age string in the user's timezone (e.g. '5 months old').

    Usage: {{ child.date_of_birth|format_child_age_tz:user.timezone }}
    """
    if dob is None:
        return ""
    return format_child_age(dob, _tz_arg(tz_name))
