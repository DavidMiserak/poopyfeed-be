from django import forms

from children.forms import LocalDateTimeFormMixin

from .models import DiaperChange


class DiaperChangeForm(LocalDateTimeFormMixin, forms.ModelForm):
    datetime_field_name = "changed_at"

    changed_at = forms.DateTimeField(
        label="Time of Change",
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
        labels = {
            "change_type": "Change Type",
        }
        widgets = {
            "change_type": forms.Select(
                attrs={"class": "form-select form-select-lg border-2"}
            ),
        }
