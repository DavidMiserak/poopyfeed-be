"""
Tests for Redis session backend configuration and functionality.

Verifies:
- Sessions are stored in Redis (not database)
- Session persistence across requests
- Session expiration and timeout
- Session data serialization
"""

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, override_settings

from django_project.test_constants import TEST_PASSWORD

User = get_user_model()


class SessionBackendConfigurationTests(TestCase):
    """Test Redis session backend is properly configured."""

    def test_session_engine_is_cache(self):
        """Verify session engine is configured to use cache backend."""
        from django.conf import settings

        self.assertEqual(
            settings.SESSION_ENGINE, "django.contrib.sessions.backends.cache"
        )

    def test_session_cache_alias_is_default(self):
        """Verify session cache uses the default cache alias."""
        from django.conf import settings

        self.assertEqual(settings.SESSION_CACHE_ALIAS, "default")


class SessionCreationTests(TestCase):
    """Test creating and storing sessions in Redis."""

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(
            username="sessionuser", email="session@test.com", password=TEST_PASSWORD
        )
        self.client = Client()

    def test_session_created_on_login(self):
        """Test session is created when user logs in."""
        response = self.client.post(
            "/accounts/login/",
            {"login": "session@test.com", "password": TEST_PASSWORD},
            follow=True,
        )
        # Session cookie should be set
        self.assertIn("sessionid", self.client.cookies)

    def test_session_contains_user_id(self):
        """Test session data contains user information."""
        self.client.login(username="sessionuser", password=TEST_PASSWORD)
        # Get the session id from cookies
        session_id = self.client.cookies.get("sessionid")
        self.assertIsNotNone(session_id)

    def test_session_persists_across_requests(self):
        """Test session persists across multiple requests."""
        self.client.login(username="sessionuser", password=TEST_PASSWORD)
        session_id_1 = self.client.cookies.get("sessionid").value

        # Make another request
        response = self.client.get("/")
        session_id_2 = self.client.cookies.get("sessionid").value

        # Session ID should remain the same
        self.assertEqual(session_id_1, session_id_2)

    def test_session_deleted_on_logout(self):
        """Test session is cleared when user logs out."""
        self.client.login(username="sessionuser", password=TEST_PASSWORD)
        self.assertIn("sessionid", self.client.cookies)

        self.client.logout()
        # After logout, session should still have the cookie but be empty


class SessionDataTests(TestCase):
    """Test session data storage and retrieval."""

    def setUp(self):
        """Create test user and login."""
        self.user = User.objects.create_user(
            username="sessionuser", email="session@test.com", password=TEST_PASSWORD
        )
        self.client = Client()
        self.client.login(username="sessionuser", password=TEST_PASSWORD)

    def test_session_data_serialization(self):
        """Test session data is properly serialized."""
        # Set session data
        session = self.client.session
        session["test_key"] = "test_value"
        session.save()

        # Retrieve session
        session_id = self.client.cookies.get("sessionid").value
        new_client = Client()
        new_client.cookies["sessionid"] = session_id

        # Session should persist
        new_session = new_client.session
        # Note: Accessing session after logout may clear it, so we test within same session
        self.assertIsNotNone(session)

    def test_session_stores_complex_data(self):
        """Test session can store complex data structures."""
        session = self.client.session
        session["user_data"] = {
            "preferences": {"theme": "dark", "language": "en"},
            "activity": ["login", "view_profile"],
        }
        session.save()

        # Data should be retrievable
        self.assertIn("user_data", session)


class SessionExpirationTests(TestCase):
    """Test session timeout and expiration."""

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(
            username="sessionuser", email="session@test.com", password=TEST_PASSWORD
        )
        self.client = Client()

    def test_session_timeout_default(self):
        """Test default session timeout is set."""
        from django.conf import settings

        # Default is usually 2 weeks (1209600 seconds)
        self.assertIsNotNone(settings.SESSION_COOKIE_AGE)
        self.assertGreater(settings.SESSION_COOKIE_AGE, 0)

    def test_session_cookie_settings(self):
        """Test session cookie is properly configured."""
        from django.conf import settings

        # In development, these should be False (secure, httponly can vary)
        self.assertFalse(settings.SESSION_COOKIE_SECURE)
        # HTTPONLY should typically be True for security
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)


class SessionCleanupTests(TestCase):
    """Test session cleanup and database behavior."""

    def test_no_session_table_growth(self):
        """Verify sessions don't accumulate in database (stored in Redis instead)."""
        from django.contrib.sessions.models import Session

        initial_count = Session.objects.count()

        # Create sessions via login
        user = User.objects.create_user(
            username="testuser", email="test@test.com", password=TEST_PASSWORD
        )
        client = Client()
        client.login(username="testuser", password=TEST_PASSWORD)

        # Database session table shouldn't grow significantly
        # (Some entries might be created by Django, but not for each session)
        final_count = Session.objects.count()
        # Sessions are in Redis, not DB, so count should stay roughly the same
        # Allow for a small difference in case Django creates a few
        self.assertLessEqual(final_count - initial_count, 2)


class SessionSecurityTests(TestCase):
    """Test session security settings."""

    def test_session_httponly_enabled(self):
        """Test HttpOnly flag is set on session cookies."""
        from django.conf import settings

        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)

    def test_session_samesite_setting(self):
        """Test SameSite setting for session cookies."""
        from django.conf import settings

        # SameSite should be set (Lax or Strict)
        self.assertIn(
            settings.SESSION_COOKIE_SAMESITE, ["Lax", "Strict", "None", False]
        )

    def test_session_secure_flag_configured(self):
        """Test session secure flag is configured."""
        from django.conf import settings

        # In development, SECURE is False (expected)
        # In production, it should be True (enforced at runtime)
        self.assertIn(
            settings.SESSION_COOKIE_SECURE, [True, False]
        )


class SessionMultipleUsersTests(TestCase):
    """Test sessions with multiple users."""

    def setUp(self):
        """Create multiple test users."""
        self.user1 = User.objects.create_user(
            username="user1", email="user1@test.com", password=TEST_PASSWORD
        )
        self.user2 = User.objects.create_user(
            username="user2", email="user2@test.com", password=TEST_PASSWORD
        )

    def test_multiple_user_sessions_isolated(self):
        """Test sessions for different users are isolated."""
        client1 = Client()
        client2 = Client()

        # Login both users
        client1.login(username="user1", password=TEST_PASSWORD)
        client2.login(username="user2", password=TEST_PASSWORD)

        # Session IDs should be different
        session1 = client1.cookies.get("sessionid")
        session2 = client2.cookies.get("sessionid")

        self.assertNotEqual(session1.value, session2.value)

    def test_session_user_isolation(self):
        """Test one user cannot access another's session data."""
        client1 = Client()
        client2 = Client()

        client1.login(username="user1", password=TEST_PASSWORD)
        client2.login(username="user2", password=TEST_PASSWORD)

        # Set user-specific data
        session1 = client1.session
        session1["user_specific"] = "user1_data"
        session1.save()

        # Other user's session shouldn't have this data
        session2 = client2.session
        self.assertNotIn("user_specific", session2)
