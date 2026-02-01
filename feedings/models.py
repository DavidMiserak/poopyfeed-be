from django.db import models

from children.models import Child


class Feeding(models.Model):
    class FeedingType(models.TextChoices):
        BOTTLE = "bottle", "Bottle"
        BREAST = "breast", "Breast"

    class BreastSide(models.TextChoices):
        LEFT = "left", "Left"
        RIGHT = "right", "Right"
        BOTH = "both", "Both"

    child = models.ForeignKey(
        Child,
        on_delete=models.CASCADE,
        related_name="feedings",
    )
    feeding_type = models.CharField(max_length=10, choices=FeedingType.choices)
    fed_at = models.DateTimeField()

    # Bottle fields
    amount_oz = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True
    )

    # Breast fields
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    side = models.CharField(max_length=10, choices=BreastSide.choices, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "children_feeding"
        ordering = ["-fed_at"]

    def __str__(self):
        return f"{self.child.name} - {self.get_feeding_type_display()}"
