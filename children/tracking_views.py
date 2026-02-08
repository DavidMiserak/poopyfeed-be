"""Base views for tracking apps (diapers, feedings, naps).

These base classes consolidate common CRUD patterns across all tracking apps.
Each tracking app inherits from these and only needs to specify model-specific
attributes (model, form_class, template_name, success_url_name).
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .mixins import ChildAccessMixin, ChildEditMixin
from .models import Child, ChildShare


class TrackingListView(ChildAccessMixin, ListView):
    """Base ListView for tracking records (diaper changes, feedings, naps).

    Subclasses must set:
        model: The tracking model class (e.g., DiaperChange, Feeding, Nap)
        template_name: Path to list template (e.g., "diapers/diaperchange_list.html")
        context_object_name: Name for queryset in template (e.g., "diaper_changes")

    Example:
        class DiaperChangeListView(TrackingListView):
            model = DiaperChange
            template_name = "diapers/diaperchange_list.html"
            context_object_name = "diaper_changes"
    """

    def get_child_for_access_check(self):
        return get_object_or_404(Child, pk=self.kwargs["child_pk"])

    def get_queryset(self):
        return self.model.objects.filter(child=self.child)


class TrackingCreateView(ChildAccessMixin, CreateView):
    """Base CreateView for tracking records.

    Subclasses must set:
        model: The tracking model class
        form_class: The form class (e.g., DiaperChangeForm)
        template_name: Path to form template (e.g., "diapers/diaperchange_form.html")
        success_url_name: URL name for redirect (e.g., "diapers:diaper_list")

    Example:
        class DiaperChangeCreateView(TrackingCreateView):
            model = DiaperChange
            form_class = DiaperChangeForm
            template_name = "diapers/diaperchange_form.html"
            success_url_name = "diapers:diaper_list"
    """

    success_url_name = None  # Must be set by subclass

    def get_child_for_access_check(self):
        return get_object_or_404(Child, pk=self.kwargs["child_pk"])

    def form_valid(self, form):
        form.instance.child = self.child
        return super().form_valid(form)

    def get_success_url(self):
        if not self.success_url_name:
            raise NotImplementedError("Subclass must set success_url_name")
        return reverse(self.success_url_name, kwargs={"child_pk": self.child.pk})


class TrackingUpdateView(ChildEditMixin, UpdateView):
    """Base UpdateView for tracking records.

    Allows editing by owner or co-parent (enforced by ChildEditMixin).

    Subclasses must set:
        model: The tracking model class
        form_class: The form class
        template_name: Path to form template
        success_url_name: URL name for redirect

    Example:
        class DiaperChangeUpdateView(TrackingUpdateView):
            model = DiaperChange
            form_class = DiaperChangeForm
            template_name = "diapers/diaperchange_form.html"
            success_url_name = "diapers:diaper_list"
    """

    success_url_name = None  # Must be set by subclass

    def get_child_for_access_check(self):
        # Get child from the tracking record object
        obj = self.get_object()
        return obj.child

    def get_queryset(self):
        # Allow editing by owner or co-parent
        return self.model.objects.filter(
            Q(child__parent=self.request.user)
            | Q(
                child__shares__user=self.request.user,
                child__shares__role=ChildShare.Role.CO_PARENT,
            )
        ).distinct()

    def get_success_url(self):
        if not self.success_url_name:
            raise NotImplementedError("Subclass must set success_url_name")
        return reverse(self.success_url_name, kwargs={"child_pk": self.object.child.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["child"] = self.object.child
        return context


class TrackingDeleteView(ChildEditMixin, DeleteView):
    """Base DeleteView for tracking records.

    Allows deleting by owner or co-parent (enforced by ChildEditMixin).

    Subclasses must set:
        model: The tracking model class
        template_name: Path to confirm delete template
        success_url_name: URL name for redirect

    Example:
        class DiaperChangeDeleteView(TrackingDeleteView):
            model = DiaperChange
            template_name = "diapers/diaperchange_confirm_delete.html"
            success_url_name = "diapers:diaper_list"
    """

    success_url_name = None  # Must be set by subclass

    def get_child_for_access_check(self):
        obj = self.get_object()
        return obj.child

    def get_queryset(self):
        # Allow deleting by owner or co-parent
        return self.model.objects.filter(
            Q(child__parent=self.request.user)
            | Q(
                child__shares__user=self.request.user,
                child__shares__role=ChildShare.Role.CO_PARENT,
            )
        ).distinct()

    def get_success_url(self):
        if not self.success_url_name:
            raise NotImplementedError("Subclass must set success_url_name")
        return reverse(self.success_url_name, kwargs={"child_pk": self.object.child.pk})
