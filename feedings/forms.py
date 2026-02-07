from decimal import Decimal

from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator

from children.forms import LocalDateTimeFormMixin

from .models import Feeding

# UI constants
BOTTLE_STEP = Decimal("0.5")


class FeedingForm(LocalDateTimeFormMixin, forms.ModelForm):
    datetime_field_name = "fed_at"

    fed_at = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": "form-control form-control-lg border-2 local-datetime",
            },
        ),
    )
    amount_oz = forms.DecimalField(
        max_digits=Feeding.BOTTLE_MAX_DIGITS,
        decimal_places=Feeding.BOTTLE_DECIMAL_PLACES,
        required=False,
        validators=[
            MinValueValidator(Feeding.MIN_BOTTLE_OZ),
            MaxValueValidator(Feeding.MAX_BOTTLE_OZ),
        ],
        widget=forms.NumberInput(
            attrs={
                "class": "form-control form-control-lg border-2",
                "step": str(BOTTLE_STEP),
                "min": str(Feeding.MIN_BOTTLE_OZ),
                "max": str(Feeding.MAX_BOTTLE_OZ),
            }
        ),
    )
    duration_minutes = forms.IntegerField(
        required=False,
        validators=[
            MinValueValidator(Feeding.MIN_BREAST_MINUTES),
            MaxValueValidator(Feeding.MAX_BREAST_MINUTES),
        ],
        widget=forms.NumberInput(
            attrs={
                "class": "form-control form-control-lg border-2",
                "min": str(Feeding.MIN_BREAST_MINUTES),
                "max": str(Feeding.MAX_BREAST_MINUTES),
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
        widgets = {
            "feeding_type": forms.Select(
                attrs={"class": "form-select form-select-lg border-2"}
            ),
            "side": forms.Select(
                attrs={"class": "form-select form-select-lg border-2"}
            ),
        }

    def clean(self):
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
