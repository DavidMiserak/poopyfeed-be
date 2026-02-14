"""
Pytest configuration for Django tests.

Handles Redis configuration and test settings override.
"""

import os

import django
from django.conf import settings
from django.test.utils import get_runner


def pytest_configure():
    """Configure pytest with Django settings."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings")
    django.setup()

    # Ensure we're using Django's test runner
    TestRunner = get_runner(settings)


def pytest_collection_modifyitems(config, items):
    """Mark tests for parallel execution compatibility."""
    # List of test IDs/patterns that conflict in parallel execution
    # These tests have race conditions or shared state issues
    parallel_unsafe_tests = [
        "test_redis_integration",          # All Redis integration tests
        "test_session",                    # Session tests
        "test_cache",                      # Cache tests
        "RevokeAccessViewTests",           # Invite/access tests with state
        "ToggleInviteViewTests",           # Toggle invite tests
    ]

    for item in items:
        # Mark tests that have timing/state conflicts in parallel execution
        test_nodeid = item.nodeid
        if any(unsafe_pattern in test_nodeid for unsafe_pattern in parallel_unsafe_tests):
            item.add_marker("parallel_unsafe")

        # Mark analytics tests as potentially requiring Redis
        if "analytics" in test_nodeid or "cache" in test_nodeid:
            item.add_marker("redis_dependent")
