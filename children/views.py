from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Max
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import ChildForm
from .models import Child


class ChildListView(LoginRequiredMixin, ListView):
    model = Child
    template_name = "children/child_list.html"
    context_object_name = "children"

    def get_queryset(self):
        return Child.objects.filter(parent=self.request.user).annotate(
            last_diaper_change=Max("diaper_changes__changed_at"),
            last_nap=Max("naps__napped_at"),
            last_feeding=Max("feedings__fed_at"),
        )


class ChildCreateView(LoginRequiredMixin, CreateView):
    model = Child
    form_class = ChildForm
    template_name = "children/child_form.html"
    success_url = reverse_lazy("children:child_list")

    def form_valid(self, form):
        form.instance.parent = self.request.user
        return super().form_valid(form)


class ChildUpdateView(LoginRequiredMixin, UpdateView):
    model = Child
    form_class = ChildForm
    template_name = "children/child_form.html"
    success_url = reverse_lazy("children:child_list")

    def get_queryset(self):
        return Child.objects.filter(parent=self.request.user)


class ChildDeleteView(LoginRequiredMixin, DeleteView):
    model = Child
    template_name = "children/child_confirm_delete.html"
    success_url = reverse_lazy("children:child_list")

    def get_queryset(self):
        return Child.objects.filter(parent=self.request.user)
