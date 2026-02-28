from zoneinfo import available_timezones

from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    timezone = models.CharField(
        max_length=63,
        default="UTC",
        help_text="IANA timezone identifier (e.g. America/New_York). "
        "No DB index by design; add one if timezone-based queries are introduced.",
    )

    @staticmethod
    def valid_timezones():
        return sorted(available_timezones())
