"""Form for creating/updating feeding records with conditional field validation.

FeedingForm validates bottle vs. breast feeding with appropriate conditional
requirements:
- Bottle: Requires amount_oz (0.1-50.0 oz), clears breast fields
- Breast: Requires duration_minutes (1-180) and side, clears bottle fields

The clean() method enforces these rules, which are also enforced at the
database level via CheckConstraints.
"""

from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator

from children.forms import LocalDateTimeFormMixin

from .constants import (
    BOTTLE_DECIMAL_PLACES,
    BOTTLE_MAX_DIGITS,
    BOTTLE_STEP,
    MAX_BOTTLE_OZ,
    MAX_BREAST_MINUTES,
    MIN_BOTTLE_OZ,
    MIN_BREAST_MINUTES,
)
from .models import Feeding


class FeedingForm(LocalDateTimeFormMixin, forms.ModelForm):
    """Form for creating and updating feeding records.

    Extends LocalDateTimeFormMixin to convert browser-local fed_at to UTC.
    Implements conditional field validation based on feeding_type:

    **Bottle Feeding:**
    - feeding_type: 'bottle'
    - Required: amount_oz (0.1-50.0 oz)
    - Cleared: duration_minutes, side

    **Breast Feeding:**
    - feeding_type: 'breast'
    - Required: duration_minutes (1-180 min), side ('left'/'right'/'both')
    - Cleared: amount_oz

    Validation layers:
    1. Field validators: MinValueValidator, MaxValueValidator
    2. Form clean(): Conditional field requirements
    3. Database constraints: CheckConstraints at schema level

    Datetime handling:
    - Accepts local datetime from HTML5 input
    - LocalDateTimeFormMixin converts to UTC using tz_offset
    - Validation prevents future timestamps

    Attributes:
        datetime_field_name: 'fed_at' (required by LocalDateTimeFormMixin)
        fed_at: HTML5 datetime-local input
        amount_oz: Decimal input with step, min, max
        duration_minutes: Integer input with min, max
    """

    datetime_field_name = "fed_at"

    fed_at = forms.DateTimeField(
        label="Time of Feeding",
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": "form-control form-control-lg border-2 local-datetime",
            },
        ),
    )
    amount_oz = forms.DecimalField(
        label="Amount (oz)",
        max_digits=BOTTLE_MAX_DIGITS,
        decimal_places=BOTTLE_DECIMAL_PLACES,
        required=False,
        validators=[
            MinValueValidator(MIN_BOTTLE_OZ),
            MaxValueValidator(MAX_BOTTLE_OZ),
        ],
        widget=forms.NumberInput(
            attrs={
                "class": "form-control form-control-lg border-2",
                "step": str(BOTTLE_STEP),
                "min": str(MIN_BOTTLE_OZ),
                "max": str(MAX_BOTTLE_OZ),
            }
        ),
    )
    duration_minutes = forms.IntegerField(
        label="Duration (minutes)",
        required=False,
        validators=[
            MinValueValidator(MIN_BREAST_MINUTES),
            MaxValueValidator(MAX_BREAST_MINUTES),
        ],
        widget=forms.NumberInput(
            attrs={
                "class": "form-control form-control-lg border-2",
                "min": str(MIN_BREAST_MINUTES),
                "max": str(MAX_BREAST_MINUTES),
            }
        ),
    )

    class Meta:
        model = Feeding
        fields = [
            "feeding_type",
            "fed_at",
            "amount_oz",
            "duration_minutes",
            "side",
            "tz_offset",
        ]
        labels = {
            "feeding_type": "Feeding Type",
            "side": "Side",
        }
        widgets = {
            "feeding_type": forms.Select(
                attrs={"class": "form-select form-select-lg border-2"}
            ),
            "side": forms.Select(
                attrs={"class": "form-select form-select-lg border-2"}
            ),
        }

    def clean(self):
        """Validate conditional fields based on feeding_type.

        Enforces two distinct feeding types with different required fields:

        **Bottle feeding (feeding_type='bottle'):**
        - Requires: amount_oz (0.1-50.0 oz)
        - Clears: duration_minutes, side (set to None/empty)
        - Validation: amount_oz must be present

        **Breast feeding (feeding_type='breast'):**
        - Requires: duration_minutes (1-180 min), side ('left'/'right'/'both')
        - Clears: amount_oz (set to None)
        - Validation: Both duration_minutes and side must be present

        The form prevents invalid combinations (e.g., bottle + duration_minutes).
        The database schema also enforces via CheckConstraints.

        Returns:
            dict: cleaned_data with conditional fields set/cleared and validated

        Raises:
            ValidationError: Added to form errors if validation fails
        """
        cleaned_data = super().clean()
        feeding_type = cleaned_data.get("feeding_type")

        if feeding_type == Feeding.FeedingType.BOTTLE:
            if not cleaned_data.get("amount_oz"):
                self.add_error("amount_oz", "Amount is required for bottle feeding.")
            # Clear breast fields
            cleaned_data["duration_minutes"] = None
            cleaned_data["side"] = ""
        elif feeding_type == Feeding.FeedingType.BREAST:
            if not cleaned_data.get("duration_minutes"):
                self.add_error(
                    "duration_minutes", "Duration is required for breastfeeding."
                )
            if not cleaned_data.get("side"):
                self.add_error("side", "Side is required for breastfeeding.")
            # Clear bottle fields
            cleaned_data["amount_oz"] = None

        return cleaned_data
