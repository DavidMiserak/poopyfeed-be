"""Cache key management and invalidation for analytics.

Centralizes all cache key generation and provides functions to safely
invalidate analytics caches when tracking records change.
"""

from django.core.cache import cache
from django.db import transaction

DASHBOARD_SUMMARY_INVALIDATED_KEY = "analytics:dashboard-summary-invalidated:{child_id}"


def _get_analytics_cache_keys(child_id: int) -> list[str]:
    """Generate all cache keys for a child's analytics.

    Args:
        child_id: The child's ID

    Returns:
        List of all cache keys for this child
    """
    # Supported day ranges: includes 7/14 used by web UI analytics view
    day_ranges = [7, 14, 30, 60, 90]

    keys = []

    # Trend endpoints (vary by day range)
    for days in day_ranges:
        keys.extend(
            [
                f"analytics:feeding-trends:{child_id}:{days}",
                f"analytics:diaper-patterns:{child_id}:{days}",
                f"analytics:sleep-summary:{child_id}:{days}",
            ]
        )

    # Summary endpoints (no day range)
    keys.extend(
        [
            f"analytics:today-summary:{child_id}",
            f"analytics:weekly-summary:{child_id}",
            f"analytics:pattern-alerts:{child_id}",
            f"analytics:timeline:{child_id}",
        ]
    )

    return keys


def invalidate_child_analytics(child_id: int) -> None:
    """Invalidate all analytics caches for a child.

    Clears all cached analytics data for the given child and sets a sentinel
    so the batch dashboard-summary cache is skipped until TTL expires.

    Args:
        child_id: The child's ID
    """
    keys = _get_analytics_cache_keys(child_id)
    cache.delete_many(keys)
    sentinel_key = DASHBOARD_SUMMARY_INVALIDATED_KEY.format(child_id=child_id)
    cache.set(sentinel_key, 1, timeout=300)
