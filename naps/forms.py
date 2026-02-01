from datetime import timedelta

from django import forms

from .models import Nap


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
            # tz_offset is in minutes, negative means behind UTC
            # e.g., EST is -300 (5 hours behind)
            # To convert local time to UTC, add the offset
            cleaned_data[self.datetime_field_name] = dt_value + timedelta(
                minutes=tz_offset
            )

        return cleaned_data


class NapForm(LocalDateTimeFormMixin, forms.ModelForm):
    datetime_field_name = "napped_at"

    tz_offset = forms.IntegerField(
        widget=forms.HiddenInput(attrs={"class": "tz-offset"}),
        required=False,
    )
    napped_at = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control local-datetime"},
        ),
    )

    class Meta:
        model = Nap
        fields = ["napped_at", "tz_offset"]
