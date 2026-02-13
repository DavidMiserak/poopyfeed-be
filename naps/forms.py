from datetime import timedelta

from django import forms

from children.forms import LocalDateTimeFormMixin

from .models import Nap


class NapForm(LocalDateTimeFormMixin, forms.ModelForm):
    datetime_field_name = "napped_at"

    napped_at = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": "form-control form-control-lg border-2 local-datetime",
            },
        ),
    )

    ended_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": "form-control form-control-lg border-2 local-datetime",
            },
        ),
    )

    class Meta:
        model = Nap
        fields = ["napped_at", "ended_at", "tz_offset"]

    def clean(self):
        """Convert local datetimes to UTC and validate ended_at > napped_at."""
        cleaned_data = super().clean()
        tz_offset = cleaned_data.get("tz_offset")
        ended_at = cleaned_data.get("ended_at")

        # Convert ended_at from local to UTC using same tz_offset
        if tz_offset is not None and ended_at is not None:
            ended_at = ended_at + timedelta(minutes=tz_offset)
            cleaned_data["ended_at"] = ended_at

        # Validate ended_at > napped_at (both now in UTC)
        napped_at = cleaned_data.get("napped_at")
        ended_at = cleaned_data.get("ended_at")
        if napped_at and ended_at and ended_at <= napped_at:
            self.add_error("ended_at", "End time must be after start time.")

        return cleaned_data
