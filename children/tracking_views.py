"""Base views for tracking apps (diapers, feedings, naps).

Consolidates common CRUD patterns across all tracking apps using class-based
views with permission mixins. Eliminates duplication and enforces consistent
permission checks (owner/co-parent can edit, caregiver can only view/add).

Each tracking app (feedings, diapers, naps) inherits from these base classes:
- TrackingListView: GET /children/{child_pk}/diapers/
- TrackingCreateView: GET/POST /children/{child_pk}/diapers/create/
- TrackingUpdateView: GET/POST /children/{child_pk}/diapers/{id}/edit/
- TrackingDeleteView: GET/POST /children/{child_pk}/diapers/{id}/delete/

Subclasses only need to specify:
- model: Tracking model (DiaperChange, Feeding, Nap)
- form_class: Form class for create/update
- template_name: Template path (e.g., "diapers/diaperchange_list.html")
- context_object_name: Template variable name (e.g., "diaper_changes")
- success_url_name: URL name for redirect (e.g., "diapers:diaper_list")

Permission model:
- Owner (child.parent): Full access (view, add, edit, delete)
- Co-parent (ChildShare.CO_PARENT): Can view, add, edit, delete
- Caregiver (ChildShare.CAREGIVER): Can view and add only
- Views use ChildAccessMixin/ChildEditMixin to enforce via dispatch()
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .mixins import ChildAccessMixin, ChildEditMixin
from .models import Child, ChildShare

# Error message for missing success_url_name attribute
ERROR_MISSING_SUCCESS_URL_NAME = "Subclass must set success_url_name"


class TrackingEditQuerysetMixin:
    """Mixin for edit views (Update/Delete) with shared queryset filtering.

    Used by TrackingUpdateView and TrackingDeleteView to filter querysets.
    Ensures only owner and co-parent can access records (caregiver cannot edit/delete).
    Works with ChildEditMixin to enforce role-based permissions.

    Filtering logic:
    - Owner (child.parent = user): Can edit/delete their own records
    - Co-parent (ChildShare with CO_PARENT role): Can edit/delete shared records
    - Caregiver: Cannot edit/delete (filtered out of queryset)
    """

    def get_queryset(self):
        """Filter tracking records to only those owner/co-parent can edit.

        Returns QuerySet of tracking records where:
        1. User is the child's owner (parent), OR
        2. User is a co-parent (has ChildShare with CO_PARENT role)

        Returns:
            QuerySet: Distinct tracking records filtered by permission

        Example:
            # Owner accessing their own record
            # ChildDiaperChange where child.parent == request.user

            # Co-parent accessing shared child's record
            # DiaperChange where child has ChildShare with CO_PARENT role
        """
        return self.model.objects.filter(
            Q(child__parent=self.request.user)
            | Q(
                child__shares__user=self.request.user,
                child__shares__role=ChildShare.Role.CO_PARENT,
            )
        ).distinct()

    def get_child_for_access_check(self):
        """Get child from the tracking record object.

        Used by ChildEditMixin to verify user's permission for this specific child.
        Extracts child from the tracking record being edited/deleted.

        Returns:
            Child: The child who owns this tracking record
        """
        obj = self.get_object()
        return obj.child


class TrackingListView(ChildAccessMixin, ListView):
    """Base ListView for tracking records (diaper changes, feedings, naps).

    Handles GET requests to list all tracking records for a child. Permission
    checking is enforced by ChildAccessMixin, which allows any authenticated
    user with access to the child (owner/co-parent/caregiver).

    Sorting: Records are ordered by timestamp descending (newest first) via
    Meta.ordering on the model class.

    Pagination: List is paginated (paginate_by); context includes page_obj and
    paginator. Aligns with API PAGE_SIZE (50) for consistency.

    Template context:
    - {context_object_name}: Current page of tracking records (e.g., "diaper_changes")
    - page_obj: Page object (has_previous, has_next, number, paginator, etc.)
    - child: The child being viewed
    - user_role: Current user's role ('owner', 'co-parent', 'caregiver')

    Required subclass attributes:
        model (Model): Tracking model class (DiaperChange, Feeding, Nap)
        template_name (str): Template path (e.g., "diapers/diaperchange_list.html")
        context_object_name (str): Template variable (e.g., "diaper_changes")

    Example:
        class DiaperChangeListView(TrackingListView):
            model = DiaperChange
            template_name = "diapers/diaperchange_list.html"
            context_object_name = "diaper_changes"
    """

    def get_child_for_access_check(self):
        """Get child from URL kwargs (child_pk).

        Returns:
            Child: Child to list records for

        Raises:
            Http404: If child_pk is missing or child not found
        """
        return get_object_or_404(Child, pk=self.kwargs["child_pk"])

    def get_queryset(self):
        """Get tracking records for the child.

        Returns:
            QuerySet: All tracking records for self.child, ordered by timestamp desc

        Note:
            Model's Meta.ordering ensures newest records appear first (e.g., -changed_at)
        """
        return self.model.objects.filter(child=self.child)

    paginate_by = 50


class TrackingCreateView(ChildAccessMixin, CreateView):
    """Base CreateView for tracking records.

    Handles GET (form display) and POST (form submission) for creating new
    tracking records (feedings, diapers, naps). ChildAccessMixin allows any
    user with access to the child to add records (owner/co-parent/caregiver).

    Timezone handling: Forms using LocalDateTimeFormMixin use the user's profile
    timezone; datetime inputs are shown and interpreted in that timezone (pure Django).

    Template context (GET):
    - form: The form instance
    - child: The child being tracked
    - user_role: Current user's role

    Success behavior:
    - Saves record with child_id from URL
    - Redirects to list view (success_url_name)
    - Shows Django messages (optional, see form.html template)

    Required subclass attributes:
        model (Model): Tracking model (DiaperChange, Feeding, Nap)
        form_class (Form): Form class for validation
        template_name (str): Form template path
        success_url_name (str): URL name for redirect list view

    Example:
        class DiaperChangeCreateView(TrackingCreateView):
            model = DiaperChange
            form_class = DiaperChangeForm
            template_name = "diapers/diaperchange_form.html"
            success_url_name = "diapers:diaper_list"
    """

    success_url_name: str | None = None  # Must be set by subclass

    def get_child_for_access_check(self):
        """Get child from URL kwargs (child_pk).

        Returns:
            Child: Child to create tracking record for

        Raises:
            Http404: If child_pk is missing or child not found
        """
        return get_object_or_404(Child, pk=self.kwargs["child_pk"])

    def get_form_kwargs(self):
        """Pass request so the form can use user timezone for datetime."""
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        """Set child before saving form.

        Called when form validation passes. Associates the tracking record
        with the correct child before saving to database.

        Args:
            form: Valid form instance

        Returns:
            HttpResponse: Redirect to success_url
        """
        form.instance.child = self.child
        return super().form_valid(form)

    def get_success_url(self):
        """Generate URL to list view after successful save.

        Returns:
            str: Reversed URL for list view with child_pk

        Raises:
            NotImplementedError: If subclass doesn't set success_url_name

        Example:
            # If success_url_name = "diapers:diaper_list"
            # Returns: /children/123/diapers/
        """
        if not self.success_url_name:
            raise NotImplementedError(ERROR_MISSING_SUCCESS_URL_NAME)
        return reverse(self.success_url_name, kwargs={"child_pk": self.child.pk})


class TrackingUpdateView(TrackingEditQuerysetMixin, ChildEditMixin, UpdateView):
    """Base UpdateView for tracking records (edit functionality).

    Handles GET (form display) and POST (form submission) for editing existing
    tracking records. Permission checking via ChildEditMixin restricts editing
    to owner and co-parent only. Caregiver role returns Http404.

    Edit capability:
    - Owner: Can edit any of their child's records
    - Co-parent: Can edit shared child's records
    - Caregiver: Cannot edit (forbidden via ChildEditMixin)

    Timezone handling: Form datetimes are in the user's profile timezone (pure Django).

    Template context (GET):
    - form: The form instance with current values
    - object: The tracking record being edited
    - child: The child who owns this record
    - user_role: Current user's role

    Success behavior:
    - Saves updated record
    - Redirects to list view (success_url_name)

    Required subclass attributes:
        model (Model): Tracking model
        form_class (Form): Form class for validation and display
        template_name (str): Form template path
        success_url_name (str): URL name for redirect

    Example:
        class DiaperChangeUpdateView(TrackingUpdateView):
            model = DiaperChange
            form_class = DiaperChangeForm
            template_name = "diapers/diaperchange_form.html"
            success_url_name = "diapers:diaper_list"
    """

    success_url_name: str | None = None  # Must be set by subclass

    def get_form_kwargs(self):
        """Pass request so the form can use user timezone for datetime."""
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_success_url(self):
        """Generate URL to list view after successful update.

        Returns:
            str: Reversed URL for list view with child_pk from edited record

        Raises:
            NotImplementedError: If subclass doesn't set success_url_name
        """
        if not self.success_url_name:
            raise NotImplementedError(ERROR_MISSING_SUCCESS_URL_NAME)
        return reverse(self.success_url_name, kwargs={"child_pk": self.object.child.pk})

    def get_context_data(self, **kwargs):
        """Add child to template context.

        Args:
            **kwargs: Context from superclass

        Returns:
            dict: Updated context with 'child' key
        """
        context = super().get_context_data(**kwargs)
        context["child"] = self.object.child
        return context


class TrackingDeleteView(TrackingEditQuerysetMixin, ChildEditMixin, DeleteView):
    """Base DeleteView for tracking records (delete confirmation).

    Handles GET (confirmation page) and POST (deletion) for removing tracking
    records. Permission checking via ChildEditMixin restricts deletion to owner
    and co-parent only. Caregiver role returns Http404.

    Delete capability:
    - Owner: Can delete any of their child's records
    - Co-parent: Can delete shared child's records
    - Caregiver: Cannot delete (forbidden via ChildEditMixin)

    Deletion behavior:
    - Cascading: When child is deleted, all tracking records cascade delete
    - Timestamps: created_at/updated_at are permanent; deletion removes entire record
    - No soft delete: Records are permanently removed from database

    Template context (GET):
    - object: The tracking record being deleted
    - child: The child who owns this record

    Success behavior:
    - Deletes record from database
    - Redirects to list view (success_url_name)
    - Shows Django messages (optional, see confirm_delete.html template)

    Required subclass attributes:
        model (Model): Tracking model
        template_name (str): Confirmation template (e.g., "diapers/diaperchange_confirm_delete.html")
        success_url_name (str): URL name for redirect after deletion

    Example:
        class DiaperChangeDeleteView(TrackingDeleteView):
            model = DiaperChange
            template_name = "diapers/diaperchange_confirm_delete.html"
            success_url_name = "diapers:diaper_list"
    """

    success_url_name: str | None = None  # Must be set by subclass

    def get_success_url(self):
        """Generate URL to list view after successful deletion.

        Note: Must access self.object.child before delete() removes the object.

        Returns:
            str: Reversed URL for list view with child_pk

        Raises:
            NotImplementedError: If subclass doesn't set success_url_name
        """
        if not self.success_url_name:
            raise NotImplementedError(ERROR_MISSING_SUCCESS_URL_NAME)
        return reverse(self.success_url_name, kwargs={"child_pk": self.object.child.pk})
