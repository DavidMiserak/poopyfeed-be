"""Forms for child creation/update and tracking record timezone handling.

LocalDateTimeFormMixin converts datetime inputs from the user's profile timezone
to UTC for storage. All display and form defaults use the user's timezone (pure
Django; no JavaScript).
"""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Column, Div, Layout, Row
from django import forms
from django.utils import timezone

from .datetime_utils import (
    naive_local_to_utc,
    now_in_user_tz_str,
    utc_to_local_datetime_local_str,
)
from .models import Child

# Shared widget attrs for consistent styling (single source of truth)
INPUT_CLASS = "form-control form-control-lg border-2"
BOTTLE_PRESET_ATTRS = {
    "class": INPUT_CLASS,
    "step": "0.1",
    "min": "0.1",
    "max": "50",
}


class ChildForm(forms.ModelForm):
    """Form for creating/updating child profiles.

    Validates child data before saving:
    - name: Required, max 100 chars
    - date_of_birth: Required, ISO format, cannot be in future
    - gender: Optional, one of 'M', 'F', 'O'
    - custom_bottle_*_oz: Optional bottle feeding presets (0.1-50 oz)

    Uses HTML5 date input widget for date_of_birth field.
    Applies Bootstrap CSS classes for consistent styling.

    Attributes:
        date_of_birth (DateField): HTML5 date input with validation
    """

    date_of_birth = forms.DateField(
        widget=forms.DateInput(
            attrs={"type": "date", "class": INPUT_CLASS},
        ),
    )

    class Meta:
        model = Child
        fields = [
            "name",
            "date_of_birth",
            "gender",
            "custom_bottle_low_oz",
            "custom_bottle_mid_oz",
            "custom_bottle_high_oz",
        ]
        labels = {
            "custom_bottle_low_oz": "Low (oz)",
            "custom_bottle_mid_oz": "Mid (oz)",
            "custom_bottle_high_oz": "High (oz)",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "gender": forms.Select(
                attrs={"class": "form-select form-select-lg border-2"}
            ),
            "custom_bottle_low_oz": forms.NumberInput(attrs=BOTTLE_PRESET_ATTRS),
            "custom_bottle_mid_oz": forms.NumberInput(attrs=BOTTLE_PRESET_ATTRS),
            "custom_bottle_high_oz": forms.NumberInput(attrs=BOTTLE_PRESET_ATTRS),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in (
            "custom_bottle_low_oz",
            "custom_bottle_mid_oz",
            "custom_bottle_high_oz",
        ):
            self.fields[f].help_text = ""
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Div(
                Div(
                    HTML(
                        '<h2 class="h6 fw-bold mb-0">'
                        '<i class="fa-solid fa-child me-2 text-primary"></i>'
                        "Details</h2>"
                    ),
                    css_class="card-header bg-transparent border-0 pt-4 pb-0 px-4",
                ),
                Div(
                    "name",
                    "date_of_birth",
                    "gender",
                    css_class="card-body p-4",
                ),
                css_class="card border-0 shadow-sm rounded-4",
            ),
            Div(
                Div(
                    HTML(
                        '<h2 class="h6 fw-bold mb-0">'
                        '<i class="fa-solid fa-wine-bottle me-2 text-primary"></i>'
                        "Bottle presets</h2>"
                    ),
                    css_class="card-header bg-transparent border-0 pt-4 pb-0 px-4",
                ),
                Div(
                    HTML(
                        '<p class="text-body-secondary small mb-3">'
                        "Quick-select amounts when logging. Optional.</p>"
                    ),
                    Row(
                        Column("custom_bottle_low_oz", css_class="col-12 mb-2"),
                        Column("custom_bottle_mid_oz", css_class="col-12 mb-2"),
                        Column("custom_bottle_high_oz", css_class="col-12"),
                    ),
                    css_class="card-body p-4",
                ),
                css_class="card border-0 shadow-sm rounded-4 mt-4",
            ),
        )

    def clean_date_of_birth(self):
        """Validate that date of birth is not in the future.

        Called automatically during form validation. Prevents creation of
        children with future birth dates (obvious data entry error).

        Returns:
            date: Validated date_of_birth

        Raises:
            ValidationError: If date_of_birth is after today
        """
        date_of_birth = self.cleaned_data.get("date_of_birth")
        if date_of_birth and date_of_birth > timezone.now().date():
            raise forms.ValidationError("Date of birth cannot be in the future.")
        return date_of_birth


class LocalDateTimeFormMixin(forms.Form):
    """Mixin to convert user-timezone datetime inputs to UTC.

    Uses the request user's profile timezone (no JavaScript). Subclasses must set
    datetime_field_name to the primary datetime field. The form receives request
    via get_form_kwargs in the view; __init__ sets initial datetime in user TZ
    (edit: from instance; create: now). clean() interprets submitted naive
    datetime as user TZ and converts to UTC.
    """

    datetime_field_name: str | None = None  # Subclasses MUST set this to field name

    def __init__(self, *args, **kwargs):
        self._request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        tz = self._user_tz()
        field_name = self.datetime_field_name
        if not field_name or not tz:
            return
        instance = getattr(self, "instance", None)
        if instance is not None and getattr(instance, "pk", None):
            utc_dt = getattr(instance, field_name, None)
            if utc_dt is not None:
                self.initial[field_name] = utc_to_local_datetime_local_str(utc_dt, tz)
        elif instance is None or not getattr(instance, "pk", None):
            self.initial[field_name] = now_in_user_tz_str(tz)

    def _user_tz(self):
        """Return user's timezone or UTC."""
        if not self._request or not getattr(self._request, "user", None):
            return "UTC"
        return getattr(self._request.user, "timezone", None) or "UTC"

    def clean(self):
        """Convert naive datetime from user timezone to UTC and validate not future."""
        cleaned_data = super().clean()
        field_name = self.datetime_field_name
        dt_value = cleaned_data.get(field_name) if field_name else None
        if dt_value is not None:
            tz = self._user_tz()
            utc_dt = naive_local_to_utc(dt_value, tz)
            cleaned_data[field_name] = utc_dt
            if utc_dt > timezone.now():
                self.add_error(
                    field_name,
                    "Date/time cannot be in the future.",
                )
        return cleaned_data
