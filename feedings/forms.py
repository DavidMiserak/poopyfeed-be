from datetime import timedelta
from decimal import Decimal

from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator

from .models import Feeding


class LocalDateTimeFormMixin:
    """Mixin to handle local timezone input for datetime fields."""

    datetime_field_name = None  # Subclasses must set this

    tz_offset = forms.IntegerField(
        widget=forms.HiddenInput(attrs={"class": "tz-offset"}),
        required=False,
    )

    def clean(self):
        cleaned_data = super().clean()
        tz_offset = cleaned_data.get("tz_offset")
        dt_value = cleaned_data.get(self.datetime_field_name)

        if tz_offset is not None and dt_value is not None:
            # tz_offset is JavaScript's getTimezoneOffset() in minutes
            # Positive means behind UTC (e.g., EST UTC-5 = +300)
            # Negative means ahead of UTC (e.g., IST UTC+5:30 = -330)
            # To convert local time to UTC, add the offset
            cleaned_data[self.datetime_field_name] = dt_value + timedelta(
                minutes=tz_offset
            )

        return cleaned_data


class FeedingForm(LocalDateTimeFormMixin, forms.ModelForm):
    datetime_field_name = "fed_at"

    tz_offset = forms.IntegerField(
        widget=forms.HiddenInput(attrs={"class": "tz-offset"}),
        required=False,
    )
    fed_at = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": "form-control form-control-lg border-2 local-datetime",
            },
        ),
    )
    amount_oz = forms.DecimalField(
        max_digits=4,
        decimal_places=1,
        required=False,
        validators=[
            MinValueValidator(Decimal("0.1")),
            MaxValueValidator(Decimal("50")),
        ],
        widget=forms.NumberInput(
            attrs={
                "class": "form-control form-control-lg border-2",
                "step": "0.5",
                "min": "0.1",
                "max": "50",
            }
        ),
    )
    duration_minutes = forms.IntegerField(
        required=False,
        validators=[MinValueValidator(1), MaxValueValidator(180)],
        widget=forms.NumberInput(
            attrs={
                "class": "form-control form-control-lg border-2",
                "min": "1",
                "max": "180",
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
