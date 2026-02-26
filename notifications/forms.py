"""Forms for notification preferences and quiet hours (template-rendered settings)."""

from django import forms

from .models import NotificationPreference, QuietHours


class QuietHoursForm(forms.ModelForm):
    """Form for global quiet hours: enable/disable and time range."""

    class Meta:
        model = QuietHours
        fields = ["enabled", "start_time", "end_time"]
        widgets = {
            "enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "start_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
            "end_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
        }
        labels = {
            "enabled": "Enable quiet hours",
            "start_time": "Start (e.g. 10:00 PM)",
            "end_time": "End (e.g. 7:00 AM)",
        }


class NotificationPreferenceForm(forms.ModelForm):
    """Form for per-child notification toggles (feedings, diapers, naps)."""

    class Meta:
        model = NotificationPreference
        fields = ["notify_feedings", "notify_diapers", "notify_naps"]
        widgets = {
            "notify_feedings": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notify_diapers": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notify_naps": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "notify_feedings": "Feedings",
            "notify_diapers": "Diaper changes",
            "notify_naps": "Naps",
        }
