from django.db import models

from children.models import Child


class Nap(models.Model):
    """Nap tracking record.

    Records when a child took a nap. Stores only the start time of the nap;
    duration can be calculated by comparing with next activity or using explicit
    nap end times if needed in future versions.

    Attributes:
        child (ForeignKey): The child who napped
        napped_at (DateTimeField): When the nap started (UTC, indexed for queries)
        created_at (DateTimeField): When record was created
        updated_at (DateTimeField): When record was last modified
    """

    child = models.ForeignKey(
        Child,
        on_delete=models.CASCADE,
        related_name="naps",
    )
    napped_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "children_nap"
        ordering = ["-napped_at"]

    def __str__(self):
        return f"{self.child.name} - Nap"
