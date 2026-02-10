from django.db import models
from django.db.models import CheckConstraint, Q
from django.core.validators import MaxValueValidator, MinValueValidator

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
        constraints = [
            # Bottle feedings must have amount_oz and no breast fields
            CheckConstraint(
                condition=Q(
                    feeding_type="bottle",
                    amount_oz__isnull=False,
                    duration_minutes__isnull=True,
                    side__exact="",
                )
                | Q(feeding_type="breast"),
                name="bottle_has_amount_oz",
            ),
            # Breast feedings must have duration_minutes and side, no amount_oz
            CheckConstraint(
                condition=Q(
                    feeding_type="breast",
                    duration_minutes__isnull=False,
                    side__in=["left", "right", "both"],
                    amount_oz__isnull=True,
                )
                | Q(feeding_type="bottle"),
                name="breast_has_duration_and_side",
            ),
            # Validate bottle amount is within range
            CheckConstraint(
                condition=Q(
                    amount_oz__isnull=True,
                )
                | Q(amount_oz__gte=MIN_BOTTLE_OZ, amount_oz__lte=MAX_BOTTLE_OZ),
                name="bottle_amount_in_range",
            ),
            # Validate breast duration is within range
            CheckConstraint(
                condition=Q(
                    duration_minutes__isnull=True,
                )
                | Q(
                    duration_minutes__gte=MIN_BREAST_MINUTES,
                    duration_minutes__lte=MAX_BREAST_MINUTES,
                ),
                name="breast_duration_in_range",
            ),
        ]

    def __str__(self):
        return f"{self.child.name} - {self.get_feeding_type_display()}"
