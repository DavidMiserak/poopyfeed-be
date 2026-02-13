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
    """Mark tests that require Redis."""
    for item in items:
        # Mark analytics tests as potentially requiring Redis
        if "analytics" in item.nodeid or "cache" in item.nodeid:
            item.add_marker("redis_dependent")
