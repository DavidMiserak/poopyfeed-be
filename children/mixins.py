"""Permission mixins for child access control."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Child


class ChildAccessMixin(LoginRequiredMixin):
    """Base mixin for views requiring any access to child (view or add)."""

    def get_child_for_access_check(self):
        """Get the child object for permission checking."""
        child_pk = self.kwargs.get("child_pk") or self.kwargs.get("pk")
        return get_object_or_404(Child, pk=child_pk)

    def check_child_permission(self, request):
        """Override in subclasses for additional permission checks."""
        return True

    def dispatch(self, request, *args, **kwargs):
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
        context = super().get_context_data(**kwargs)
        if hasattr(self, "child"):
            context["child"] = self.child
        if hasattr(self, "user_role"):
            context["user_role"] = self.user_role
        return context


class ChildEditMixin(ChildAccessMixin):
    """Mixin for views requiring edit permission (owner or co-parent)."""

    def check_child_permission(self, request):
        """Check if user can edit this child's data."""
        return self.child.can_edit(request.user)


class ChildOwnerMixin(ChildAccessMixin):
    """Mixin for views requiring owner permission (sharing management, delete)."""

    def check_child_permission(self, request):
        """Check if user is the owner of this child."""
        return self.child.can_manage_sharing(request.user)
