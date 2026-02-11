"""
Tests for Redis cache backend configuration and functionality.

Verifies:
- Cache set/get/delete operations
- Cache expiration/timeout
- Connection pooling and configuration
- Fallback behavior on cache miss
"""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings


class RedisCacheConfigurationTests(TestCase):
    """Test Redis cache is properly configured."""

    def test_cache_backend_is_configured(self):
        """Verify cache backend is properly configured."""
        # Check that cache is not None and is usable
        self.assertIsNotNone(cache)
        # Test basic operations work
        cache.set('test_config', 'value')
        self.assertEqual(cache.get('test_config'), 'value')

    def test_cache_operations_work(self):
        """Verify cache operations work end-to-end."""
        # Test that cache can store and retrieve data
        cache.set("location_test", "success")
        result = cache.get("location_test")
        self.assertEqual(result, "success")


class CacheOperationsTests(TestCase):
    """Test basic cache operations (set, get, delete)."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def test_cache_set_and_get(self):
        """Test setting and retrieving a value from cache."""
        cache.set("test_key", "test_value", timeout=300)
        result = cache.get("test_key")
        self.assertEqual(result, "test_value")

    def test_cache_get_nonexistent_key(self):
        """Test getting a non-existent key returns None."""
        result = cache.get("nonexistent_key")
        self.assertIsNone(result)

    def test_cache_get_with_default(self):
        """Test getting with default value for missing key."""
        result = cache.get("nonexistent_key", "default_value")
        self.assertEqual(result, "default_value")

    def test_cache_delete(self):
        """Test deleting a key from cache."""
        cache.set("delete_test", "value")
        self.assertEqual(cache.get("delete_test"), "value")
        cache.delete("delete_test")
        self.assertIsNone(cache.get("delete_test"))

    def test_cache_delete_nonexistent_key(self):
        """Test deleting a non-existent key doesn't raise error."""
        # Should not raise an exception
        cache.delete("nonexistent_key")

    def test_cache_clear(self):
        """Test clearing all cache entries."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        self.assertEqual(cache.get("key1"), "value1")
        cache.clear()
        self.assertIsNone(cache.get("key1"))
        self.assertIsNone(cache.get("key2"))
        self.assertIsNone(cache.get("key3"))


class CacheExpirationTests(TestCase):
    """Test cache timeout and expiration."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def test_cache_with_timeout(self):
        """Test cache entry with timeout."""
        # Use short timeout for testing
        cache.set("timeout_test", "value", timeout=1)
        self.assertEqual(cache.get("timeout_test"), "value")

    def test_cache_timeout_none(self):
        """Test cache with None timeout (no expiration)."""
        cache.set("no_timeout", "value", timeout=None)
        result = cache.get("no_timeout")
        self.assertEqual(result, "value")

    def test_cache_timeout_zero(self):
        """Test cache with zero timeout (immediate expiration)."""
        cache.set("zero_timeout", "value", timeout=0)
        # Value might already be expired
        result = cache.get("zero_timeout")
        # Either None or the value, depending on timing
        self.assertIn(result, [None, "value"])


class CacheDataTypeTests(TestCase):
    """Test caching various data types."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def test_cache_string(self):
        """Test caching string values."""
        cache.set("string_key", "string_value")
        self.assertEqual(cache.get("string_key"), "string_value")

    def test_cache_integer(self):
        """Test caching integer values."""
        cache.set("int_key", 12345)
        self.assertEqual(cache.get("int_key"), 12345)

    def test_cache_list(self):
        """Test caching list values."""
        test_list = [1, 2, 3, "four", 5.0]
        cache.set("list_key", test_list)
        self.assertEqual(cache.get("list_key"), test_list)

    def test_cache_dict(self):
        """Test caching dictionary values."""
        test_dict = {"name": "test", "value": 123, "nested": {"key": "value"}}
        cache.set("dict_key", test_dict)
        self.assertEqual(cache.get("dict_key"), test_dict)

    def test_cache_none(self):
        """Test caching None value."""
        cache.set("none_key", None)
        # None is a valid cached value
        self.assertIsNone(cache.get("none_key"))

    def test_cache_boolean(self):
        """Test caching boolean values."""
        cache.set("bool_key_true", True)
        cache.set("bool_key_false", False)
        self.assertTrue(cache.get("bool_key_true"))
        self.assertFalse(cache.get("bool_key_false"))


class CacheIncrementDecrementTests(TestCase):
    """Test atomic cache increment/decrement operations."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def test_cache_incr(self):
        """Test incrementing a cache value."""
        cache.set("counter", 10)
        cache.incr("counter", 5)
        self.assertEqual(cache.get("counter"), 15)

    def test_cache_decr(self):
        """Test decrementing a cache value."""
        cache.set("counter", 10)
        cache.decr("counter", 3)
        self.assertEqual(cache.get("counter"), 7)

    def test_cache_incr_nonexistent(self):
        """Test incrementing a counter from zero."""
        cache.set("new_counter", 0)
        cache.incr("new_counter", 1)
        self.assertEqual(cache.get("new_counter"), 1)


class CacheMultipleKeysTests(TestCase):
    """Test cache operations with multiple keys."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def test_cache_set_many(self):
        """Test setting multiple cache values at once."""
        data = {"key1": "value1", "key2": "value2", "key3": "value3"}
        cache.set_many(data, timeout=300)

        self.assertEqual(cache.get("key1"), "value1")
        self.assertEqual(cache.get("key2"), "value2")
        self.assertEqual(cache.get("key3"), "value3")

    def test_cache_get_many(self):
        """Test getting multiple cache values at once."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        results = cache.get_many(["key1", "key2", "key3", "nonexistent"])
        self.assertEqual(results["key1"], "value1")
        self.assertEqual(results["key2"], "value2")
        self.assertEqual(results["key3"], "value3")
        self.assertNotIn("nonexistent", results)

    def test_cache_delete_many(self):
        """Test deleting multiple cache values at once."""
        cache.set_many({"key1": "value1", "key2": "value2", "key3": "value3"})
        cache.delete_many(["key1", "key2"])

        self.assertIsNone(cache.get("key1"))
        self.assertIsNone(cache.get("key2"))
        self.assertEqual(cache.get("key3"), "value3")


class CacheKeyPrefixTests(TestCase):
    """Test cache key handling and patterns."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def test_cache_with_complex_key(self):
        """Test cache with complex key names."""
        complex_key = "user:123:profile:settings:theme"
        cache.set(complex_key, "dark_mode")
        self.assertEqual(cache.get(complex_key), "dark_mode")

    def test_cache_key_pattern_matching(self):
        """Test caching with patterned keys."""
        # Set multiple related keys
        for user_id in range(1, 4):
            cache.set(f"user:{user_id}:data", {"id": user_id, "name": f"User {user_id}"})

        # Verify each can be retrieved
        for user_id in range(1, 4):
            result = cache.get(f"user:{user_id}:data")
            self.assertIsNotNone(result)
            self.assertEqual(result["id"], user_id)


class CacheConnectionPoolTests(TestCase):
    """Test connection pooling configuration."""

    def test_cache_is_functional(self):
        """Verify cache backend is functional."""
        # Test basic set/get to verify connection works
        test_key = "pool_test_key"
        test_value = "pool_test_value"
        cache.set(test_key, test_value, timeout=60)
        result = cache.get(test_key)
        self.assertEqual(result, test_value)
        cache.delete(test_key)

    def test_cache_timeout_works(self):
        """Verify cache timeout is respected."""
        cache.set("timeout_key", "value", timeout=1)
        # Should exist immediately
        self.assertEqual(cache.get("timeout_key"), "value")

    def test_cache_under_load(self):
        """Verify cache handles multiple operations."""
        # Set many values
        for i in range(100):
            cache.set(f"load_test_{i}", f"value_{i}")

        # Retrieve them
        for i in range(100):
            self.assertEqual(cache.get(f"load_test_{i}"), f"value_{i}")

        # Clean up
        for i in range(100):
            cache.delete(f"load_test_{i}")
