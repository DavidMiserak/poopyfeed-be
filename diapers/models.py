from django.db import models

from children.models import Child


class DiaperChange(models.Model):
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

    def __str__(self):
        return f"{self.child.name} - {self.get_change_type_display()}"
