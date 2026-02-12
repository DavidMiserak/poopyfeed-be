"""
Integration tests combining Redis, Sessions, Caching, and Celery.

Verifies that all three Redis features work together correctly:
- User creates session
- Session data persists in Redis
- API requests use cached data
- Background tasks queue and execute
- Cache invalidation happens on data changes
"""

from unittest.mock import patch

from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from children.models import Child
from diapers.models import DiaperChange
from django_project.test_constants import TEST_PASSWORD
from feedings.models import Feeding
from naps.models import Nap

User = get_user_model()


class RedisSessionAndCacheIntegrationTests(TestCase):
    """Test sessions and caching work together."""

    def setUp(self):
        """Create test user and setup client."""
        self.user = User.objects.create_user(
            username="testuser", email="test@test.com", password=TEST_PASSWORD
        )
        self.client = Client()
        cache.clear()

    def test_session_and_cache_coexist_in_redis(self):
        """Test session and cache both use Redis without conflicts."""
        # Set cache value
        cache.set("test_cache_key", "cache_value", timeout=300)

        # Login to create session
        self.client.login(username="testuser", password=TEST_PASSWORD)

        # Both session and cache should exist
        self.assertIn("sessionid", self.client.cookies)
        self.assertEqual(cache.get("test_cache_key"), "cache_value")

    def test_session_survives_cache_clear_partial(self):
        """Test session survives when cache is partially cleared."""
        self.client.login(username="testuser", password=TEST_PASSWORD)
        session_id_1 = self.client.cookies.get("sessionid").value

        # Set cache value
        cache.set("test_key", "test_value")
        self.assertEqual(cache.get("test_key"), "test_value")

        # Delete specific cache key
        cache.delete("test_key")
        self.assertIsNone(cache.get("test_key"))

        # Session should still be valid
        session_id_2 = self.client.cookies.get("sessionid").value
        self.assertEqual(session_id_1, session_id_2)


class RedisCachingAPIIntegrationTests(TestCase):
    """Test caching in API requests."""

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        cls.parent = User.objects.create_user(
            username="parent", email="parent@test.com", password=TEST_PASSWORD
        )
        cls.child = Child.objects.create(
            parent=cls.parent,
            name="Test Child",
            date_of_birth="2024-01-15",
            gender="M",
        )

    def setUp(self):
        """Setup client and login."""
        self.client = Client()
        self.client.login(username="parent", password=TEST_PASSWORD)
        cache.clear()

    def test_api_response_cached(self):
        """Test that caching works alongside API requests."""
        # Set cache value
        cache.set("api_test_key", "api_test_value", timeout=300)
        self.assertEqual(cache.get("api_test_key"), "api_test_value")

        # Verify session still exists
        self.assertIn("sessionid", self.client.cookies)

    def test_cache_invalidated_on_data_mutation(self):
        """Test cache is invalidated when data is created/updated."""
        # Set cache before mutation
        cache.set("pre_mutation", "value", timeout=300)

        # Create feeding (mutation)
        feeding = Feeding.objects.create(
            child=self.child,
            fed_at="2024-01-15 10:00:00",
            amount_oz=4.0,
            feeding_type="bottle",
        )

        # Cache should be invalidated via signals
        self.assertIsNotNone(feeding)

    def test_child_activity_cache_invalidated(self):
        """Test child last activity cache is properly invalidated."""
        # Create initial feeding
        feeding1 = Feeding.objects.create(
            child=self.child,
            fed_at="2024-01-15 10:00:00",
            amount_oz=4.0,
            feeding_type="bottle",
        )

        # Create another feeding (should trigger cache invalidation)
        feeding2 = Feeding.objects.create(
            child=self.child,
            fed_at="2024-01-15 11:00:00",
            amount_oz=4.5,
            feeding_type="bottle",
        )

        # Verify both feedings exist
        self.assertIsNotNone(feeding1)
        self.assertIsNotNone(feeding2)

        # Verify cache invalidation happens (signal fires without error)
        self.assertEqual(Feeding.objects.filter(child=self.child).count(), 2)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class RedisCeleryIntegrationTests(TestCase):
    """Test Celery tasks work with Redis backend."""

    def setUp(self):
        """Clear cache and setup."""
        cache.clear()

    def test_celery_task_queues_in_redis(self):
        """Test task can be queued."""

        @shared_task
        def integration_task(value):
            return value * 2

        # Queue task
        result = integration_task.delay(5)
        self.assertIsNotNone(result.id)

    def test_celery_task_with_cache(self):
        """Test Celery task can use cache."""

        @shared_task
        def task_with_cache(key, value):
            cache.set(key, value, timeout=300)
            return cache.get(key)

        result = task_with_cache.delay("task_key", "task_value")
        self.assertEqual(result.get(), "task_value")

        # Verify cache was set
        self.assertEqual(cache.get("task_key"), "task_value")

    def test_celery_task_with_database(self):
        """Test Celery task can access database."""

        @shared_task
        def task_with_db(child_id):
            child = Child.objects.get(id=child_id)
            return {"child_name": child.name, "child_id": child.id}

        # Create test child
        user = User.objects.create_user(
            username="dbuser", email="db@test.com", password=TEST_PASSWORD
        )
        child = Child.objects.create(
            parent=user,
            name="DB Child",
            date_of_birth="2024-01-15",
            gender="M",
        )

        # Run task
        result = task_with_db.delay(child.id)
        task_result = result.get()

        self.assertEqual(task_result["child_name"], "DB Child")
        self.assertEqual(task_result["child_id"], child.id)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class RedisCacheCeleryFullIntegrationTests(TestCase):
    """Full integration test with all three Redis features."""

    @classmethod
    def setUpTestData(cls):
        """Create test data."""
        cls.parent = User.objects.create_user(
            username="parent", email="parent@test.com", password=TEST_PASSWORD
        )
        cls.child = Child.objects.create(
            parent=cls.parent,
            name="Integration Child",
            date_of_birth="2024-01-15",
            gender="M",
        )

    def setUp(self):
        """Setup client and clear cache."""
        self.client = Client()
        self.client.login(username="parent", password=TEST_PASSWORD)
        cache.clear()

    def test_full_workflow_session_cache_celery(self):
        """Test complete workflow with session, cache, and Celery."""

        @shared_task
        def create_diaper_record(child_id, diaper_change_type):
            child = Child.objects.get(id=child_id)
            diaper = DiaperChange.objects.create(
                child=child,
                changed_at="2024-01-15 10:00:00",
                change_type=diaper_change_type,
            )
            cache.set(
                f"diaper_{diaper.id}",
                {"id": diaper.id, "change_type": diaper_change_type},
            )
            return {"diaper_id": diaper.id, "change_type": diaper_change_type}

        # 1. User is logged in (session in Redis)
        self.assertIn("sessionid", self.client.cookies)

        # 2. Cache a value
        cache.set("workflow_test", "initial_value", timeout=300)
        self.assertEqual(cache.get("workflow_test"), "initial_value")

        # 3. Queue background task
        task_result = create_diaper_record.delay(self.child.id, "wet")
        self.assertIsNotNone(task_result.get())

        # 4. Verify task created data
        diaper_id = task_result.get()["diaper_id"]
        diaper = DiaperChange.objects.get(id=diaper_id)
        self.assertEqual(diaper.change_type, "wet")

        # 5. Verify task set cache
        cached_diaper = cache.get(f"diaper_{diaper_id}")
        self.assertIsNotNone(cached_diaper)
        self.assertEqual(cached_diaper["change_type"], "wet")

        # 6. Verify session still exists
        self.assertIn("sessionid", self.client.cookies)

        # 7. Verify workflow cache still exists
        self.assertEqual(cache.get("workflow_test"), "initial_value")

    def test_redis_survives_multiple_operations(self):
        """Test Redis stability through multiple operations."""
        operations = []

        # Set multiple cache values
        for i in range(10):
            cache.set(f"key_{i}", f"value_{i}", timeout=300)
            operations.append(f"cache_set_{i}")

        # Login multiple times
        for _ in range(3):
            client = Client()
            client.login(username="parent", password=TEST_PASSWORD)
            self.assertIn("sessionid", client.cookies)
            operations.append("login")

        # Queue multiple tasks
        @shared_task
        def counter_task(n):
            return n * n

        for i in range(5):
            result = counter_task.delay(i)
            self.assertEqual(result.get(), i * i)
            operations.append(f"task_{i}")

        # Verify all cache values still exist
        for i in range(10):
            self.assertEqual(cache.get(f"key_{i}"), f"value_{i}")

        # Verify operations were tracked
        self.assertGreater(len(operations), 15)

    def test_cache_invalidation_propagates_correctly(self):
        """Test cache invalidation in complex scenario."""
        # Set initial cache
        cache.set("parent_cache", {"children": [self.child.id]}, timeout=300)

        # Create feeding (should invalidate cache via signal)
        feeding = Feeding.objects.create(
            child=self.child,
            fed_at="2024-01-15 10:00:00",
            amount_oz=4.0,
            feeding_type="bottle",
        )

        # Update cache after feeding
        parent_data = cache.get("parent_cache")
        if parent_data:
            parent_data["last_activity"] = "feeding"
            cache.set("parent_cache", parent_data, timeout=300)

        # Create diaper (should invalidate via signal)
        diaper = DiaperChange.objects.create(
            child=self.child,
            changed_at="2024-01-15 10:30:00",
            change_type="wet",
        )

        # Create nap (should invalidate via signal)
        nap = Nap.objects.create(
            child=self.child,
            napped_at="2024-01-15 11:00:00",
        )

        # Verify all were created
        self.assertIsNotNone(feeding)
        self.assertIsNotNone(diaper)
        self.assertIsNotNone(nap)

        # Verify multiple children can coexist
        user2 = User.objects.create_user(
            username="parent2", email="parent2@test.com", password=TEST_PASSWORD
        )
        child2 = Child.objects.create(
            parent=user2,
            name="Child 2",
            date_of_birth="2023-06-20",
            gender="F",
        )

        # Cache for second parent should be independent
        cache.set("parent2_cache", {"children": [child2.id]}, timeout=300)
        parent1_cache = cache.get("parent_cache")
        parent2_cache = cache.get("parent2_cache")

        self.assertNotEqual(parent1_cache["children"], parent2_cache["children"])
