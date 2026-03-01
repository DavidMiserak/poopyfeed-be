"""Aggregation utilities for analytics calculations.

Functions to compute trends, patterns, and summaries from raw tracking data.
All aggregations are performed at the database level using Django ORM
aggregation functions for efficiency.
"""

import csv
from datetime import date, datetime, timedelta
from io import StringIO
from typing import Any, cast
from zoneinfo import ZoneInfo

from django.db.models import (
    Avg,
    Count,
    ExpressionWrapper,
    F,
    FloatField,
    Func,
    Q,
    Sum,
)
from django.db.models.functions import TruncDate
from django.utils import timezone

from children.models import Child
from diapers.models import DiaperChange
from feedings.models import Feeding
from naps.models import Nap

# Duration expression for nap calculations: (ended_at - napped_at) in minutes
# EXTRACT(EPOCH FROM interval) returns seconds; divide by 60 for minutes
_DURATION_EXPR = ExpressionWrapper(
    Func(
        F("ended_at") - F("napped_at"),
        function="",
        template="EXTRACT(EPOCH FROM %(expressions)s)",
    )
    / 60,
    output_field=FloatField(),
)


def _get_date_range(days: int = 30) -> tuple[date, date]:
    """Get start and end dates for a trend query.

    Args:
        days: Number of days to retrieve (1-90)

    Returns:
        Tuple of (start_date, end_date) as date objects
    """
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days - 1)
    return start_date, end_date


def _fill_date_gaps(
    data: list[dict],
    days: int,
) -> list[dict]:
    """Fill missing dates with zero counts to prevent chart gaps.

    Args:
        data: List of aggregated data dicts with 'date' key
        days: Total number of days in the range

    Returns:
        List of dicts with one entry per date, filled gaps have count=0
    """
    start_date, end_date = _get_date_range(days)

    # Create a dict for quick lookup by date
    data_dict = {d["date"]: d for d in data}

    # Get sample data to determine what fields to fill
    sample_fields = set(data[0].keys()) if data else {"date", "count"}

    # Generate all dates in range
    current_date = start_date
    filled_data = []

    while current_date <= end_date:
        if current_date in data_dict:
            filled_data.append(data_dict[current_date])
        else:
            # Fill gap with zero count and None for other fields
            gap_entry = {"date": current_date, "count": 0}
            for field in sample_fields:
                if field != "date" and field != "count":
                    gap_entry[field] = None
            filled_data.append(gap_entry)

        current_date += timedelta(days=1)

    return filled_data


def _calculate_trend(values: list[int | float]) -> str:
    """Calculate trend direction from a list of values.

    Compares the first half with second half to determine if trending
    up, down, or stable.

    Args:
        values: List of numeric values

    Returns:
        String: 'increasing', 'decreasing', or 'stable'
    """
    if not values or len(values) < 2:
        return "stable"

    mid = len(values) // 2
    first_half = values[:mid]
    second_half = values[mid:]

    first_avg = sum(first_half) / len(first_half)
    second_avg = sum(second_half) / len(second_half)

    # Calculate percentage change
    if first_avg == 0:
        return "increasing" if second_avg > 0 else "stable"

    pct_change = (second_avg - first_avg) / first_avg

    if pct_change > 0.1:  # 10% increase
        return "increasing"
    elif pct_change < -0.1:  # 10% decrease
        return "decreasing"
    else:
        return "stable"


def _calculate_variance(values: list[int | float]) -> float:
    """Calculate variance of values.

    Args:
        values: List of numeric values

    Returns:
        Variance as float (rounded to 2 decimals)
    """
    if not values or len(values) < 2:
        return 0.0

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)

    return round(variance, 2)


def _weekly_summary_from_daily(daily_data: list[dict]) -> dict[str, Any]:
    """Build weekly_summary dict from daily_data (counts, avg, trend, variance)."""
    counts = [d["count"] for d in daily_data]
    avg_per_day = sum(counts) / len(counts) if counts else 0
    return {
        "avg_per_day": round(avg_per_day, 2),
        "trend": _calculate_trend(counts),
        "variance": _calculate_variance(counts),
    }


def get_feeding_trends(
    child_id: int,
    days: int = 30,
) -> dict[str, Any]:
    """Get feeding trends for a child over the specified period.

    Aggregates feedings by date and calculates weekly summaries.

    Args:
        child_id: The child's ID
        days: Number of days to retrieve (1-90, default 30)

    Returns:
        Dict with period, daily_data, weekly_summary, and last_updated
    """
    start_date, end_date = _get_date_range(days)

    # Fetch aggregated data from database
    raw_data = (
        Feeding.objects.filter(
            child_id=child_id,
            fed_at__date__gte=start_date,
            fed_at__date__lte=end_date,
        )
        .annotate(date=TruncDate("fed_at"))
        .values("date")
        .annotate(
            count=Count("id"),
            average_duration=Avg("duration_minutes"),
            total_oz=Sum("amount_oz"),
        )
        .order_by("date")
    )

    # Convert QuerySet to list of dicts
    daily_data = list(raw_data.values("date", "count", "average_duration", "total_oz"))

    # Fill gaps for dates with no data
    daily_data = _fill_date_gaps(daily_data, days)

    return {
        "period": f"{start_date} to {end_date}",
        "child_id": child_id,
        "daily_data": daily_data,
        "weekly_summary": _weekly_summary_from_daily(daily_data),
        "last_updated": timezone.now().isoformat(),
    }


def get_diaper_patterns(
    child_id: int,
    days: int = 30,
) -> dict[str, Any]:
    """Get diaper change patterns for a child.

    Aggregates diaper changes by date with per-day type breakdown.

    Args:
        child_id: The child's ID
        days: Number of days to retrieve (1-90, default 30)

    Returns:
        Dict with period, daily_data, weekly_summary, breakdown, and last_updated
    """
    start_date, end_date = _get_date_range(days)

    # Single optimized query: fetch all diaper data with date and type
    all_diaper_data = (
        DiaperChange.objects.filter(
            child_id=child_id,
            changed_at__date__gte=start_date,
            changed_at__date__lte=end_date,
        )
        .annotate(date=TruncDate("changed_at"))
        .values("date", "change_type")
        .annotate(count=Count("id"))
        .order_by("date", "change_type")
    )

    # Pivot data: transform (date, type) → (date, {wet, dirty, both})
    daily_by_date = {}
    period_breakdown = {"wet": 0, "dirty": 0, "both": 0}

    for row in all_diaper_data:
        date = row["date"]
        change_type = row["change_type"]
        count = row["count"]

        # Initialize date entry if not exists
        if date not in daily_by_date:
            daily_by_date[date] = {
                "date": date,
                "count": 0,
                "wet_count": 0,
                "dirty_count": 0,
                "both_count": 0,
            }

        # Add to daily count
        daily_by_date[date]["count"] += count

        # Add to type-specific counts (change_type values: 'wet', 'dirty', 'both')
        if change_type == "wet":
            daily_by_date[date]["wet_count"] = count
        elif change_type == "dirty":
            daily_by_date[date]["dirty_count"] = count
        elif change_type == "both":
            daily_by_date[date]["both_count"] = count

        # Add to period breakdown
        if change_type in period_breakdown:
            period_breakdown[change_type] += count

    # Convert to sorted list and fill date gaps
    daily_data = sorted(daily_by_date.values(), key=lambda x: x["date"])
    daily_data = _fill_date_gaps(daily_data, days)

    result = {
        "period": f"{start_date} to {end_date}",
        "child_id": child_id,
        "daily_data": daily_data,
        "weekly_summary": _weekly_summary_from_daily(daily_data),
        "last_updated": timezone.now().isoformat(),
    }
    result["breakdown"] = period_breakdown
    return result


def get_sleep_summary(
    child_id: int,
    days: int = 30,
) -> dict[str, Any]:
    """Get sleep summary for a child.

    Aggregates naps by date.

    Args:
        child_id: The child's ID
        days: Number of days to retrieve (1-90, default 30)

    Returns:
        Dict with period, daily_data, weekly_summary, and last_updated
    """
    start_date, end_date = _get_date_range(days)

    # Use pre-calculated duration expression
    duration_expr = _DURATION_EXPR

    # Fetch aggregated daily data with duration stats
    raw_data = (
        Nap.objects.filter(
            child_id=child_id,
            napped_at__date__gte=start_date,
            napped_at__date__lte=end_date,
        )
        .annotate(date=TruncDate("napped_at"))
        .values("date")
        .annotate(
            count=Count("id"),
            average_duration=Avg(
                duration_expr,
                filter=Q(ended_at__isnull=False),
            ),
            total_minutes=Sum(
                duration_expr,
                filter=Q(ended_at__isnull=False),
            ),
        )
        .order_by("date")
    )

    daily_data = list(
        raw_data.values("date", "count", "average_duration", "total_minutes")
    )

    daily_data = _fill_date_gaps(daily_data, days)

    return {
        "period": f"{start_date} to {end_date}",
        "child_id": child_id,
        "daily_data": daily_data,
        "weekly_summary": _weekly_summary_from_daily(daily_data),
        "last_updated": timezone.now().isoformat(),
    }


def _aggregate_feedings(feeding_filter: Q) -> dict[str, Any]:
    """Aggregate feeding count, total_oz, and breakdown by feeding_type. Shared by today/weekly summary."""
    stats = Feeding.objects.filter(feeding_filter).aggregate(
        count=Count("id"),
        total_oz=Sum("amount_oz"),
    )
    breakdown = (
        Feeding.objects.filter(feeding_filter)
        .values("feeding_type")
        .annotate(count=Count("id"))
    )
    data = {
        "count": stats["count"] or 0,
        "total_oz": float(stats["total_oz"] or 0),
        "bottle": 0,
        "breast": 0,
    }
    for item in breakdown:
        data[item["feeding_type"]] = item["count"]
    return data


def _aggregate_diapers(diaper_filter: Q) -> dict[str, Any]:
    """Aggregate diaper count and breakdown by change_type. Shared by today/weekly summary."""
    stats = DiaperChange.objects.filter(diaper_filter).aggregate(count=Count("id"))
    breakdown = (
        DiaperChange.objects.filter(diaper_filter)
        .values("change_type")
        .annotate(count=Count("id"))
    )
    data = {"count": stats["count"] or 0, "wet": 0, "dirty": 0, "both": 0}
    for item in breakdown:
        data[item["change_type"]] = item["count"]
    return data


def _aggregate_naps(nap_filter: Q) -> dict[str, Any]:
    """Aggregate nap count and duration stats. Shared by today/weekly summary."""
    nap_stats = Nap.objects.filter(nap_filter).aggregate(
        count=Count("id"),
        total_minutes=Sum(_DURATION_EXPR, filter=Q(ended_at__isnull=False)),
        avg_duration=Avg(_DURATION_EXPR, filter=Q(ended_at__isnull=False)),
    )
    return {
        "naps": nap_stats["count"] or 0,
        "total_minutes": (
            int(round(nap_stats["total_minutes"])) if nap_stats["total_minutes"] else 0
        ),
        "avg_duration": (
            int(round(nap_stats["avg_duration"])) if nap_stats["avg_duration"] else 0
        ),
    }


def _today_utc_range(user_timezone: str):
    """Return (start_utc, end_utc) for the current calendar day in user's timezone.

    Used so "today" in the summary matches what the user sees (e.g. EST midnight
    boundary, not UTC). Uses module-level timezone so tests can patch
    analytics.utils.timezone.now.
    """
    user_tz = ZoneInfo(user_timezone)
    now_utc = timezone.now()
    now_local = now_utc.astimezone(user_tz)
    local_today = now_local.date()
    start_of_day = datetime(
        local_today.year,
        local_today.month,
        local_today.day,
        0,
        0,
        0,
        tzinfo=user_tz,
    )
    end_of_day = start_of_day + timedelta(days=1)
    start_utc = start_of_day.astimezone(ZoneInfo("UTC"))
    end_utc = end_of_day.astimezone(ZoneInfo("UTC"))
    return start_utc, end_utc


def get_today_summary(
    child_id: int,
    *,
    user_timezone: str | None = None,
) -> dict[str, Any]:
    """Get today's activity summary for a child.

    Quickly summarizes today's feedings, diapers, and naps. "Today" is the
    current calendar day in the user's timezone when user_timezone is set;
    otherwise UTC (for backward compatibility).

    Args:
        child_id: The child's ID
        user_timezone: Optional IANA timezone (e.g. America/New_York). When set,
            events are counted for the calendar day in this timezone.

    Returns:
        Dict with feedings, diapers, sleep counts and totals
    """
    if user_timezone:
        start_utc, end_utc = _today_utc_range(user_timezone)
        feeding_filter = Q(child_id=child_id, fed_at__gte=start_utc, fed_at__lt=end_utc)
        diaper_filter = Q(
            child_id=child_id,
            changed_at__gte=start_utc,
            changed_at__lt=end_utc,
        )
        nap_filter = Q(
            child_id=child_id,
            napped_at__gte=start_utc,
            napped_at__lt=end_utc,
        )
    else:
        today = timezone.now().date()
        feeding_filter = Q(child_id=child_id, fed_at__date=today)
        diaper_filter = Q(child_id=child_id, changed_at__date=today)
        nap_filter = Q(child_id=child_id, napped_at__date=today)

    feeding_data = _aggregate_feedings(feeding_filter)
    diaper_data = _aggregate_diapers(diaper_filter)
    sleep_data = _aggregate_naps(nap_filter)

    return {
        "child_id": child_id,
        "period": "today",
        "feedings": feeding_data,
        "diapers": diaper_data,
        "sleep": sleep_data,
        "last_updated": timezone.now().isoformat(),
    }


def get_weekly_summary(child_id: int) -> dict[str, Any]:
    """Get this week's activity summary for a child.

    Summarizes the past 7 days of activity.

    Args:
        child_id: The child's ID

    Returns:
        Dict with weekly feedings, diapers, and sleep statistics
    """
    today = timezone.now().date()
    week_start = today - timedelta(days=6)
    week_filter = Q(
        child_id=child_id,
        fed_at__date__gte=week_start,
        fed_at__date__lte=today,
    )
    diaper_week_filter = Q(
        child_id=child_id,
        changed_at__date__gte=week_start,
        changed_at__date__lte=today,
    )
    nap_week_filter = Q(
        child_id=child_id,
        napped_at__date__gte=week_start,
        napped_at__date__lte=today,
    )

    feeding_data = _aggregate_feedings(week_filter)
    diaper_data = _aggregate_diapers(diaper_week_filter)
    sleep_data = _aggregate_naps(nap_week_filter)

    return {
        "child_id": child_id,
        "period": f"{week_start} to {today}",
        "feedings": feeding_data,
        "diapers": diaper_data,
        "sleep": sleep_data,
        "last_updated": timezone.now().isoformat(),
    }


def build_analytics_csv(
    feeding_data: dict,
    diaper_data: dict,
    sleep_data: dict,
    child_name: str,
    days: int,
) -> tuple[str, str]:
    """Build analytics CSV content and filename. Shared by children.views and analytics.views.

    Returns:
        (csv_content, suggested_filename)
    """
    feeding_by_date = {d["date"]: d for d in feeding_data.get("daily_data", [])}
    diaper_by_date = {d["date"]: d for d in diaper_data.get("daily_data", [])}
    sleep_by_date = {d["date"]: d for d in sleep_data.get("daily_data", [])}
    all_dates = sorted(
        set(feeding_by_date.keys())
        | set(diaper_by_date.keys())
        | set(sleep_by_date.keys())
    )
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Date",
            "Feedings (count)",
            "Feedings (avg duration min)",
            "Feedings (total oz)",
            "Diaper Changes (count)",
            "Diaper Changes (wet)",
            "Diaper Changes (dirty)",
            "Diaper Changes (both)",
            "Naps (count)",
            "Naps (avg duration min)",
            "Naps (total minutes)",
        ]
    )
    for d in all_dates:
        feeding = feeding_by_date.get(d, {})
        diaper = diaper_by_date.get(d, {})
        sleep = sleep_by_date.get(d, {})
        writer.writerow(
            [
                d,
                feeding.get("count", 0),
                feeding.get("average_duration") or "",
                feeding.get("total_oz") or "",
                diaper.get("count", 0),
                diaper.get("wet_count", 0),
                diaper.get("dirty_count", 0),
                diaper.get("both_count", 0),
                sleep.get("count", 0),
                sleep.get("average_duration") or "",
                sleep.get("total_minutes") or "",
            ]
        )
    filename = f"analytics-{child_name.replace(' ', '_')}-{days}days.csv"
    return buffer.getvalue(), filename


# Timeline: fetch up to this many per type before merge (matches children.views)
TIMELINE_FETCH_PER_TYPE = 100


def get_child_timeline_events(
    child_id: int, limit_per_type: int = TIMELINE_FETCH_PER_TYPE
) -> list[dict[str, Any]]:
    """Build a merged chronological timeline of feedings, diapers, and naps.

    Fetches the most recent events per type, merges by timestamp, and returns
    a single list sorted by time descending (newest first).

    Args:
        child_id: The child's ID
        limit_per_type: Max events to fetch per type (default 100)

    Returns:
        List of event dicts, each with "type", "at" (datetime), and a type-keyed
        payload ("feeding", "diaper", or "nap"). Datetimes are timezone-aware UTC.
    """
    feedings = list(
        Feeding.objects.filter(child_id=child_id)
        .order_by("-fed_at")[:limit_per_type]
        .values("id", "fed_at", "feeding_type", "amount_oz", "duration_minutes", "side")
    )
    diapers = list(
        DiaperChange.objects.filter(child_id=child_id)
        .order_by("-changed_at")[:limit_per_type]
        .values("id", "changed_at", "change_type")
    )
    naps = list(
        Nap.objects.filter(child_id=child_id)
        .order_by("-napped_at")[:limit_per_type]
        .values("id", "napped_at", "ended_at")
    )
    # Nap duration_minutes is a model property; compute for API payload
    naps_list: list[dict[str, Any]] = cast(list[dict[str, Any]], list(naps))
    for n in naps_list:
        if n.get("ended_at") and n.get("napped_at"):
            total_sec = (n["ended_at"] - n["napped_at"]).total_seconds()
            n["duration_minutes"] = int(round(total_sec / 60))
        else:
            n["duration_minutes"] = None

    merged: list[dict[str, Any]] = []
    for f in feedings:
        merged.append({"type": "feeding", "at": f["fed_at"], "feeding": f})
    for d in diapers:
        merged.append({"type": "diaper", "at": d["changed_at"], "diaper": d})
    for n in naps_list:
        merged.append({"type": "nap", "at": n["napped_at"], "nap": n})
    merged.sort(key=lambda x: x["at"] or datetime.min, reverse=True)
    return merged


# --- Pattern Alerts ---

# Minimum data points before alerts can fire
_MIN_FEEDINGS_FOR_ALERT = 4  # need 3+ intervals
_MIN_COMPLETED_NAPS_FOR_ALERT = 3  # need 2+ wake windows

# Alert fires at 1.1x the average (10% buffer)
_ALERT_THRESHOLD_MULTIPLIER = 1.1


def _format_hours_minutes(total_minutes: float) -> str:
    """Format minutes as '{X}h {Y}m' string, omitting zero parts."""
    hours = int(total_minutes // 60)
    minutes = int(round(total_minutes % 60))
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def _compute_interval_alert(child_id: int, now: datetime) -> dict[str, Any]:
    """Compute feeding interval alert for a child.

    Returns a dict with alert status, message, avg_interval_minutes,
    minutes_since_last, last_fed_at, and data_points.
    """
    seven_days_ago = now - timedelta(days=7)

    feedings = list(
        Feeding.objects.filter(
            child_id=child_id,
            fed_at__gte=seven_days_ago,
        )
        .order_by("fed_at")
        .values_list("fed_at", flat=True)
    )

    data_points = len(feedings)

    no_alert = {
        "alert": False,
        "message": None,
        "avg_interval_minutes": None,
        "minutes_since_last": None,
        "last_fed_at": None,
        "data_points": data_points,
    }

    if data_points < _MIN_FEEDINGS_FOR_ALERT:
        return no_alert

    # Calculate intervals between consecutive feedings
    intervals = []
    for i in range(1, len(feedings)):
        delta = (feedings[i] - feedings[i - 1]).total_seconds() / 60
        intervals.append(delta)

    avg_interval = sum(intervals) / len(intervals)
    last_fed_at = feedings[-1]
    minutes_since = (now - last_fed_at).total_seconds() / 60
    threshold = avg_interval * _ALERT_THRESHOLD_MULTIPLIER

    result = {
        "alert": False,
        "message": None,
        "avg_interval_minutes": round(avg_interval),
        "minutes_since_last": round(minutes_since),
        "last_fed_at": last_fed_at.isoformat(),
        "data_points": data_points,
    }

    if minutes_since > threshold:
        avg_fmt = _format_hours_minutes(avg_interval)
        elapsed_fmt = _format_hours_minutes(minutes_since)
        result["alert"] = True
        result["message"] = (
            f"Baby usually feeds every {avg_fmt} — it's been {elapsed_fmt}"
        )

    return result


def _compute_wake_alert(child_id: int, now: datetime) -> dict[str, Any]:
    """Compute nap wake-window alert for a child.

    Returns a dict with alert status, message, avg_wake_window_minutes,
    minutes_awake, last_nap_ended_at, and data_points.
    """
    seven_days_ago = now - timedelta(days=7)

    completed_naps = list(
        Nap.objects.filter(
            child_id=child_id,
            napped_at__gte=seven_days_ago,
            ended_at__isnull=False,
        )
        .order_by("napped_at")
        .values_list("napped_at", "ended_at")
    )

    data_points = len(completed_naps)

    no_alert = {
        "alert": False,
        "message": None,
        "avg_wake_window_minutes": None,
        "minutes_awake": None,
        "last_nap_ended_at": None,
        "data_points": data_points,
    }

    if data_points < _MIN_COMPLETED_NAPS_FOR_ALERT:
        return no_alert

    # Calculate wake windows: time from nap end to next nap start
    wake_windows = []
    for i in range(1, len(completed_naps)):
        prev_ended = completed_naps[i - 1][1]  # ended_at
        curr_started = completed_naps[i][0]  # napped_at
        wake_min = (curr_started - prev_ended).total_seconds() / 60
        if wake_min > 0:
            wake_windows.append(wake_min)

    if not wake_windows:
        return no_alert

    avg_wake = sum(wake_windows) / len(wake_windows)
    last_ended = completed_naps[-1][1]  # ended_at of most recent
    minutes_awake = (now - last_ended).total_seconds() / 60
    threshold = avg_wake * _ALERT_THRESHOLD_MULTIPLIER

    result = {
        "alert": False,
        "message": None,
        "avg_wake_window_minutes": round(avg_wake),
        "minutes_awake": round(minutes_awake),
        "last_nap_ended_at": last_ended.isoformat(),
        "data_points": data_points,
    }

    if minutes_awake > threshold:
        avg_fmt = _format_hours_minutes(avg_wake)
        awake_fmt = _format_hours_minutes(minutes_awake)
        result["alert"] = True
        result["message"] = (
            f"Baby usually naps after ~{avg_fmt} awake — awake for {awake_fmt}"
        )

    return result


def compute_pattern_alerts(
    child_id: int, now: datetime | None = None
) -> dict[str, Any]:
    """Compute pattern alerts for a child based on feeding and nap history.

    Analyzes the last 7 days of data to detect when current gaps exceed
    the child's own historical patterns (with 10% buffer).

    Args:
        child_id: The child's ID
        now: Optional override for current time (for testing)

    Returns:
        Dict with child_id, feeding alert data, and nap alert data
    """
    if now is None:
        now = timezone.now()

    return {
        "child_id": child_id,
        "feeding": _compute_interval_alert(child_id, now),
        "nap": _compute_wake_alert(child_id, now),
    }
