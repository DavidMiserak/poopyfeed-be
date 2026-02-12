"""
Custom PostgreSQL database backend with connection pooling.

This module provides a connection-pooled PostgreSQL backend that reuses
database connections efficiently, improving performance under load.

Usage in settings.py:
    DATABASES = {
        "default": {
            "ENGINE": "django_project.db.PostgreSQLPooledBackend",
            ...
        }
    }
"""

import os
from threading import RLock

from django.db.backends.postgresql import base as psycopg2_base

# Try to import psycopg2 pool (available in psycopg2 2.8+)
try:
    from psycopg2 import pool

    HAS_PSYCOPG2_POOL = True
except ImportError:
    HAS_PSYCOPG2_POOL = False


class PostgreSQLPooledBackend(psycopg2_base.DatabaseWrapper):
    """
    PostgreSQL backend with connection pooling.

    Maintains a pool of database connections to reduce connection overhead.
    Connection pools are thread-safe and automatically manage connection lifecycle.
    """

    # Class-level connection pools (shared across instances)
    _pools = {}
    _pools_lock = RLock()

    def _get_pool_key(self):
        """Get a unique key for this database configuration."""
        return (
            self.settings_dict.get("HOST"),
            self.settings_dict.get("PORT"),
            self.settings_dict.get("NAME"),
            self.settings_dict.get("USER"),
        )

    def _create_pool(self):
        """Create a connection pool for this database."""
        if not HAS_PSYCOPG2_POOL:
            return None

        settings = self.settings_dict
        pool_key = self._get_pool_key()

        with self._pools_lock:
            if pool_key in self._pools:
                return self._pools[pool_key]

            # Get pool size from settings or environment
            min_pool_size = int(os.environ.get("DB_POOL_MIN_SIZE", "2"))
            max_pool_size = int(os.environ.get("DB_POOL_MAX_SIZE", "10"))

            # Create connection pool
            try:
                pool_obj = pool.SimpleConnectionPool(
                    min_pool_size,
                    max_pool_size,
                    dsn=self._get_dsn(),
                    connect_timeout=settings.get("OPTIONS", {}).get(
                        "connect_timeout", 10
                    ),
                )
                self._pools[pool_key] = pool_obj
                return pool_obj
            except Exception as e:
                print(f"Failed to create connection pool: {e}")
                return None

    def _get_dsn(self):
        """Get the DSN string for this database."""
        settings = self.settings_dict
        return (
            f"dbname={settings.get('NAME')} "
            f"user={settings.get('USER')} "
            f"password={settings.get('PASSWORD')} "
            f"host={settings.get('HOST')} "
            f"port={settings.get('PORT', 5432)}"
        )

    def get_new_connection(self, conn_params):
        """Get a connection from the pool instead of creating a new one."""
        if not HAS_PSYCOPG2_POOL:
            # Fall back to default behavior if psycopg2 pool is not available
            return super().get_new_connection(conn_params)

        pool_obj = self._create_pool()
        if pool_obj:
            try:
                return pool_obj.getconn()
            except Exception as e:
                print(f"Failed to get connection from pool: {e}")
                return super().get_new_connection(conn_params)
        else:
            return super().get_new_connection(conn_params)

    def close(self):
        """Close the connection and return it to the pool if applicable."""
        if self.connection is None:
            return

        try:
            pool_obj = self._create_pool()
            if pool_obj and HAS_PSYCOPG2_POOL:
                # Return connection to pool instead of closing
                pool_obj.putconn(self.connection)
            else:
                # Fall back to default close behavior
                self.connection.close()
        except Exception:
            # If anything goes wrong, close the connection normally
            if self.connection is not None:
                self.connection.close()
        finally:
            self.connection = None

    @classmethod
    def close_all_pools(cls):
        """Close all connection pools (useful for cleanup/testing)."""
        if not HAS_PSYCOPG2_POOL:
            return

        with cls._pools_lock:
            for pool_obj in cls._pools.values():
                try:
                    pool_obj.closeall()
                except Exception:
                    pass
            cls._pools.clear()
