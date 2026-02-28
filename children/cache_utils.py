"""Caching utilities for child tracking data annotations.

Provides efficient caching of expensive last-activity annotations
(last_diaper_change, last_nap, last_feeding) that are frequently accessed
but expensive to compute via database aggregations.
"""

import logging

from django.core.cache import cache
from django.db.models import Max

logger = logging.getLogger(__name__)


def get_child_last_activities(child_ids):
    """Get last activity timestamps for multiple children from cache or database.

    Args:
        child_ids: List of child IDs to fetch annotations for

    Returns:
        Dict of {child_id: {
            'last_diaper_change': datetime or None,
            'last_nap': datetime or None,
            'last_feeding': datetime or None
        }}

    This method tries to fetch cached annotations for each child. For any
    missing from cache, queries the database once using a single query for
    all missing children. This is far more efficient than the per-request
    .annotate() pattern which required 3 expensive Max() aggregations per
    child list request.
    """
    if not child_ids:
        return {}

    # Try to get cached values for each child
    cache_keys = [f"child_activities_{child_id}" for child_id in child_ids]
    cached_results = cache.get_many(cache_keys)

    # Find which children are missing from cache
    missing_child_ids = [
        child_id
        for child_id, cache_key in zip(child_ids, cache_keys)
        if cache_key not in cached_results
    ]

    # If all are cached, return immediately
    if not missing_child_ids:
        logger.debug(
            f"Cache HIT for all children: {child_ids}",
            extra={"hit_count": len(child_ids)},
        )
        return {
            child_id: cached_results[f"child_activities_{child_id}"]
            for child_id in child_ids
        }

    logger.debug(
        f"Cache MISS for children: {missing_child_ids}",
        extra={"miss_count": len(missing_child_ids), "total": len(child_ids)},
    )

    # Query database for missing children - single query for all missing
    from children.models import Child

    missing_data = (
        Child.objects.filter(id__in=missing_child_ids)
        .annotate(
            last_diaper_change=Max("diaper_changes__changed_at"),
            last_nap=Max("naps__napped_at"),
            last_feeding=Max("feedings__fed_at"),
        )
        .values(
            "id",
            "last_diaper_change",
            "last_nap",
            "last_feeding",
        )
    )

    # Convert query results to dict and cache each child's activities
    missing_dict = {}
    cache_to_set = {}

    for item in missing_data:
        child_id = item["id"]
        activities = {
            "last_diaper_change": item["last_diaper_change"],
            "last_nap": item["last_nap"],
            "last_feeding": item["last_feeding"],
        }
        missing_dict[child_id] = activities
        cache_to_set[f"child_activities_{child_id}"] = activities

    # Cache the results (5 minute TTL - balance between freshness and performance)
    # Cache invalidates automatically when tracking records change via signals
    if cache_to_set:
        cache.set_many(cache_to_set, 300)

    # Merge cached and newly-fetched results
    result = {}
    for child_id in child_ids:
        cache_key = f"child_activities_{child_id}"
        if cache_key in cached_results:
            result[child_id] = cached_results[cache_key]
        else:
            result[child_id] = missing_dict.get(
                child_id,
                {
                    "last_diaper_change": None,
                    "last_nap": None,
                    "last_feeding": None,
                },
            )

    return result


def invalidate_child_activities_cache(child_id):
    """Invalidate cached last-activity annotations for a child.

    Called when any tracking record (DiaperChange, Feeding, Nap) is created,
    updated, or deleted for the child. Ensures the next request fetches
    fresh data from the database.

    Uses transaction.on_commit() to defer cache invalidation until after
    the database transaction commits, preventing race conditions where
    the cache is cleared before data is persisted.

    Args:
        child_id: The ID of the child whose cache should be invalidated
    """
    from django.db import transaction

    def clear_cache():
        cache_key = f"child_activities_{child_id}"
        try:
            cache.delete(cache_key)
            logger.info(
                f"Invalidated child activities cache",
                extra={"child_id": child_id, "cache_key": cache_key},
            )
        except Exception as e:
            # Log cache deletion failures (e.g., Redis connection issues)
            # This prevents silent failures where stale cache persists
            logger.error(
                f"Failed to invalidate child activities cache: {e}",
                extra={
                    "child_id": child_id,
                    "cache_key": cache_key,
                    "error": str(e),
                },
                exc_info=True,
            )

    # Schedule invalidation to run after transaction commits
    transaction.on_commit(clear_cache)
