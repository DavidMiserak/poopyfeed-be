"""Caching utilities for child tracking data annotations.

Provides efficient caching of expensive last-activity annotations
(last_diaper_change, last_nap, last_feeding) that are frequently accessed
but expensive to compute via database aggregations.

Cache values are stored in JSON-safe form (datetime as ISO string) so the
Redis cache backend can use JSON serialization and avoid pickle errors.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Type for the activities dict returned per child
ChildActivitiesDict = dict[str, datetime | None]

# JSON-serializable shape stored in Redis (ISO string or null)
ChildActivitiesCacheDict = dict[str, str | None]


def _activities_to_cache(activities: ChildActivitiesDict) -> ChildActivitiesCacheDict:
    """Convert activities dict to JSON-serializable form for cache.

    Args:
        activities: Dict with last_diaper_change, last_nap, last_feeding (datetime or None).

    Returns:
        Dict with same keys and ISO datetime strings (or None) for Redis/JSON storage.
    """

    def _iso(dt: datetime | None) -> str | None:
        return dt.isoformat() if dt is not None else None

    return {
        "last_diaper_change": _iso(activities.get("last_diaper_change")),
        "last_nap": _iso(activities.get("last_nap")),
        "last_feeding": _iso(activities.get("last_feeding")),
    }


def _activities_from_cache(raw: ChildActivitiesCacheDict) -> ChildActivitiesDict:
    """Parse cache dict (ISO strings) back to ChildActivitiesDict (datetime | None).

    Args:
        raw: Dict from cache with last_diaper_change, last_nap, last_feeding as ISO str or None.

    Returns:
        Dict with same keys and timezone-aware datetimes (or None).
    """

    def parse(v: str | None) -> datetime | None:
        if v is None:
            return None
        return datetime.fromisoformat(v.replace("Z", "+00:00"))

    return {
        "last_diaper_change": parse(raw.get("last_diaper_change")),
        "last_nap": parse(raw.get("last_nap")),
        "last_feeding": parse(raw.get("last_feeding")),
    }


def get_child_last_activities(
    child_ids: list[int],
) -> dict[int, ChildActivitiesDict]:
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

    # If all are cached, return immediately (parse JSON-safe form to datetimes)
    if not missing_child_ids:
        logger.debug(
            f"Cache HIT for all children: {child_ids}",
            extra={"hit_count": len(child_ids)},
        )
        return {
            child_id: _activities_from_cache(
                cached_results[f"child_activities_{child_id}"]
            )
            for child_id in child_ids
        }

    logger.debug(
        f"Cache MISS for children: {missing_child_ids}",
        extra={"miss_count": len(missing_child_ids), "total": len(child_ids)},
    )

    # Query database for missing children using "last row per child" per model
    from diapers.models import DiaperChange
    from feedings.models import Feeding
    from naps.models import Nap

    def _latest_by_child(
        model, ts_field: str, ids: list[int]
    ) -> dict[int, datetime | None]:
        if not ids:
            return {}
        qs = (
            model.objects.filter(child_id__in=ids)
            .order_by("child_id", f"-{ts_field}")
            .distinct("child_id")
            .values_list("child_id", ts_field)
        )
        return {child_id: ts for child_id, ts in qs}

    last_diapers = _latest_by_child(DiaperChange, "changed_at", missing_child_ids)
    last_naps = _latest_by_child(Nap, "napped_at", missing_child_ids)
    last_feedings = _latest_by_child(Feeding, "fed_at", missing_child_ids)

    # Convert query results to dict and cache each child's activities
    missing_dict = {}
    cache_to_set = {}

    for child_id in missing_child_ids:
        activities = {
            "last_diaper_change": last_diapers.get(child_id),
            "last_nap": last_naps.get(child_id),
            "last_feeding": last_feedings.get(child_id),
        }
        missing_dict[child_id] = activities
        cache_to_set[f"child_activities_{child_id}"] = _activities_to_cache(activities)

    # Cache the results (1 hour TTL - signal-based invalidation ensures freshness
    # on writes, so the TTL is just a safety net for idle periods)
    if cache_to_set:
        cache.set_many(cache_to_set, 3600)

    # Merge cached and newly-fetched results (parse cache entries to datetimes)
    result = {}
    for child_id in child_ids:
        cache_key = f"child_activities_{child_id}"
        if cache_key in cached_results:
            result[child_id] = _activities_from_cache(cached_results[cache_key])
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


def invalidate_child_activities_cache(child_id: int) -> None:
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
