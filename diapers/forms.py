from datetime import timedelta

from django import forms

from .models import DiaperChange


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


class DiaperChangeForm(LocalDateTimeFormMixin, forms.ModelForm):
    datetime_field_name = "changed_at"

    tz_offset = forms.IntegerField(
        widget=forms.HiddenInput(attrs={"class": "tz-offset"}),
        required=False,
    )
    changed_at = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": "form-control form-control-lg border-2 local-datetime",
            },
        ),
    )

    class Meta:
        model = DiaperChange
        fields = ["change_type", "changed_at", "tz_offset"]
        widgets = {
            "change_type": forms.Select(
                attrs={"class": "form-select form-select-lg border-2"}
            ),
        }
