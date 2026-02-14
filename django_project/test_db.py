"""Tests for PostgreSQL connection pooling backend.

Tests the PostgreSQLPooledBackend class for proper pool creation,
connection management, and fallback behavior.
"""

import os
from unittest.mock import MagicMock, patch

from django.test import TestCase


class PostgreSQLPooledBackendPoolKeyTests(TestCase):
    """Test pool key generation for connection pooling."""

    def test_pool_key_includes_all_settings(self):
        """Pool key should include host, port, name, and user."""
        from django_project.db import PostgreSQLPooledBackend

        backend = PostgreSQLPooledBackend("default")
        backend.settings_dict = {
            "HOST": "localhost",
            "PORT": 5432,
            "NAME": "mydb",
            "USER": "postgres",
        }

        key = backend._get_pool_key()

        self.assertEqual(key, ("localhost", 5432, "mydb", "postgres"))

    def test_pool_key_handles_missing_values(self):
        """Pool key should handle missing settings gracefully."""
        from django_project.db import PostgreSQLPooledBackend

        backend = PostgreSQLPooledBackend("default")
        backend.settings_dict = {
            "HOST": "localhost",
            "PORT": None,
            "NAME": "mydb",
            "USER": None,
        }

        key = backend._get_pool_key()

        self.assertEqual(key, ("localhost", None, "mydb", None))

    def test_different_hosts_have_different_keys(self):
        """Different hosts should generate different pool keys."""
        from django_project.db import PostgreSQLPooledBackend

        backend1 = PostgreSQLPooledBackend("default")
        backend1.settings_dict = {
            "HOST": "localhost",
            "PORT": 5432,
            "NAME": "mydb",
            "USER": "postgres",
        }

        backend2 = PostgreSQLPooledBackend("default")
        backend2.settings_dict = {
            "HOST": "remote.server",
            "PORT": 5432,
            "NAME": "mydb",
            "USER": "postgres",
        }

        key1 = backend1._get_pool_key()
        key2 = backend2._get_pool_key()

        self.assertNotEqual(key1, key2)


class PostgreSQLPooledBackendDSNTests(TestCase):
    """Test DSN (Data Source Name) string generation."""

    def test_get_dsn_includes_all_components(self):
        """DSN should include database name, user, password, host, and port."""
        from django_project.db import PostgreSQLPooledBackend

        backend = PostgreSQLPooledBackend("default")
        backend.settings_dict = {
            "NAME": "mydb",
            "USER": "postgres",
            "PASSWORD": "secret",
            "HOST": "localhost",
            "PORT": 5432,
        }

        dsn = backend._get_dsn()

        self.assertIn("dbname=mydb", dsn)
        self.assertIn("user=postgres", dsn)
        self.assertIn("password=secret", dsn)
        self.assertIn("host=localhost", dsn)
        self.assertIn("port=5432", dsn)

    def test_get_dsn_uses_default_port(self):
        """DSN should use default port 5432 if not specified."""
        from django_project.db import PostgreSQLPooledBackend

        backend = PostgreSQLPooledBackend("default")
        backend.settings_dict = {
            "NAME": "mydb",
            "USER": "postgres",
            "PASSWORD": "secret",
            "HOST": "localhost",
        }

        dsn = backend._get_dsn()

        self.assertIn("port=5432", dsn)

    def test_get_dsn_handles_missing_values(self):
        """DSN should handle missing settings gracefully."""
        from django_project.db import PostgreSQLPooledBackend

        backend = PostgreSQLPooledBackend("default")
        backend.settings_dict = {
            "NAME": "mydb",
            "USER": "postgres",
        }

        dsn = backend._get_dsn()

        # Should still be valid DSN format even with missing values
        self.assertIn("dbname=mydb", dsn)
        self.assertIn("user=postgres", dsn)
        self.assertIn("host=None", dsn)


class PostgreSQLPooledBackendPoolCreationTests(TestCase):
    """Test connection pool creation and caching."""

    @patch("django_project.db.HAS_PSYCOPG2_POOL", False)
    def test_create_pool_returns_none_without_psycopg2_pool(self):
        """Pool creation should return None if psycopg2 pool is not available."""
        from django_project.db import PostgreSQLPooledBackend

        backend = PostgreSQLPooledBackend("default")
        backend.settings_dict = {"HOST": "localhost", "NAME": "test"}

        result = backend._create_pool()

        self.assertIsNone(result)

    @patch("django_project.db.HAS_PSYCOPG2_POOL", True)
    @patch("django_project.db.pool.SimpleConnectionPool")
    def test_create_pool_creates_new_pool(self, mock_pool_class):
        """Pool creation should create a new connection pool."""
        from django_project.db import PostgreSQLPooledBackend

        mock_pool_instance = MagicMock()
        mock_pool_class.return_value = mock_pool_instance

        backend = PostgreSQLPooledBackend("default")
        backend.settings_dict = {
            "HOST": "localhost",
            "PORT": 5432,
            "NAME": "test",
            "USER": "postgres",
            "PASSWORD": "pass",
        }
        # Clear pools cache before test
        backend._pools.clear()

        result = backend._create_pool()

        # Should return pool instance
        self.assertIsNotNone(result)

        # Should have called SimpleConnectionPool with correct args
        mock_pool_class.assert_called_once()
        call_args = mock_pool_class.call_args
        self.assertEqual(call_args[0][0], 2)  # min size
        self.assertEqual(call_args[0][1], 10)  # max size

    @patch("django_project.db.HAS_PSYCOPG2_POOL", True)
    @patch("django_project.db.pool.SimpleConnectionPool")
    def test_create_pool_respects_environment_variables(self, mock_pool_class):
        """Pool creation should use DB_POOL_MIN/MAX_SIZE environment variables."""
        from django_project.db import PostgreSQLPooledBackend

        mock_pool_instance = MagicMock()
        mock_pool_class.return_value = mock_pool_instance

        with patch.dict(os.environ, {"DB_POOL_MIN_SIZE": "3", "DB_POOL_MAX_SIZE": "20"}):
            backend = PostgreSQLPooledBackend("default")
            backend.settings_dict = {
                "HOST": "localhost",
                "NAME": "test",
            }

            backend._create_pool()

            call_args = mock_pool_class.call_args
            self.assertEqual(call_args[0][0], 3)  # custom min size
            self.assertEqual(call_args[0][1], 20)  # custom max size

    @patch("django_project.db.HAS_PSYCOPG2_POOL", True)
    @patch("django_project.db.pool.SimpleConnectionPool")
    def test_create_pool_caches_pools(self, mock_pool_class):
        """Pool creation should cache pools by key."""
        from django_project.db import PostgreSQLPooledBackend

        mock_pool_instance = MagicMock()
        mock_pool_class.return_value = mock_pool_instance

        backend = PostgreSQLPooledBackend("default")
        backend.settings_dict = {
            "HOST": "localhost",
            "PORT": 5432,
            "NAME": "test",
            "USER": "postgres",
            "PASSWORD": "pass",
        }

        # Call twice with same settings
        result1 = backend._create_pool()
        result2 = backend._create_pool()

        # Should return same instance (from cache)
        self.assertEqual(result1, result2)

        # Should only create pool once
        self.assertEqual(mock_pool_class.call_count, 1)

    @patch("django_project.db.HAS_PSYCOPG2_POOL", True)
    @patch("django_project.db.pool.SimpleConnectionPool")
    def test_create_pool_handles_creation_error(self, mock_pool_class):
        """Pool creation should handle errors gracefully."""
        from django_project.db import PostgreSQLPooledBackend

        # Pool creation raises error
        mock_pool_class.side_effect = Exception("Connection failed")

        backend = PostgreSQLPooledBackend("default")
        backend.settings_dict = {
            "HOST": "localhost",
            "NAME": "test",
        }

        # Should return None on error
        result = backend._create_pool()

        self.assertIsNone(result)


class PostgreSQLPooledBackendConnectionTests(TestCase):
    """Test connection management."""

    @patch("django_project.db.HAS_PSYCOPG2_POOL", False)
    def test_get_new_connection_fallback_without_pool(self):
        """Should fallback to default when psycopg2 pool unavailable."""
        from django_project.db import PostgreSQLPooledBackend

        backend = PostgreSQLPooledBackend("default")
        backend.settings_dict = {"HOST": "localhost"}

        with patch.object(
            PostgreSQLPooledBackend, "get_new_connection", wraps=backend.get_new_connection
        ) as mock_method:
            # When HAS_PSYCOPG2_POOL is False, should call super()
            with patch("django_project.db.psycopg2_base.DatabaseWrapper.get_new_connection"):
                backend.get_new_connection({})

    @patch("django_project.db.HAS_PSYCOPG2_POOL", True)
    @patch("django_project.db.pool.SimpleConnectionPool")
    def test_get_new_connection_from_pool(self, mock_pool_class):
        """Should get connection from pool when available."""
        from django_project.db import PostgreSQLPooledBackend

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_pool_class.return_value = mock_pool

        backend = PostgreSQLPooledBackend("default")
        backend.settings_dict = {
            "HOST": "localhost",
            "NAME": "test",
            "USER": "postgres",
            "PASSWORD": "pass",
        }
        # Clear pools cache before test
        backend._pools.clear()

        conn = backend.get_new_connection({})

        # Should have gotten connection from pool
        self.assertIsNotNone(conn)
        mock_pool.getconn.assert_called()

    @patch("django_project.db.HAS_PSYCOPG2_POOL", True)
    @patch("django_project.db.pool.SimpleConnectionPool")
    def test_get_new_connection_fallback_on_pool_error(self, mock_pool_class):
        """Should fallback to default if pool getconn fails."""
        from django_project.db import PostgreSQLPooledBackend

        mock_pool = MagicMock()
        mock_pool.getconn.side_effect = Exception("Pool error")
        mock_pool_class.return_value = mock_pool

        with patch("django_project.db.psycopg2_base.DatabaseWrapper.get_new_connection"):
            backend = PostgreSQLPooledBackend("default")
            backend.settings_dict = {
                "HOST": "localhost",
                "NAME": "test",
                "USER": "postgres",
            }

            # Should catch error and fallback
            backend.get_new_connection({})


class PostgreSQLPooledBackendCloseTests(TestCase):
    """Test connection closing and pool cleanup."""

    @patch("django_project.db.HAS_PSYCOPG2_POOL", True)
    @patch("django_project.db.pool.SimpleConnectionPool")
    def test_close_returns_connection_to_pool(self, mock_pool_class):
        """Closing should return connection to pool."""
        from django_project.db import PostgreSQLPooledBackend

        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool
        mock_conn = MagicMock()

        backend = PostgreSQLPooledBackend("default")
        backend.settings_dict = {
            "HOST": "localhost",
            "NAME": "test",
            "USER": "postgres",
            "PASSWORD": "pass",
        }
        # Clear pools cache and set up pool
        backend._pools.clear()
        backend._create_pool()  # Populate cache with mock pool
        backend.connection = mock_conn

        backend.close()

        # Connection should be set to None
        self.assertIsNone(backend.connection)

    @patch("django_project.db.HAS_PSYCOPG2_POOL", False)
    def test_close_without_pool_closes_connection(self):
        """Without pool, close should close connection directly."""
        from django_project.db import PostgreSQLPooledBackend

        backend = PostgreSQLPooledBackend("default")
        backend.settings_dict = {"HOST": "localhost"}

        mock_conn = MagicMock()
        backend.connection = mock_conn

        backend.close()

        # Should close connection
        mock_conn.close.assert_called_once()
        self.assertIsNone(backend.connection)

    def test_close_handles_none_connection(self):
        """Close should handle None connection gracefully."""
        from django_project.db import PostgreSQLPooledBackend

        backend = PostgreSQLPooledBackend("default")
        backend.connection = None

        # Should not raise error
        backend.close()

    @patch("django_project.db.HAS_PSYCOPG2_POOL", True)
    @patch("django_project.db.pool.SimpleConnectionPool")
    def test_close_handles_putconn_error(self, mock_pool_class):
        """Close should handle errors when returning to pool."""
        from django_project.db import PostgreSQLPooledBackend

        mock_pool = MagicMock()
        mock_pool.putconn.side_effect = Exception("Pool error")
        mock_pool_class.return_value = mock_pool

        backend = PostgreSQLPooledBackend("default")
        backend.settings_dict = {
            "HOST": "localhost",
            "NAME": "test",
            "USER": "postgres",
            "PASSWORD": "pass",
        }
        mock_conn = MagicMock()
        backend.connection = mock_conn

        # Should handle error and close connection
        backend.close()

        # Should try to close connection as fallback
        mock_conn.close.assert_called_once()
        self.assertIsNone(backend.connection)

    def test_close_all_pools_closes_all(self):
        """close_all_pools should close all cached pools."""
        from django_project.db import PostgreSQLPooledBackend

        # Simulate cached pools
        mock_pool1 = MagicMock()
        mock_pool2 = MagicMock()
        PostgreSQLPooledBackend._pools = {
            ("localhost", 5432, "db1", "user"): mock_pool1,
            ("remote", 5432, "db2", "user"): mock_pool2,
        }

        PostgreSQLPooledBackend.close_all_pools()

        # Both pools should be closed
        mock_pool1.closeall.assert_called_once()
        mock_pool2.closeall.assert_called_once()
        # Cache should be cleared
        self.assertEqual(len(PostgreSQLPooledBackend._pools), 0)

    @patch("django_project.db.HAS_PSYCOPG2_POOL", False)
    def test_close_all_pools_without_psycopg2(self):
        """close_all_pools should handle missing psycopg2 gracefully."""
        from django_project.db import PostgreSQLPooledBackend

        # Should not raise error
        PostgreSQLPooledBackend.close_all_pools()
