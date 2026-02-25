from zoneinfo import available_timezones

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Layout, Row
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.core.exceptions import ValidationError


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = (
            "email",
            "username",
            "timezone",
        )


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = get_user_model()
        fields = (
            "email",
            "username",
            "timezone",
        )


class ProfileForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ("first_name", "last_name", "email", "timezone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tz_choices = [(tz, tz) for tz in sorted(available_timezones())]
        self.fields["timezone"].widget = forms.Select(choices=tz_choices)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("first_name", css_class="col-sm-6"),
                Column("last_name", css_class="col-sm-6"),
            ),
            "email",
            "timezone",
        )

    def clean_email(self):
        email = self.cleaned_data["email"]
        User = get_user_model()
        if User.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email


class DeleteAccountForm(forms.Form):
    current_password = forms.CharField(
        widget=forms.PasswordInput(),
        label="Confirm your password",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_current_password(self):
        password = self.cleaned_data["current_password"]
        if self.user and not self.user.check_password(password):
            raise ValidationError("Current password is incorrect.")
        return password
