"""Forms for child creation/update and tracking record timezone handling.

LocalDateTimeFormMixin handles the critical task of converting browser-local
datetime inputs to UTC for storage and API responses. This ensures all timestamps
in the database are normalized to UTC, while the frontend handles client-side
timezone display via JavaScript.
"""

from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import Child


class ChildForm(forms.ModelForm):
    """Form for creating/updating child profiles.

    Validates child data before saving:
    - name: Required, max 100 chars
    - date_of_birth: Required, ISO format, cannot be in future
    - gender: Optional, one of 'M', 'F', 'O'

    Uses HTML5 date input widget for date_of_birth field.
    Applies Bootstrap CSS classes for consistent styling.

    Attributes:
        date_of_birth (DateField): HTML5 date input with validation
    """

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
    """Mixin to handle local timezone conversion for datetime fields.

    Critical for tracking apps (feedings, diapers, naps) which need to accept
    local datetime inputs from users and convert them to UTC for storage.

    Timezone handling architecture:
    1. Frontend: JavaScript captures browser timezone offset (getTimezoneOffset)
    2. Hidden field: tz_offset sent in form submission
    3. Form clean(): Converts local datetime to UTC using offset
    4. Database: All datetime fields stored in UTC
    5. API responses: Return UTC timestamps (frontend converts back to local)

    Subclasses must set:
        datetime_field_name: Name of the datetime field to convert (e.g., "fed_at")

    Timezone offset math:
    - JavaScript getTimezoneOffset() returns minutes offset from UTC
    - Positive offset = behind UTC (e.g., EST is UTC-5 = +300 minutes)
    - Negative offset = ahead of UTC (e.g., IST is UTC+5:30 = -330 minutes)
    - Conversion: utc_datetime = local_datetime + timedelta(minutes=offset)

    Example usage in forms.py:
        class FeedingForm(LocalDateTimeFormMixin, forms.ModelForm):
            datetime_field_name = "fed_at"

    Example usage in template:
        <input type="hidden" class="tz-offset" name="tz_offset"
               value="{{ tz_offset }}" />
        <script>
            document.querySelector('.tz-offset').value =
                new Date().getTimezoneOffset();
        </script>
    """

    datetime_field_name = None  # Subclasses MUST set this to field name

    tz_offset = forms.IntegerField(
        widget=forms.HiddenInput(attrs={"class": "tz-offset"}),
        required=False,
    )

    def clean(self):
        """Convert local datetime to UTC using timezone offset.

        Performs two conversions:
        1. Local datetime + tz_offset → UTC datetime
        2. Validate UTC datetime is not in future

        The datetime_field_name subclass attribute specifies which form field
        contains the local datetime.

        Returns:
            dict: cleaned_data with datetime field converted to UTC

        Raises:
            ValidationError: If resulting UTC datetime is in the future
        """
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

            # Validate not in future (compare UTC times)
            if utc_dt > timezone.now():
                self.add_error(
                    self.datetime_field_name,
                    "Date/time cannot be in the future.",
                )

        return cleaned_data
