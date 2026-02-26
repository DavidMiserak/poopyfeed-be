from django.db import models
from django.db.models import CheckConstraint, Q

from children.models import Child


class Nap(models.Model):
    """Nap tracking record.

    Records when a child took a nap, with optional end time for duration tracking.
    End time can be set manually or auto-filled when the next activity is recorded.

    Attributes:
        child (ForeignKey): The child who napped
        napped_at (DateTimeField): When the nap started (UTC, indexed for queries)
        ended_at (DateTimeField): When the nap ended (UTC, nullable, indexed)
        created_at (DateTimeField): When record was created
        updated_at (DateTimeField): When record was last modified
    """

    child = models.ForeignKey(
        Child,
        on_delete=models.CASCADE,
        related_name="naps",
    )
    napped_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "children_nap"
        ordering = ["-napped_at"]
        constraints = [
            CheckConstraint(
                condition=Q(ended_at__isnull=True)
                | Q(ended_at__gt=models.F("napped_at")),
                name="nap_ended_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.child.name} - Nap"

    @property
    def duration_minutes(self):
        """Calculate nap duration in minutes, or None if nap hasn't ended."""
        if self.ended_at is None:
            return None
        return (self.ended_at - self.napped_at).total_seconds() / 60

    @property
    def duration_display(self):
        """Human-readable duration (e.g. '1h 30m') or None if nap is ongoing."""
        if self.ended_at is None:
            return None
        total = int(self.duration_minutes)
        h, m = divmod(total, 60)
        return f"{h}h {m}m" if h else f"{m}m"
