from django.db import models

from children.models import Child


class DiaperChange(models.Model):
    """Diaper change tracking record.

    Records when a diaper was changed and what type of change occurred.
    Supports three change types: wet, dirty, or both.

    Attributes:
        child (ForeignKey): The child whose diaper was changed
        change_type (CharField): One of 'wet', 'dirty', or 'both'
        changed_at (DateTimeField): When the diaper change occurred (UTC, indexed for queries)
        created_at (DateTimeField): When record was created
        updated_at (DateTimeField): When record was last modified
    """

    class ChangeType(models.TextChoices):
        WET = "wet", "Wet"
        DIRTY = "dirty", "Dirty"
        BOTH = "both", "Wet + Dirty"

    child = models.ForeignKey(
        Child,
        on_delete=models.CASCADE,
        related_name="diaper_changes",
    )
    change_type = models.CharField(max_length=10, choices=ChangeType.choices)
    changed_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "children_diaperchange"
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["child", "changed_at"]),
        ]

    def __str__(self):
        return f"{self.child.name} - {self.get_change_type_display()}"
