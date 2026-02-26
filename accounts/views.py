from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import TemplateView

from .forms import DeleteAccountForm, ProfileForm


class AccountSettingsView(LoginRequiredMixin, TemplateView):
    template_name = "account/settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if "profile_form" not in context:
            context["profile_form"] = ProfileForm(instance=self.request.user)
        if "delete_form" not in context:
            context["delete_form"] = DeleteAccountForm(user=self.request.user)
        context["profile_success"] = self.request.GET.get("profile_saved") == "1"
        context["notifications_success"] = (
            self.request.GET.get("notifications_saved") == "1"
        )
        self._add_quiet_hours_context(context)
        return context

    def _add_quiet_hours_context(self, context):
        """Add quiet hours form for the account settings page."""
        from notifications.forms import QuietHoursForm
        from notifications.models import QuietHours

        quiet_hours, _ = QuietHours.objects.get_or_create(user=self.request.user)
        context["quiet_hours_form"] = context.get("quiet_hours_form") or QuietHoursForm(
            instance=quiet_hours
        )

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")

        if action == "profile":
            return self._handle_profile(request)
        elif action == "delete":
            return self._handle_delete(request)
        elif action == "quiet_hours":
            return self._handle_quiet_hours(request)

        return redirect("account_settings")

    def _handle_profile(self, request):
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect(f"{request.path}?profile_saved=1")
        context = self.get_context_data(profile_form=form)
        return self.render_to_response(context)

    def _handle_delete(self, request):
        form = DeleteAccountForm(request.POST, user=request.user)
        if form.is_valid():
            request.user.delete()
            return redirect("home")
        context = self.get_context_data(delete_form=form)
        return self.render_to_response(context)

    def _handle_quiet_hours(self, request):
        from notifications.forms import QuietHoursForm
        from notifications.models import QuietHours

        quiet_hours, _ = QuietHours.objects.get_or_create(user=request.user)
        form = QuietHoursForm(request.POST, instance=quiet_hours)
        if form.is_valid():
            form.save()
            return redirect(f"{request.path}?notifications_saved=1")
        context = self.get_context_data(quiet_hours_form=form)
        return self.render_to_response(context)
