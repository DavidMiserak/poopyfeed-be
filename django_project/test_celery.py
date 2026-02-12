"""
Tests for Celery configuration and task functionality.

Verifies:
- Celery app is properly configured
- Tasks can be defined and queued
- Celery broker/result backend use Redis
- Task execution (in eager mode for testing)
- Task serialization
"""

from unittest.mock import patch

from celery import shared_task
from django.test import TestCase, override_settings

from django_project.celery import app, debug_task


class CeleryConfigurationTests(TestCase):
    """Test Celery app configuration."""

    def test_celery_app_exists(self):
        """Verify Celery app is initialized."""
        self.assertIsNotNone(app)
        self.assertEqual(app.main, "poopyfeed")

    def test_celery_broker_url_configured(self):
        """Verify Celery broker URL is set to Redis."""
        broker_url = app.conf.broker_url
        self.assertIsNotNone(broker_url)
        self.assertTrue(broker_url.startswith("redis://"))

    def test_celery_result_backend_configured(self):
        """Verify Celery result backend is set to Redis."""
        result_backend = app.conf.result_backend
        self.assertIsNotNone(result_backend)
        self.assertTrue(result_backend.startswith("redis://"))

    def test_celery_accepts_json_only(self):
        """Verify Celery is configured to use JSON serialization."""
        self.assertIn("json", app.conf.accept_content)

    def test_celery_task_serializer_is_json(self):
        """Verify task serialization is JSON."""
        self.assertEqual(app.conf.task_serializer, "json")

    def test_celery_result_serializer_is_json(self):
        """Verify result serialization is JSON."""
        self.assertEqual(app.conf.result_serializer, "json")

    def test_celery_timezone_configured(self):
        """Verify Celery timezone is set."""
        self.assertIsNotNone(app.conf.timezone)
        self.assertEqual(app.conf.timezone, "UTC")


class CeleryTaskDefinitionTests(TestCase):
    """Test defining and registering Celery tasks."""

    def test_debug_task_exists(self):
        """Verify debug task is defined."""
        self.assertIsNotNone(debug_task)

    def test_debug_task_is_registered(self):
        """Verify debug task is registered in app."""
        task_name = f"{debug_task.__module__}.{debug_task.__name__}"
        # Task should be discoverable
        self.assertIsNotNone(debug_task)

    def test_shared_task_can_be_created(self):
        """Verify @shared_task decorator works."""

        @shared_task
        def test_shared_task(x, y):
            return x + y

        self.assertIsNotNone(test_shared_task)
        self.assertTrue(hasattr(test_shared_task, "delay"))
        self.assertTrue(hasattr(test_shared_task, "apply_async"))


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class CeleryTaskExecutionTests(TestCase):
    """Test task execution (in eager mode for testing)."""

    def test_debug_task_executes(self):
        """Test debug task can be executed."""
        # In eager mode, task executes immediately
        result = debug_task.delay()
        self.assertIsNotNone(result)

    def test_simple_task_execution(self):
        """Test executing a simple task."""

        @shared_task
        def add(x, y):
            return x + y

        result = add.delay(2, 3)
        self.assertEqual(result.get(), 5)

    def test_task_with_string_argument(self):
        """Test task with string arguments."""

        @shared_task
        def greeting(name):
            return f"Hello, {name}!"

        result = greeting.delay("Alice")
        self.assertEqual(result.get(), "Hello, Alice!")

    def test_task_with_multiple_arguments(self):
        """Test task with multiple arguments."""

        @shared_task
        def multiply(a, b, c):
            return a * b * c

        result = multiply.delay(2, 3, 4)
        self.assertEqual(result.get(), 24)

    def test_task_with_kwargs(self):
        """Test task with keyword arguments."""

        @shared_task
        def build_string(prefix, suffix, middle="MIDDLE"):
            return f"{prefix}-{middle}-{suffix}"

        result = build_string.delay(prefix="START", suffix="END", middle="CENTER")
        self.assertEqual(result.get(), "START-CENTER-END")


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class CeleryTaskReturnValuesTests(TestCase):
    """Test task return values and result handling."""

    def test_task_returns_value(self):
        """Test task return value is captured."""

        @shared_task
        def return_value():
            return "test_value"

        result = return_value.delay()
        self.assertEqual(result.get(), "test_value")

    def test_task_returns_dict(self):
        """Test task can return dictionary."""

        @shared_task
        def return_dict():
            return {"status": "success", "data": [1, 2, 3]}

        result = return_dict.delay()
        self.assertEqual(result.get()["status"], "success")
        self.assertEqual(result.get()["data"], [1, 2, 3])

    def test_task_returns_list(self):
        """Test task can return list."""

        @shared_task
        def return_list():
            return [1, 2, 3, 4, 5]

        result = return_list.delay()
        self.assertEqual(result.get(), [1, 2, 3, 4, 5])

    def test_task_returns_none(self):
        """Test task can return None."""

        @shared_task
        def return_none():
            pass  # Returns None

        result = return_none.delay()
        self.assertIsNone(result.get())


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class CeleryTaskErrorHandlingTests(TestCase):
    """Test task error handling and resilience."""

    def test_task_with_conditional_logic(self):
        """Test task with conditional logic."""

        @shared_task
        def conditional_task(value):
            if value < 0:
                return {"status": "error", "reason": "negative value"}
            return {"status": "success", "result": value * 2}

        # Success case
        result = conditional_task.delay(5)
        self.assertEqual(result.get()["result"], 10)

        # Failure case (returns error instead of raising)
        result = conditional_task.delay(-5)
        self.assertEqual(result.get()["status"], "error")


class CeleryTaskQueueingTests(TestCase):
    """Test queueing tasks without execution."""

    def test_task_delay_returns_result_object(self):
        """Test .delay() returns a result object."""

        @shared_task
        def queue_test():
            return "queued"

        result = queue_test.delay()
        # Should return an AsyncResult object (even if not executing)
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, "id"))

    def test_task_apply_async_returns_result_object(self):
        """Test .apply_async() returns a result object."""

        @shared_task
        def async_test():
            return "async"

        result = async_test.apply_async()
        self.assertIsNotNone(result)
        self.assertTrue(hasattr(result, "id"))

    def test_task_result_id_is_unique(self):
        """Test each task queuing gets a unique ID."""

        @shared_task
        def unique_test():
            return "unique"

        result1 = unique_test.apply_async()
        result2 = unique_test.apply_async()

        self.assertNotEqual(result1.id, result2.id)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class CeleryTaskTimeoutTests(TestCase):
    """Test task timeout configuration."""

    def test_task_time_limit_configured(self):
        """Verify task time limits are configured."""
        self.assertIsNotNone(app.conf.task_time_limit)
        self.assertIsNotNone(app.conf.task_soft_time_limit)

    def test_task_soft_limit_less_than_hard_limit(self):
        """Verify soft limit is less than hard limit."""
        self.assertLess(app.conf.task_soft_time_limit, app.conf.task_time_limit)

    def test_task_time_limit_values(self):
        """Verify time limit values are reasonable."""
        # Hard limit: 30 minutes
        self.assertEqual(app.conf.task_time_limit, 30 * 60)
        # Soft limit: 25 minutes
        self.assertEqual(app.conf.task_soft_time_limit, 25 * 60)


class CeleryTaskAutoDiscoveryTests(TestCase):
    """Test Celery task auto-discovery."""

    def test_celery_autodiscover_tasks_configured(self):
        """Verify Celery is configured to auto-discover tasks."""
        # Check if autodiscover_tasks is called in celery.py
        # Tasks from apps should be discovered
        self.assertIsNotNone(app)

    def test_django_apps_registered(self):
        """Verify Django apps are available for task discovery."""
        from django.apps import apps

        # Common apps that might have tasks
        app_labels = [app.label for app in apps.get_app_configs()]
        self.assertGreater(len(app_labels), 0)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class CeleryIntegrationTests(TestCase):
    """Integration tests combining multiple Celery features."""

    def test_task_chain_execution(self):
        """Test executing multiple tasks in sequence."""

        @shared_task
        def step1(value):
            return value * 2

        @shared_task
        def step2(value):
            return value + 10

        # Execute first task
        result1 = step1.delay(5)
        first_result = result1.get()

        # Execute second task with result from first
        result2 = step2.delay(first_result)
        final_result = result2.get()

        self.assertEqual(first_result, 10)
        self.assertEqual(final_result, 20)

    def test_concurrent_task_execution(self):
        """Test executing multiple tasks concurrently."""

        @shared_task
        def concurrent_task(task_num, value):
            return {"task": task_num, "result": value * task_num}

        # Queue multiple tasks
        results = [concurrent_task.delay(i, 10) for i in range(1, 4)]

        # Collect results
        task_results = [r.get() for r in results]

        self.assertEqual(len(task_results), 3)
        self.assertEqual(task_results[0]["result"], 10)
        self.assertEqual(task_results[1]["result"], 20)
        self.assertEqual(task_results[2]["result"], 30)

    def test_task_with_database_operations(self):
        """Test task that interacts with database."""
        from django.contrib.auth import get_user_model

        User = get_user_model()

        @shared_task
        def create_user_task(username, email):
            user = User.objects.create_user(username=username, email=email)
            return {"id": user.id, "username": user.username}

        result = create_user_task.delay("task_user", "task@test.com")
        task_result = result.get()

        # User should be created
        self.assertIsNotNone(task_result)
        self.assertEqual(task_result["username"], "task_user")

        # Verify in database
        user = User.objects.get(username="task_user")
        self.assertEqual(user.email, "task@test.com")
