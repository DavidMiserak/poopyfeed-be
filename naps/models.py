from django.db import models

from children.models import Child


class Nap(models.Model):
    child = models.ForeignKey(
        Child,
        on_delete=models.CASCADE,
        related_name="naps",
    )
    napped_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "children_nap"
        ordering = ["-napped_at"]

    def __str__(self):
        return f"{self.child.name} - Nap"
