"""Aggregation utilities for analytics calculations.

Functions to compute trends, patterns, and summaries from raw tracking data.
All aggregations are performed at the database level using Django ORM
aggregation functions for efficiency.
"""

from datetime import date, datetime, timedelta
from typing import Any

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
    Func(F("ended_at") - F("napped_at"), function="", template="EXTRACT(EPOCH FROM %(expressions)s)") / 60,
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

    if not first_half or not second_half:
        return "stable"

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

    # Calculate weekly summary
    counts = [d["count"] for d in daily_data]
    avg_per_day = sum(counts) / len(counts) if counts else 0
    trend = _calculate_trend(counts)
    variance = _calculate_variance(counts)

    return {
        "period": f"{start_date} to {end_date}",
        "child_id": child_id,
        "daily_data": daily_data,
        "weekly_summary": {
            "avg_per_day": round(avg_per_day, 2),
            "trend": trend,
            "variance": variance,
        },
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

    # Calculate weekly summary
    counts = [d["count"] for d in daily_data]
    avg_per_day = sum(counts) / len(counts) if counts else 0
    trend = _calculate_trend(counts)
    variance = _calculate_variance(counts)

    return {
        "period": f"{start_date} to {end_date}",
        "child_id": child_id,
        "daily_data": daily_data,
        "weekly_summary": {
            "avg_per_day": round(avg_per_day, 2),
            "trend": trend,
            "variance": variance,
        },
        "breakdown": period_breakdown,
        "last_updated": timezone.now().isoformat(),
    }


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

    daily_data = list(raw_data.values("date", "count", "average_duration", "total_minutes"))

    daily_data = _fill_date_gaps(daily_data, days)

    # Calculate weekly summary
    counts = [d["count"] for d in daily_data]
    avg_per_day = sum(counts) / len(counts) if counts else 0
    trend = _calculate_trend(counts)
    variance = _calculate_variance(counts)

    return {
        "period": f"{start_date} to {end_date}",
        "child_id": child_id,
        "daily_data": daily_data,
        "weekly_summary": {
            "avg_per_day": round(avg_per_day, 2),
            "trend": trend,
            "variance": variance,
        },
        "last_updated": timezone.now().isoformat(),
    }


def get_today_summary(child_id: int) -> dict[str, Any]:
    """Get today's activity summary for a child.

    Quickly summarizes today's feedings, diapers, and naps.

    Args:
        child_id: The child's ID

    Returns:
        Dict with feedings, diapers, sleep counts and totals
    """
    today = timezone.now().date()

    # Get today's feedings
    feeding_stats = Feeding.objects.filter(
        child_id=child_id,
        fed_at__date=today,
    ).aggregate(
        count=Count("id"),
        total_oz=Sum("amount_oz"),
    )

    feeding_breakdown = (
        Feeding.objects.filter(
            child_id=child_id,
            fed_at__date=today,
        )
        .values("feeding_type")
        .annotate(count=Count("id"))
    )

    feeding_data = {
        "count": feeding_stats["count"] or 0,
        "total_oz": float(feeding_stats["total_oz"] or 0),
        "bottle": 0,
        "breast": 0,
    }
    for item in feeding_breakdown:
        feeding_data[item["feeding_type"]] = item["count"]

    # Get today's diaper changes
    diaper_stats = DiaperChange.objects.filter(
        child_id=child_id,
        changed_at__date=today,
    ).aggregate(count=Count("id"))

    diaper_breakdown = (
        DiaperChange.objects.filter(
            child_id=child_id,
            changed_at__date=today,
        )
        .values("change_type")
        .annotate(count=Count("id"))
    )

    diaper_data = {
        "count": diaper_stats["count"] or 0,
        "wet": 0,
        "dirty": 0,
        "both": 0,
    }
    for item in diaper_breakdown:
        diaper_data[item["change_type"]] = item["count"]

    # Get today's naps with duration stats
    duration_expr = _DURATION_EXPR
    nap_stats = Nap.objects.filter(
        child_id=child_id,
        napped_at__date=today,
    ).aggregate(
        count=Count("id"),
        total_minutes=Sum(duration_expr, filter=Q(ended_at__isnull=False)),
        avg_duration=Avg(duration_expr, filter=Q(ended_at__isnull=False)),
    )

    sleep_data = {
        "naps": nap_stats["count"] or 0,
        "total_minutes": int(round(nap_stats["total_minutes"]))
        if nap_stats["total_minutes"]
        else 0,
        "avg_duration": int(round(nap_stats["avg_duration"]))
        if nap_stats["avg_duration"]
        else 0,
    }

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

    # Get week's feedings
    feeding_stats = Feeding.objects.filter(
        child_id=child_id,
        fed_at__date__gte=week_start,
        fed_at__date__lte=today,
    ).aggregate(
        count=Count("id"),
        total_oz=Sum("amount_oz"),
    )

    feeding_breakdown = (
        Feeding.objects.filter(
            child_id=child_id,
            fed_at__date__gte=week_start,
            fed_at__date__lte=today,
        )
        .values("feeding_type")
        .annotate(count=Count("id"))
    )

    feeding_data = {
        "count": feeding_stats["count"] or 0,
        "total_oz": float(feeding_stats["total_oz"] or 0),
        "bottle": 0,
        "breast": 0,
    }
    for item in feeding_breakdown:
        feeding_data[item["feeding_type"]] = item["count"]

    # Get week's diaper changes
    diaper_stats = DiaperChange.objects.filter(
        child_id=child_id,
        changed_at__date__gte=week_start,
        changed_at__date__lte=today,
    ).aggregate(count=Count("id"))

    diaper_breakdown = (
        DiaperChange.objects.filter(
            child_id=child_id,
            changed_at__date__gte=week_start,
            changed_at__date__lte=today,
        )
        .values("change_type")
        .annotate(count=Count("id"))
    )

    diaper_data = {
        "count": diaper_stats["count"] or 0,
        "wet": 0,
        "dirty": 0,
        "both": 0,
    }
    for item in diaper_breakdown:
        diaper_data[item["change_type"]] = item["count"]

    # Get week's naps with duration stats
    duration_expr = _DURATION_EXPR
    nap_stats = Nap.objects.filter(
        child_id=child_id,
        napped_at__date__gte=week_start,
        napped_at__date__lte=today,
    ).aggregate(
        count=Count("id"),
        total_minutes=Sum(duration_expr, filter=Q(ended_at__isnull=False)),
        avg_duration=Avg(duration_expr, filter=Q(ended_at__isnull=False)),
    )

    sleep_data = {
        "naps": nap_stats["count"] or 0,
        "total_minutes": int(round(nap_stats["total_minutes"]))
        if nap_stats["total_minutes"]
        else 0,
        "avg_duration": int(round(nap_stats["avg_duration"]))
        if nap_stats["avg_duration"]
        else 0,
    }

    return {
        "child_id": child_id,
        "period": f"{week_start} to {today}",
        "feedings": feeding_data,
        "diapers": diaper_data,
        "sleep": sleep_data,
        "last_updated": timezone.now().isoformat(),
    }
