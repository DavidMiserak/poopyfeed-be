"""Notification models for in-app activity alerts.

Provides persistent notifications when co-parents or caregivers log
tracking activities (feedings, diapers, naps) for shared children.
Includes per-child notification preferences and global quiet hours.
"""

from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """In-app notification for shared activity alerts."""

    class EventType(models.TextChoices):
        FEEDING = "feeding", "Feeding"
        DIAPER = "diaper", "Diaper Change"
        NAP = "nap", "Nap"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )
    child = models.ForeignKey(
        "children.Child",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    event_type = models.CharField(
        max_length=10,
        choices=EventType.choices,
    )
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["recipient", "is_read", "-created_at"],
                name="notif_recipient_unread_idx",
            ),
            models.Index(
                fields=["created_at"],
                name="notif_cleanup_idx",
            ),
        ]

    def __str__(self):
        return f"Notification for {self.recipient.email}: {self.message}"


class NotificationPreference(models.Model):
    """Per-child notification preferences for a user.

    Created automatically when a user first accesses preferences.
    Controls which event types generate notifications for a specific child.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    child = models.ForeignKey(
        "children.Child",
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    notify_feedings = models.BooleanField(default=True)
    notify_diapers = models.BooleanField(default=True)
    notify_naps = models.BooleanField(default=True)

    class Meta:
        unique_together = [["user", "child"]]

    def __str__(self):
        return f"Notification prefs for {self.user.email} on {self.child.name}"


class QuietHours(models.Model):
    """Global quiet hours for a user (single schedule, not per-child).

    During quiet hours, no notifications are created for this user.
    Times are interpreted in the user's timezone (CustomUser.timezone).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiet_hours",
    )
    enabled = models.BooleanField(default=False)
    start_time = models.TimeField(
        default="22:00",
        help_text="Start of quiet period (user local time)",
    )
    end_time = models.TimeField(
        default="07:00",
        help_text="End of quiet period (user local time)",
    )

    class Meta:
        verbose_name_plural = "quiet hours"

    def __str__(self):
        status = "ON" if self.enabled else "OFF"
        return f"Quiet hours for {self.user.email}: {self.start_time}-{self.end_time} ({status})"

    def is_quiet_now(self):
        """Check if current time falls within quiet hours for this user.

        Uses the user's configured timezone from CustomUser.timezone.
        Handles overnight ranges (e.g., 22:00 to 07:00).
        """
        if not self.enabled:
            return False

        user_tz = ZoneInfo(self.user.timezone)
        now_local = timezone.now().astimezone(user_tz).time()

        if self.start_time <= self.end_time:
            # Same-day range (e.g., 09:00 to 17:00)
            return self.start_time <= now_local <= self.end_time
        else:
            # Overnight range (e.g., 22:00 to 07:00)
            return now_local >= self.start_time or now_local <= self.end_time
