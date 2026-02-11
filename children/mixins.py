"""Permission mixins for child access control.

These mixins implement view-level authorization for child access. They are used in
conjunction with Child.has_access() and related permission methods to enforce
role-based access control across the application.

Security model:
- Returns Http404 (not Http403) to avoid revealing child existence
- Checks are performed in dispatch() before view execution
- Subclasses can override check_child_permission() for additional checks
- Authenticated users are required (LoginRequiredMixin)
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Child


class ChildAccessMixin(LoginRequiredMixin):
    """Base mixin for views requiring any access to child (view or add).

    Ensures user has some level of access to the child (owner, co-parent, or
    caregiver). Can be subclassed to enforce stricter permissions (edit, owner).

    Sets self.child and self.user_role during dispatch() for use in view methods.

    Attributes (set by dispatch):
        child (Child): The child object from URL kwargs
        user_role (str): User's role ('owner', 'co-parent', 'caregiver', None)

    Example:
        class ChildListView(ChildAccessMixin, ListView):
            model = Child
            def get_queryset(self):
                return Child.objects.filter(id=self.child.id)
    """

    def get_child_for_access_check(self):
        """Get the child object for permission checking.

        Looks for 'child_pk' or 'pk' in URL kwargs. Returns 404 if not found.

        Returns:
            Child: The child object from database

        Raises:
            Http404: If child does not exist
        """
        child_pk = self.kwargs.get("child_pk") or self.kwargs.get("pk")
        return get_object_or_404(Child, pk=child_pk)

    def check_child_permission(self, request):
        """Override in subclasses for additional permission checks.

        This method is called after basic access is verified. Return False to
        deny access (returns Http404). Used by ChildEditMixin and ChildOwnerMixin.

        Args:
            request: HTTP request object

        Returns:
            bool: True to allow access, False to deny
        """
        return True

    def dispatch(self, request, *args, **kwargs):
        """Check child access before dispatching to view.

        Permission checks in order:
        1. LoginRequiredMixin (redirect if not authenticated)
        2. Child exists and user has access (Http404 if not)
        3. check_child_permission() passes (Http404 if not)

        Sets self.child and self.user_role for use in view methods.

        Args:
            request: HTTP request object
            *args: Positional URL kwargs
            **kwargs: Keyword URL kwargs (includes child_pk or pk)

        Returns:
            HttpResponse: View response or Http404/redirect if access denied

        Raises:
            Http404: If child doesn't exist or user lacks permission
        """
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        self.child = self.get_child_for_access_check()
        if not self.child.has_access(request.user):
            # Use 404 to not reveal child existence (security through obscurity)
            raise Http404()

        self.user_role = self.child.get_user_role(request.user)

        # Check additional permissions before calling view method
        if not self.check_child_permission(request):
            raise Http404()

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Add child and user_role to template context.

        Args:
            **kwargs: Context dict from superclass

        Returns:
            dict: Updated context with 'child' and 'user_role' keys
        """
        context = super().get_context_data(**kwargs)
        if hasattr(self, "child"):
            context["child"] = self.child
        if hasattr(self, "user_role"):
            context["user_role"] = self.user_role
        return context


class ChildEditMixin(ChildAccessMixin):
    """Mixin for views requiring edit permission (owner or co-parent).

    Restricts view access to users with edit permissions:
    - Owner (parent field): Can edit everything
    - Co-parent (ChildShare.CO_PARENT): Can edit tracking records
    - Caregiver (ChildShare.CAREGIVER): DENIED - returns Http404

    Use for views like ChildUpdateView, TrackingUpdateView, etc.

    Example:
        class ChildUpdateView(ChildEditMixin, UpdateView):
            model = Child
            form_class = ChildForm
    """

    def check_child_permission(self, request):
        """Check if user can edit this child's data.

        Args:
            request: HTTP request object

        Returns:
            bool: True if user can edit (owner or co-parent), False if caregiver
        """
        return self.child.can_edit(request.user)


class ChildOwnerMixin(ChildAccessMixin):
    """Mixin for views requiring owner permission (sharing management, delete).

    Restricts view access to the child's owner only:
    - Owner (parent field): ALLOWED
    - Co-parent (ChildShare.CO_PARENT): DENIED - returns Http404
    - Caregiver (ChildShare.CAREGIVER): DENIED - returns Http404

    Use for sensitive operations like sharing management, child deletion, invite creation.

    Example:
        class ChildSharingView(ChildOwnerMixin, DetailView):
            model = Child
            template_name = 'child_sharing.html'
    """

    def check_child_permission(self, request):
        """Check if user is the owner of this child.

        Args:
            request: HTTP request object

        Returns:
            bool: True if user is the child's parent/owner, False otherwise
        """
        return self.child.can_manage_sharing(request.user)
