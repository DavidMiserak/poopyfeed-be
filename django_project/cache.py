"""Custom Redis cache backend that tolerates deserialization (pickle) errors.

django-redis uses pickle by default to serialize cache values. Occasional
UnpicklingError or AttributeError/ModuleNotFoundError can occur due to:
- Python version or protocol mismatch across deploys
- Corrupt or truncated bytes in Redis
- Class/module renames or moves in code

This backend wraps get/get_many to treat deserialization failures as cache
miss: delete the bad key(s), log for observability, and return None or omit
from results so the app recomputes and repopulates cache.
"""

import json
import logging
import pickle  # nosec B403 - only used to catch UnpicklingError, no unpickling of untrusted data

from django_redis.cache import RedisCache  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Exceptions that indicate corrupted or incompatible cached payloads.
# Pickle: UnpicklingError, AttributeError/ModuleNotFoundError (class missing).
# JSON: JSONDecodeError (e.g. reading old pickle bytes with JSON serializer).
# Generic: EOFError, ValueError (corrupt/truncated bytes).
_DESERIALIZE_ERRORS = (
    pickle.UnpicklingError,
    AttributeError,
    ModuleNotFoundError,
    ImportError,
    EOFError,
    ValueError,
    json.JSONDecodeError,
)


class SafeRedisCache(RedisCache):
    """Redis cache backend that treats deserialization errors as cache miss.

    On get() or get_many(), if the backend raises a deserialization-related
    error, the key(s) are deleted, a warning is logged (for SLO/alerting),
    and the caller receives None or partial results so the app can recompute.
    """

    def get(self, key, default=None, version=None):
        """Return cached value or default; on deserialization error, delete key and return default.

        Args:
            key: Cache key.
            default: Value to return on miss or deserialization error.
            version: Optional key version.

        Returns:
            Cached value or default.
        """
        try:
            return super().get(key, default=default, version=version)
        except _DESERIALIZE_ERRORS as e:
            self._handle_deserialize_error(key, e, version)
            return default

    def get_many(self, keys, version=None):
        """Return dict of cached values; on deserialization error, delete requested keys and return {}.

        Args:
            keys: List of cache keys.
            version: Optional key version.

        Returns:
            Dict mapping key to value for successful hits; empty dict if any key causes deserialization error.
        """
        try:
            return super().get_many(keys, version=version)
        except _DESERIALIZE_ERRORS as e:
            # get_many can fail on first bad key; we don't know which key
            # caused it. Delete all requested keys to clear any bad entries.
            for key in keys:
                self._delete_key_safe(key, version)
            logger.warning(
                "Redis cache get_many deserialization error; treated keys as miss",
                extra={
                    "keys": list(keys),
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
                exc_info=True,
            )
            return {}  # No hits; caller will treat all as miss

    def _handle_deserialize_error(self, key, error, version=None):
        """Delete the bad key and log a warning.

        Args:
            key: Cache key that caused the error.
            error: The deserialization exception.
            version: Optional key version.
        """
        self._delete_key_safe(key, version)
        logger.warning(
            "Redis cache get deserialization error; treated as miss",
            extra={
                "cache_key": key,
                "error_type": type(error).__name__,
                "error": str(error),
            },
            exc_info=True,
        )

    def _delete_key_safe(self, key, version=None):
        """Delete a cache key; log and swallow any exception from the backend.

        Args:
            key: Cache key to delete.
            version: Optional key version.
        """
        try:
            self.delete(key, version=version)
        except Exception as delete_err:
            logger.warning(
                "Failed to delete bad cache key after deserialize error",
                extra={"cache_key": key, "delete_error": str(delete_err)},
            )
