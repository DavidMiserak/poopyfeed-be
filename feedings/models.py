from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from children.models import Child

from .constants import (
    BOTTLE_DECIMAL_PLACES,
    BOTTLE_MAX_DIGITS,
    MAX_BOTTLE_OZ,
    MAX_BREAST_MINUTES,
    MIN_BOTTLE_OZ,
    MIN_BREAST_MINUTES,
)


class Feeding(models.Model):
    class FeedingType(models.TextChoices):
        BOTTLE = "bottle", "Bottle"
        BREAST = "breast", "Breast"

    class BreastSide(models.TextChoices):
        LEFT = "left", "Left"
        RIGHT = "right", "Right"
        BOTH = "both", "Both"

    # Re-export constants for backwards compatibility
    MIN_BOTTLE_OZ = MIN_BOTTLE_OZ
    MAX_BOTTLE_OZ = MAX_BOTTLE_OZ
    MIN_BREAST_MINUTES = MIN_BREAST_MINUTES
    MAX_BREAST_MINUTES = MAX_BREAST_MINUTES
    BOTTLE_MAX_DIGITS = BOTTLE_MAX_DIGITS
    BOTTLE_DECIMAL_PLACES = BOTTLE_DECIMAL_PLACES

    child = models.ForeignKey(
        Child,
        on_delete=models.CASCADE,
        related_name="feedings",
    )
    feeding_type = models.CharField(max_length=10, choices=FeedingType.choices)
    fed_at = models.DateTimeField(db_index=True)

    # Bottle fields
    amount_oz = models.DecimalField(
        max_digits=BOTTLE_MAX_DIGITS,
        decimal_places=BOTTLE_DECIMAL_PLACES,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(MIN_BOTTLE_OZ),
            MaxValueValidator(MAX_BOTTLE_OZ),
        ],
    )

    # Breast fields
    duration_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(MIN_BREAST_MINUTES),
            MaxValueValidator(MAX_BREAST_MINUTES),
        ],
    )
    side = models.CharField(max_length=10, choices=BreastSide.choices, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "children_feeding"
        ordering = ["-fed_at"]

    def __str__(self):
        return f"{self.child.name} - {self.get_feeding_type_display()}"
