"""
Test settings for PoopyFeed backend.

Overrides production settings for test environment:
- Uses in-memory cache for local tests
- Uses Redis cache if available (for GitHub Actions integration tests)
- Enables eager task execution for Celery
- Disables migrations for speed
"""

import os

from django_project.settings import *  # noqa: F401, F403

# Execute Celery tasks synchronously in tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable signal handlers during tests to reduce overhead
# (cache invalidation happens naturally from test cleanup)
ANALYTICS_DISABLE_SIGNALS = True

# Configure cache for tests:
# - If REDIS_HOST is set (GitHub Actions), use Redis with error handling
# - Otherwise, use in-memory cache (local testing)
if os.environ.get("REDIS_HOST"):
    # GitHub Actions or production-like test environment with Redis
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = os.environ.get("REDIS_PORT", "6379")
    redis_url = f"redis://{redis_host}:{redis_port}/0"

    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": redis_url,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "CONNECTION_POOL_KWARGS": {
                    "retry_on_timeout": True,
                    "socket_connect_timeout": 5,
                    "socket_timeout": 5,
                },
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
                "IGNORE_EXCEPTIONS": True,  # Fall back gracefully if Redis unavailable
            },
        }
    }
else:
    # Local testing without Redis
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }

# Configure database for tests:
# - If DATABASE_HOST is set (GitHub Actions/Docker), use PostgreSQL
# - Otherwise, use SQLite in-memory for local testing
if os.environ.get("DATABASE_HOST"):
    # GitHub Actions or Docker environment with PostgreSQL
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DATABASE_NAME", "postgres"),
            "USER": os.environ.get("DATABASE_USER", "postgres"),
            "PASSWORD": os.environ.get("DATABASE_PASSWORD", ""),
            "HOST": os.environ.get("DATABASE_HOST"),
            "PORT": os.environ.get("DATABASE_PORT", "5432"),
        }
    }
else:
    # Local testing with SQLite in-memory
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
