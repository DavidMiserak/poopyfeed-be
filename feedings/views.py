from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from children.models import Child

from .forms import FeedingForm
from .models import Feeding


class FeedingListView(LoginRequiredMixin, ListView):
    model = Feeding
    template_name = "feedings/feeding_list.html"
    context_object_name = "feedings"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        self.child = get_object_or_404(
            Child, pk=kwargs["child_pk"], parent=request.user
        )
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Feeding.objects.filter(child=self.child)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["child"] = self.child
        return context


class FeedingCreateView(LoginRequiredMixin, CreateView):
    model = Feeding
    form_class = FeedingForm
    template_name = "feedings/feeding_form.html"

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
        return reverse("feedings:feeding_list", kwargs={"child_pk": self.child.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["child"] = self.child
        return context


class FeedingUpdateView(LoginRequiredMixin, UpdateView):
    model = Feeding
    form_class = FeedingForm
    template_name = "feedings/feeding_form.html"

    def get_queryset(self):
        return Feeding.objects.filter(child__parent=self.request.user)

    def get_success_url(self):
        return reverse(
            "feedings:feeding_list", kwargs={"child_pk": self.object.child.pk}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["child"] = self.object.child
        return context


class FeedingDeleteView(LoginRequiredMixin, DeleteView):
    model = Feeding
    template_name = "feedings/feeding_confirm_delete.html"

    def get_queryset(self):
        return Feeding.objects.filter(child__parent=self.request.user)

    def get_success_url(self):
        return reverse(
            "feedings:feeding_list", kwargs={"child_pk": self.object.child.pk}
        )
