from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from children.models import Child

from .forms import DiaperChangeForm
from .models import DiaperChange


class DiaperChangeListView(LoginRequiredMixin, ListView):
    model = DiaperChange
    template_name = "diapers/diaperchange_list.html"
    context_object_name = "diaper_changes"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        self.child = get_object_or_404(
            Child, pk=kwargs["child_pk"], parent=request.user
        )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return DiaperChange.objects.filter(child=self.child)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["child"] = self.child
        return context


class DiaperChangeCreateView(LoginRequiredMixin, CreateView):
    model = DiaperChange
    form_class = DiaperChangeForm
    template_name = "diapers/diaperchange_form.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        self.child = get_object_or_404(
            Child, pk=kwargs["child_pk"], parent=request.user
        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.child = self.child
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("diapers:diaper_list", kwargs={"child_pk": self.child.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["child"] = self.child
        return context


class DiaperChangeUpdateView(LoginRequiredMixin, UpdateView):
    model = DiaperChange
    form_class = DiaperChangeForm
    template_name = "diapers/diaperchange_form.html"

    def get_queryset(self):
        return DiaperChange.objects.filter(child__parent=self.request.user)

    def get_success_url(self):
        return reverse("diapers:diaper_list", kwargs={"child_pk": self.object.child.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["child"] = self.object.child
        return context


class DiaperChangeDeleteView(LoginRequiredMixin, DeleteView):
    model = DiaperChange
    template_name = "diapers/diaperchange_confirm_delete.html"

    def get_queryset(self):
        return DiaperChange.objects.filter(child__parent=self.request.user)

    def get_success_url(self):
        return reverse("diapers:diaper_list", kwargs={"child_pk": self.object.child.pk})
