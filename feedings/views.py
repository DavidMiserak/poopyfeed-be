from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from children.mixins import ChildAccessMixin, ChildEditMixin
from children.models import Child, ChildShare

from .forms import FeedingForm
from .models import Feeding

URL_FEEDING_LIST = "feedings:feeding_list"


class FeedingListView(ChildAccessMixin, ListView):
    model = Feeding
    template_name = "feedings/feeding_list.html"
    context_object_name = "feedings"

    def get_child_for_access_check(self):
        return get_object_or_404(Child, pk=self.kwargs["child_pk"])

    def get_queryset(self):
        return Feeding.objects.filter(child=self.child)


class FeedingCreateView(ChildAccessMixin, CreateView):
    model = Feeding
    form_class = FeedingForm
    template_name = "feedings/feeding_form.html"

    def get_child_for_access_check(self):
        return get_object_or_404(Child, pk=self.kwargs["child_pk"])

    def form_valid(self, form):
        form.instance.child = self.child
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(URL_FEEDING_LIST, kwargs={"child_pk": self.child.pk})


class FeedingUpdateView(ChildEditMixin, UpdateView):
    model = Feeding
    form_class = FeedingForm
    template_name = "feedings/feeding_form.html"

    def get_child_for_access_check(self):
        obj = self.get_object()
        return obj.child

    def get_queryset(self):
        # Allow editing by owner or co-parent
        return Feeding.objects.filter(
            Q(child__parent=self.request.user)
            | Q(
                child__shares__user=self.request.user,
                child__shares__role=ChildShare.Role.CO_PARENT,
            )
        ).distinct()

    def get_success_url(self):
        return reverse(URL_FEEDING_LIST, kwargs={"child_pk": self.object.child.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["child"] = self.object.child
        return context


class FeedingDeleteView(ChildEditMixin, DeleteView):
    model = Feeding
    template_name = "feedings/feeding_confirm_delete.html"

    def get_child_for_access_check(self):
        obj = self.get_object()
        return obj.child

    def get_queryset(self):
        # Allow deleting by owner or co-parent
        return Feeding.objects.filter(
            Q(child__parent=self.request.user)
            | Q(
                child__shares__user=self.request.user,
                child__shares__role=ChildShare.Role.CO_PARENT,
            )
        ).distinct()

    def get_success_url(self):
        return reverse(URL_FEEDING_LIST, kwargs={"child_pk": self.object.child.pk})
