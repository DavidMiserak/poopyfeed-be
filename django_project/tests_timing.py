"""Tests for the @timing decorator."""

import time

from django.test import TestCase

from .utils.timing import timing

LOG_PERFORMANCE = "poopyfeed.performance"


class TimingDecoratorTests(TestCase):
    """Tests for django_project.utils.timing.timing decorator."""

    def test_fast_function_logs_at_debug(self):
        """Functions completing below threshold log at DEBUG."""

        @timing(threshold_ms=5000)
        def fast_func():
            return 42

        with self.assertLogs(LOG_PERFORMANCE, level="DEBUG") as cm:
            result = fast_func()

        self.assertEqual(result, 42)
        self.assertTrue(any("DEBUG" in m for m in cm.output))
        self.assertFalse(any("WARNING" in m for m in cm.output))

    def test_slow_function_logs_at_warning(self):
        """Functions exceeding threshold log at WARNING."""

        @timing(threshold_ms=1)
        def slow_func():
            time.sleep(0.01)
            return "done"

        with self.assertLogs(LOG_PERFORMANCE, level="DEBUG") as cm:
            result = slow_func()

        self.assertEqual(result, "done")
        self.assertTrue(any("WARNING" in m for m in cm.output))

    def test_custom_label_in_log(self):
        """Custom label appears in log message."""

        @timing(label="PDF export", threshold_ms=5000)
        def export():
            # Empty body to test that decorator logs and does not alter behavior.
            pass

        with self.assertLogs(LOG_PERFORMANCE, level="DEBUG") as cm:
            export()

        self.assertTrue(any("PDF export" in m for m in cm.output))

    def test_default_label_uses_qualname(self):
        """Default label uses function's qualified name."""

        @timing(threshold_ms=5000)
        def my_special_func():
            # Empty body to test default label uses function qualname.
            pass

        with self.assertLogs(LOG_PERFORMANCE, level="DEBUG") as cm:
            my_special_func()

        self.assertTrue(any("my_special_func" in m for m in cm.output))

    def test_custom_threshold_ms(self):
        """Custom threshold_ms controls WARNING vs DEBUG boundary."""

        @timing(threshold_ms=50000)
        def func_with_high_threshold():
            time.sleep(0.005)

        with self.assertLogs(LOG_PERFORMANCE, level="DEBUG") as cm:
            func_with_high_threshold()

        # Should be DEBUG since 5ms << 50000ms threshold
        self.assertTrue(any("DEBUG" in m for m in cm.output))
        self.assertFalse(any("WARNING" in m for m in cm.output))

    def test_return_value_preserved(self):
        """Decorated function's return value is passed through."""

        @timing(threshold_ms=5000)
        def returns_dict():
            return {"key": "value", "count": 3}

        with self.assertLogs(LOG_PERFORMANCE, level="DEBUG"):
            result = returns_dict()

        self.assertEqual(result, {"key": "value", "count": 3})

    def test_exceptions_propagate(self):
        """Exceptions from decorated functions propagate correctly."""

        @timing(threshold_ms=5000)
        def raises_error():
            raise ValueError("test error")

        with self.assertLogs(LOG_PERFORMANCE, level="DEBUG"):
            with self.assertRaises(ValueError, msg="test error"):
                raises_error()

    def test_preserves_function_metadata(self):
        """Decorator preserves function name and docstring."""

        @timing(threshold_ms=5000)
        def documented_func():
            """This is the docstring."""
            pass

        self.assertEqual(documented_func.__name__, "documented_func")
        self.assertEqual(documented_func.__doc__, "This is the docstring.")
