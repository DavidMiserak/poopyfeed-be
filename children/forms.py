from django import forms
from django.utils import timezone

from .models import Child, DiaperChange


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


class DiaperChangeForm(forms.ModelForm):
    changed_at = forms.DateTimeField(
        initial=timezone.now,
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"},
        ),
    )

    class Meta:
        model = DiaperChange
        fields = ["change_type", "changed_at"]
        widgets = {
            "change_type": forms.Select(attrs={"class": "form-select"}),
        }
