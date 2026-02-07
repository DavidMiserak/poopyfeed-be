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

    class Meta:
        model = Nap
        fields = ["napped_at", "tz_offset"]
