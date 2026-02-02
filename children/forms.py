from django import forms

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
