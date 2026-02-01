from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from children.models import Child

from .forms import NapForm
from .models import Nap


class NapListView(LoginRequiredMixin, ListView):
    model = Nap
    template_name = "naps/nap_list.html"
    context_object_name = "naps"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        self.child = get_object_or_404(
            Child, pk=kwargs["child_pk"], parent=request.user
        )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Nap.objects.filter(child=self.child)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["child"] = self.child
        return context


class NapCreateView(LoginRequiredMixin, CreateView):
    model = Nap
    form_class = NapForm
    template_name = "naps/nap_form.html"

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
        return reverse("naps:nap_list", kwargs={"child_pk": self.child.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["child"] = self.child
        return context


class NapUpdateView(LoginRequiredMixin, UpdateView):
    model = Nap
    form_class = NapForm
    template_name = "naps/nap_form.html"

    def get_queryset(self):
        return Nap.objects.filter(child__parent=self.request.user)

    def get_success_url(self):
        return reverse("naps:nap_list", kwargs={"child_pk": self.object.child.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["child"] = self.object.child
        return context


class NapDeleteView(LoginRequiredMixin, DeleteView):
    model = Nap
    template_name = "naps/nap_confirm_delete.html"

    def get_queryset(self):
        return Nap.objects.filter(child__parent=self.request.user)

    def get_success_url(self):
        return reverse("naps:nap_list", kwargs={"child_pk": self.object.child.pk})
