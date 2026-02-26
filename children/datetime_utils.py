"""Pure Django datetime helpers using the user's timezone (no JavaScript)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.utils import timezone as django_tz


def _user_tz(tz_name):
    """Return ZoneInfo for tz_name, defaulting to UTC."""
    return ZoneInfo(tz_name) if tz_name else ZoneInfo("UTC")


def utc_to_local_datetime_local_str(utc_dt, tz_name):
    """Format an aware UTC datetime for HTML datetime-local input (YYYY-MM-DDTHH:mm).

    Args:
        utc_dt: timezone-aware datetime in UTC
        tz_name: IANA timezone name (e.g. America/New_York)

    Returns:
        str: Value for <input type="datetime-local"> in that timezone
    """
    if utc_dt is None:
        return ""
    local = utc_dt.astimezone(_user_tz(tz_name))
    return local.strftime("%Y-%m-%dT%H:%M")


def now_in_user_tz_str(tz_name):
    """Current time formatted for datetime-local input in the given timezone."""
    return utc_to_local_datetime_local_str(django_tz.now(), tz_name)


def naive_local_to_utc(naive_dt, tz_name):
    """Interpret a naive datetime as being in tz_name and return aware UTC.

    Args:
        naive_dt: naive datetime (e.g. from form input)
        tz_name: IANA timezone name

    Returns:
        timezone-aware datetime in UTC
    """
    if naive_dt is None:
        return None
    tz = _user_tz(tz_name)
    local = naive_dt.replace(tzinfo=tz)
    return local.astimezone(django_tz.UTC)


def format_datetime_user_tz(utc_dt, tz_name, fmt="%b %d, %I:%M %p"):
    """Format an aware UTC datetime for display in the user's timezone.

    Args:
        utc_dt: timezone-aware datetime in UTC
        tz_name: IANA timezone name
        fmt: strftime format (default e.g. "Jan 15, 2:30 PM")

    Returns:
        str: Formatted string
    """
    if utc_dt is None:
        return ""
    local = utc_dt.astimezone(_user_tz(tz_name))
    return local.strftime(fmt)


def format_relative(utc_dt):
    """Format an aware UTC datetime as relative time (e.g. '2 hours ago').

    Uses the same instant globally; wording is in English.
    """
    if utc_dt is None:
        return ""
    now = django_tz.now()
    delta = now - utc_dt
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return "just now"
    if total_seconds < 3600:
        m = total_seconds // 60
        return f"{m} min{'s' if m != 1 else ''} ago"
    if total_seconds < 86400:
        h = total_seconds // 3600
        return f"{h} hour{'s' if h != 1 else ''} ago"
    if total_seconds < 2592000:  # 30 days
        d = total_seconds // 86400
        return f"{d} day{'s' if d != 1 else ''} ago"
    if total_seconds < 31536000:  # 365 days
        mo = total_seconds // 2592000
        return f"{mo} month{'s' if mo != 1 else ''} ago"
    y = total_seconds // 31536000
    return f"{y} year{'s' if y != 1 else ''} ago"


def format_child_age(dob, tz_name):
    """Format a date of birth as age string (e.g. '(5 months old)').

    Uses 'today' in the user's timezone so the age is correct for their calendar day.
    """
    if not dob:
        return ""
    tz = _user_tz(tz_name)
    today = django_tz.now().astimezone(tz).date()
    if isinstance(dob, datetime):
        dob = dob.date()
    delta_days = (today - dob).days
    if delta_days < 60:
        return f"({delta_days} day{'s' if delta_days != 1 else ''} old)"
    if delta_days < 730:
        months = delta_days // 30
        return f"({months} month{'s' if months != 1 else ''} old)"
    years = delta_days // 365
    return f"({years} year{'s' if years != 1 else ''} old)"
