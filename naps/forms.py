from django import forms

from children.datetime_utils import (
    naive_local_to_utc,
    utc_to_local_datetime_local_str,
)
from children.forms import LocalDateTimeFormMixin

from .models import Nap


class NapForm(LocalDateTimeFormMixin, forms.ModelForm):
    datetime_field_name = "napped_at"

    napped_at = forms.DateTimeField(
        label="Start Time",
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": "form-control form-control-lg border-2 local-datetime",
            },
        ),
    )

    ended_at = forms.DateTimeField(
        label="End Time (optional)",
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
        fields = ["napped_at", "ended_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tz = self._user_tz()
        if self.instance and getattr(self.instance, "pk", None) and tz:
            ended_at = getattr(self.instance, "ended_at", None)
            if ended_at is not None:
                self.initial["ended_at"] = utc_to_local_datetime_local_str(ended_at, tz)

    def clean(self):
        """Convert ended_at from user TZ to UTC and validate ended_at > napped_at."""
        cleaned_data = super().clean()
        ended_at = cleaned_data.get("ended_at")
        if ended_at is not None and self._request:
            tz = self._user_tz()
            cleaned_data["ended_at"] = naive_local_to_utc(ended_at, tz)
        napped_at = cleaned_data.get("napped_at")
        ended_at = cleaned_data.get("ended_at")
        if napped_at and ended_at and ended_at <= napped_at:
            self.add_error("ended_at", "End time must be after start time.")
        return cleaned_data
