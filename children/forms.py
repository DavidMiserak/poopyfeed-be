from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import Child


class ChildForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control form-control-lg border-2"},
        ),
    )

    class Meta:
        model = Child
        fields = ["name", "date_of_birth", "gender"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control form-control-lg border-2"}
            ),
            "gender": forms.Select(
                attrs={"class": "form-select form-select-lg border-2"}
            ),
        }

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data.get("date_of_birth")
        if date_of_birth and date_of_birth > timezone.now().date():
            raise forms.ValidationError("Date of birth cannot be in the future.")
        return date_of_birth


class LocalDateTimeFormMixin(forms.Form):
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
            utc_dt = dt_value + timedelta(minutes=tz_offset)
            cleaned_data[self.datetime_field_name] = utc_dt

            # Validate not in future
            if utc_dt > timezone.now():
                self.add_error(
                    self.datetime_field_name,
                    "Date/time cannot be in the future.",
                )

        return cleaned_data
