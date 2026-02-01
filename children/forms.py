from datetime import timedelta

from django import forms

from .models import Child, DiaperChange, Feeding, Nap


class ChildForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control"},
        ),
    )

    class Meta:
        model = Child
        fields = ["name", "date_of_birth", "gender"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-select"}),
        }


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


class DiaperChangeForm(LocalDateTimeFormMixin, forms.ModelForm):
    datetime_field_name = "changed_at"

    tz_offset = forms.IntegerField(
        widget=forms.HiddenInput(attrs={"class": "tz-offset"}),
        required=False,
    )
    changed_at = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control local-datetime"},
        ),
    )

    class Meta:
        model = DiaperChange
        fields = ["change_type", "changed_at", "tz_offset"]
        widgets = {
            "change_type": forms.Select(attrs={"class": "form-select"}),
        }


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


class FeedingForm(LocalDateTimeFormMixin, forms.ModelForm):
    datetime_field_name = "fed_at"

    tz_offset = forms.IntegerField(
        widget=forms.HiddenInput(attrs={"class": "tz-offset"}),
        required=False,
    )
    fed_at = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control local-datetime"},
        ),
    )
    amount_oz = forms.DecimalField(
        max_digits=4,
        decimal_places=1,
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.5", "min": "0"}
        ),
    )
    duration_minutes = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
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
            "feeding_type": forms.Select(attrs={"class": "form-select"}),
            "side": forms.Select(attrs={"class": "form-select"}),
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
