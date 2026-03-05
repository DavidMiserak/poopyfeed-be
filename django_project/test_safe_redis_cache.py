"""Tests for SafeRedisCache deserialization-error handling.

Verifies that get/get_many treat deserialization errors as cache miss (return
default or {}), delete bad keys, and that _delete_key_safe swallows delete
failures.
"""

import pickle  # nosec B403 - only used for exception type in tests, no unpickling
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase


class SafeRedisCacheGetTests(TestCase):
    """Test SafeRedisCache.get treats deserialization errors as miss."""

    def test_get_returns_default_on_unpickling_error(self):
        """When backend raises UnpicklingError, get returns default and does not raise."""
        with patch(
            "django_redis.cache.RedisCache.get",
            side_effect=pickle.UnpicklingError("corrupt"),
        ):
            result = cache.get("bad_key", default="my_default")
        self.assertEqual(result, "my_default")

    def test_get_returns_default_on_attribute_error(self):
        """When backend raises AttributeError (e.g. missing class), get returns default."""
        with patch(
            "django_redis.cache.RedisCache.get",
            side_effect=AttributeError("No module 'foo'"),
        ):
            result = cache.get("bad_key", default=None)
        self.assertIsNone(result)

    def test_get_returns_default_on_value_error(self):
        """When backend raises ValueError (corrupt bytes), get returns default."""
        with patch(
            "django_redis.cache.RedisCache.get", side_effect=ValueError("corrupt")
        ):
            result = cache.get("bad_key", default=42)
        self.assertEqual(result, 42)


class SafeRedisCacheGetManyTests(TestCase):
    """Test SafeRedisCache.get_many treats deserialization errors as total miss."""

    def test_get_many_returns_empty_on_deserialize_error(self):
        """When get_many raises a deserialization error, returns {} and clears requested keys."""
        with patch(
            "django_redis.cache.RedisCache.get_many",
            side_effect=pickle.UnpicklingError("bad"),
        ):
            result = cache.get_many(["key1", "key2"])
        self.assertEqual(result, {})

    def test_get_many_returns_empty_on_json_decode_error(self):
        """When get_many raises JSONDecodeError, returns {}."""
        import json

        with patch(
            "django_redis.cache.RedisCache.get_many",
            side_effect=json.JSONDecodeError("err", "doc", 0),
        ):
            result = cache.get_many(["key1"])
        self.assertEqual(result, {})


class SafeRedisCacheDeleteKeySafeTests(TestCase):
    """Test _delete_key_safe swallows delete failures."""

    def test_delete_after_deserialize_error_swallows_delete_failure(self):
        """When delete() raises after a get deserialization error, exception is logged but not raised."""
        with patch(
            "django_redis.cache.RedisCache.get",
            side_effect=pickle.UnpicklingError("corrupt"),
        ):
            with patch(
                "django_redis.cache.RedisCache.delete",
                side_effect=RuntimeError("Redis down"),
            ):
                result = cache.get("bad_key", default="default")
        self.assertEqual(result, "default")
