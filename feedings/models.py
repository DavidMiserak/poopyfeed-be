from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
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

    # Validation constants
    MIN_BOTTLE_OZ = Decimal("0.1")
    MAX_BOTTLE_OZ = Decimal("50")
    MIN_BREAST_MINUTES = 1
    MAX_BREAST_MINUTES = 180
    BOTTLE_MAX_DIGITS = 4
    BOTTLE_DECIMAL_PLACES = 1

    child = models.ForeignKey(
        Child,
        on_delete=models.CASCADE,
        related_name="feedings",
    )
    feeding_type = models.CharField(max_length=10, choices=FeedingType.choices)
    fed_at = models.DateTimeField()

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
