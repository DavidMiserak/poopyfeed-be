"""Performance timing decorator for profiling functions.

Usage::

    from django_project.utils.timing import timing

    @timing()
    def my_function():
        ...

    @timing(label="PDF export", threshold_ms=500)
    def generate_pdf():
        ...
"""

import functools
import logging
import time

logger = logging.getLogger("poopyfeed.performance")


def timing(label: str | None = None, threshold_ms: float = 200):
    """Decorator that logs function execution time.

    Args:
        label: Human-readable name for logs. Defaults to the function name.
        threshold_ms: Log at WARNING when execution time >= this value (ms).
            Otherwise logs at DEBUG.
    """

    def decorator(func):
        func_label = label or func.__qualname__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed_ms = (time.monotonic() - start) * 1000
                if elapsed_ms >= threshold_ms:
                    logger.warning(
                        "%s took %.1fms (threshold: %.0fms)",
                        func_label,
                        elapsed_ms,
                        threshold_ms,
                    )
                else:
                    logger.debug(
                        "%s took %.1fms",
                        func_label,
                        elapsed_ms,
                    )

        return wrapper

    return decorator
