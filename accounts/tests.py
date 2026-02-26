from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.forms import DeleteAccountForm, ProfileForm
from django_project.test_constants import TEST_PASSWORD


class CustomUserTests(TestCase):
    def test_create_user(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="will", email="will@email.com", password=TEST_PASSWORD
        )
        self.assertEqual(user.username, "will")
        self.assertEqual(user.email, "will@email.com")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        user_model = get_user_model()
        admin_user = user_model.objects.create_superuser(
            username="superadmin", email="superadmin@email.com", password=TEST_PASSWORD
        )
        self.assertEqual(admin_user.username, "superadmin")
        self.assertEqual(admin_user.email, "superadmin@email.com")
        self.assertTrue(admin_user.is_active)
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)

    def test_timezone_default(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="tzuser", email="tz@email.com", password=TEST_PASSWORD
        )
        self.assertEqual(user.timezone, "UTC")

    def test_timezone_custom(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="tzuser2",
            email="tz2@email.com",
            password=TEST_PASSWORD,
            timezone="America/New_York",
        )
        self.assertEqual(user.timezone, "America/New_York")

    def test_valid_timezones_returns_sorted_list(self):
        """valid_timezones() should return sorted list of IANA timezone strings."""
        user_model = get_user_model()
        timezones = user_model.valid_timezones()

        # Should be a list
        self.assertIsInstance(timezones, list)

        # Should contain many timezones
        self.assertGreater(len(timezones), 100)

        # Should contain common timezones
        self.assertIn("UTC", timezones)
        self.assertIn("America/New_York", timezones)
        self.assertIn("Europe/London", timezones)
        self.assertIn("Asia/Tokyo", timezones)

        # Should be sorted
        self.assertEqual(timezones, sorted(timezones))


class SignUpPageTests(TestCase):
    def setUp(self):
        url = reverse("account_signup")
        self.response = self.client.get(url)

    def test_signup_template(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertTemplateUsed(self.response, "account/signup.html")
        self.assertContains(self.response, "Sign Up")

    def test_signup_form(self):
        user_model = get_user_model()
        self.client.post(
            reverse("account_signup"),
            {
                "email": "testuser@email.com",
                "password1": TEST_PASSWORD,
                "password2": TEST_PASSWORD,
            },
        )
        self.assertEqual(user_model.objects.count(), 1)
        self.assertEqual(user_model.objects.first().email, "testuser@email.com")


class ProfileFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="profileuser",
            email="profile@example.com",
            password=TEST_PASSWORD,
            first_name="John",
            last_name="Doe",
        )
        cls.other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password=TEST_PASSWORD,
        )

    def test_profile_form_valid(self):
        """Test ProfileForm with valid data."""
        form = ProfileForm(
            data={
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane@example.com",
                "timezone": "America/New_York",
            },
            instance=self.user,
        )
        self.assertTrue(form.is_valid())

    def test_profile_form_updates_user(self):
        """Test ProfileForm saves user changes."""
        form = ProfileForm(
            data={
                "first_name": "Updated",
                "last_name": "Name",
                "email": "updated@example.com",
                "timezone": "Europe/London",
            },
            instance=self.user,
        )
        self.assertTrue(form.is_valid())
        form.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(self.user.last_name, "Name")
        self.assertEqual(self.user.email, "updated@example.com")
        self.assertEqual(self.user.timezone, "Europe/London")

    def test_profile_form_email_duplicate_rejection(self):
        """Test ProfileForm rejects duplicate email."""
        form = ProfileForm(
            data={
                "first_name": "John",
                "last_name": "Doe",
                "email": "other@example.com",  # Already used by other_user
                "timezone": "UTC",
            },
            instance=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
        self.assertIn("already exists", str(form.errors["email"][0]))

    def test_profile_form_allows_same_email(self):
        """Test ProfileForm allows user to keep their current email."""
        form = ProfileForm(
            data={
                "first_name": "John",
                "last_name": "Doe",
                "email": "profile@example.com",  # Same as self.user
                "timezone": "UTC",
            },
            instance=self.user,
        )
        self.assertTrue(form.is_valid())

    def test_profile_form_timezone_field_populated(self):
        """Test ProfileForm timezone field contains valid timezones."""
        form = ProfileForm(instance=self.user)
        timezone_choices = form.fields["timezone"].widget.choices
        # Check that timezone choices are populated
        self.assertGreater(len(timezone_choices), 0)
        # Check that UTC is in choices
        tz_values = [choice[0] for choice in timezone_choices]
        self.assertIn("UTC", tz_values)
        self.assertIn("America/New_York", tz_values)

    def test_profile_form_has_crispy_helper(self):
        """Test ProfileForm has crispy FormHelper with row layout."""
        form = ProfileForm(instance=self.user)
        self.assertIsNotNone(form.helper)
        self.assertFalse(form.helper.form_tag)

    def test_profile_form_empty_names_allowed(self):
        """Test ProfileForm allows empty first_name and last_name."""
        form = ProfileForm(
            data={
                "first_name": "",
                "last_name": "",
                "email": "test@example.com",
                "timezone": "UTC",
            },
            instance=self.user,
        )
        self.assertTrue(form.is_valid())


class DeleteAccountFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="deleteuser",
            email="delete@example.com",
            password=TEST_PASSWORD,
        )

    def test_delete_account_form_valid_password(self):
        """Test DeleteAccountForm with correct password."""
        form = DeleteAccountForm(
            data={"current_password": TEST_PASSWORD},
            user=self.user,
        )
        self.assertTrue(form.is_valid())

    def test_delete_account_form_invalid_password(self):
        """Test DeleteAccountForm rejects incorrect password."""
        form = DeleteAccountForm(
            data={"current_password": "wrongpassword"},
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("current_password", form.errors)
        self.assertIn("incorrect", str(form.errors["current_password"][0]))

    def test_delete_account_form_empty_password(self):
        """Test DeleteAccountForm requires password."""
        form = DeleteAccountForm(
            data={"current_password": ""},
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("current_password", form.errors)

    def test_delete_account_form_no_user_skips_validation(self):
        """Test DeleteAccountForm skips validation when user is None."""
        form = DeleteAccountForm(
            data={"current_password": "anypassword"},
            user=None,
        )
        # Form is valid because check is skipped when user is None
        self.assertTrue(form.is_valid())

    def test_delete_account_form_widget_is_password_input(self):
        """Test DeleteAccountForm uses PasswordInput widget."""
        form = DeleteAccountForm(user=self.user)
        password_field = form.fields["current_password"]
        self.assertEqual(password_field.widget.__class__.__name__, "PasswordInput")


class AccountSettingsViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="settings_user",
            email="settings@example.com",
            password=TEST_PASSWORD,
            first_name="Settings",
            last_name="User",
        )

    def setUp(self):
        self.client.login(username="settings_user", password=TEST_PASSWORD)

    def test_account_settings_get_requires_login(self):
        """Test AccountSettingsView requires authentication."""
        self.client.logout()
        response = self.client.get(reverse("account_settings"))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_account_settings_get_displays_forms(self):
        """Test AccountSettingsView GET displays forms."""
        response = self.client.get(reverse("account_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account/settings.html")
        self.assertIn("profile_form", response.context)
        self.assertIn("delete_form", response.context)
        self.assertFalse(response.context["profile_success"])

    def test_account_settings_context_has_profile_form(self):
        """Test AccountSettingsView provides ProfileForm in context."""
        response = self.client.get(reverse("account_settings"))
        profile_form = response.context["profile_form"]
        self.assertEqual(profile_form.instance, self.user)

    def test_account_settings_context_has_delete_form(self):
        """Test AccountSettingsView provides DeleteAccountForm in context."""
        response = self.client.get(reverse("account_settings"))
        delete_form = response.context["delete_form"]
        self.assertIsNotNone(delete_form)

    def test_account_settings_context_has_quiet_hours_form(self):
        """Test AccountSettingsView provides quiet hours form in context."""
        response = self.client.get(reverse("account_settings"))
        self.assertIn("quiet_hours_form", response.context)

    def test_account_settings_post_quiet_hours_valid(self):
        """Test AccountSettingsView saves quiet hours and redirects with success."""
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "quiet_hours",
                "enabled": "on",
                "start_time": "22:00",
                "end_time": "07:00",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("notifications_saved=1", response.url)
        from notifications.models import QuietHours

        qh = QuietHours.objects.get(user=self.user)
        self.assertTrue(qh.enabled)
        self.assertEqual(str(qh.start_time), "22:00:00")
        self.assertEqual(str(qh.end_time), "07:00:00")

    def test_account_settings_profile_success_flag_from_query(self):
        """Test AccountSettingsView shows success message from query param."""
        response = self.client.get(reverse("account_settings") + "?profile_saved=1")
        self.assertTrue(response.context["profile_success"])

    def test_account_settings_profile_success_flag_false_by_default(self):
        """Test AccountSettingsView hides success message by default."""
        response = self.client.get(reverse("account_settings"))
        self.assertFalse(response.context["profile_success"])

    def test_account_settings_post_profile_valid(self):
        """Test AccountSettingsView updates profile with valid data."""
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "profile",
                "first_name": "Updated",
                "last_name": "Name",
                "email": "updated@example.com",
                "timezone": "Europe/London",
            },
        )
        # Should redirect with success query param
        self.assertEqual(response.status_code, 302)
        self.assertIn("profile_saved=1", response.url)
        # Verify user was updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(self.user.email, "updated@example.com")

    def test_account_settings_post_profile_invalid_email(self):
        """Test AccountSettingsView rejects invalid profile data."""
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "profile",
                "first_name": "Updated",
                "last_name": "Name",
                "email": "invalid",  # Invalid email
                "timezone": "UTC",
            },
        )
        # Should re-render form with errors
        self.assertEqual(response.status_code, 200)
        profile_form = response.context["profile_form"]
        self.assertFalse(profile_form.is_valid())
        self.assertIn("email", profile_form.errors)

    def test_account_settings_post_profile_duplicate_email(self):
        """Test AccountSettingsView prevents duplicate email."""
        User = get_user_model()
        User.objects.create_user(
            username="other",
            email="taken@example.com",
            password=TEST_PASSWORD,
        )
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "profile",
                "first_name": "Updated",
                "last_name": "Name",
                "email": "taken@example.com",
                "timezone": "UTC",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("profile_form", response.context)

    def test_account_settings_post_delete_valid_password(self):
        """Test AccountSettingsView deletes account with valid password."""
        user_pk = self.user.pk
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "delete",
                "current_password": TEST_PASSWORD,
            },
        )
        # Should redirect home
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))
        # User should be deleted
        self.assertFalse(get_user_model().objects.filter(pk=user_pk).exists())

    def test_account_settings_post_delete_invalid_password(self):
        """Test AccountSettingsView rejects delete with wrong password."""
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "delete",
                "current_password": "wrongpassword",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("delete_form", response.context)
        # User should still exist
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_account_settings_post_unknown_action(self):
        """Test AccountSettingsView redirects for unknown action."""
        response = self.client.post(
            reverse("account_settings"),
            {"action": "unknown"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("account_settings"))

    def test_account_settings_post_no_action(self):
        """Test AccountSettingsView redirects when no action specified."""
        response = self.client.post(reverse("account_settings"), {})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("account_settings"))

    def test_account_settings_delete_form_preserved_on_profile_error(self):
        """Test AccountSettingsView preserves delete form on profile error."""
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "profile",
                "first_name": "Updated",
                "last_name": "Name",
                "email": "invalid",
                "timezone": "UTC",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("delete_form", response.context)

    def test_account_settings_profile_form_preserved_on_delete_error(self):
        """Test AccountSettingsView preserves profile form on delete error."""
        response = self.client.post(
            reverse("account_settings"),
            {
                "action": "delete",
                "current_password": "wrongpassword",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("profile_form", response.context)


class TimezoneUpdateViewTests(TestCase):
    """Tests for the timezone-only update endpoint used by the timezone banner."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="tzupdate",
            email="tzupdate@example.com",
            password=TEST_PASSWORD,
            timezone="UTC",
        )

    def test_post_requires_login(self):
        """Unauthenticated POST redirects to login."""
        response = self.client.post(
            reverse("account_settings_timezone"),
            {"timezone": "America/New_York"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.timezone, "UTC")

    def test_post_valid_timezone_updates_user(self):
        """POST with valid timezone updates user and redirects to settings."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("account_settings_timezone"),
            {"timezone": "America/New_York"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("account_settings") + "?profile_saved=1")
        self.user.refresh_from_db()
        self.assertEqual(self.user.timezone, "America/New_York")

    def test_post_invalid_timezone_redirects_without_updating(self):
        """POST with invalid timezone does not update user."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("account_settings_timezone"),
            {"timezone": "Invalid/Zone"},
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.timezone, "UTC")

    def test_post_empty_timezone_redirects_without_updating(self):
        """POST with empty timezone does not update user."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("account_settings_timezone"),
            {"timezone": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.timezone, "UTC")


class TimezoneBannerTemplateTests(TestCase):
    """Tests that the timezone banner is present in base template for authenticated users."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="tzbanner",
            email="tzbanner@example.com",
            password=TEST_PASSWORD,
            timezone="Europe/London",
        )

    def test_base_template_includes_tz_banner_when_authenticated(self):
        """Authenticated users get the timezone banner in the base template."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("account_settings"))
        content = response.content.decode()
        self.assertIn('id="tz-banner"', content)
        self.assertIn("Europe/London", content)
        self.assertIn("data-profile-timezone=", content)
        self.assertIn("tz-banner-dismiss-btn", content)
        self.assertIn("/accounts/settings/timezone/", content)

    def test_base_template_no_tz_banner_when_anonymous(self):
        """Anonymous users do not get the timezone banner markup."""
        response = self.client.get(reverse("account_login"))
        self.assertNotContains(response, 'id="tz-banner"')
