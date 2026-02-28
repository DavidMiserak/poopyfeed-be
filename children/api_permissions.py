"""DRF permission classes for child access control.

These wrap the existing model permission methods to provide consistent
authorization across both web UI and API.
"""

from typing import Any

from rest_framework.permissions import BasePermission

from .models import Child


class HasChildAccess(BasePermission):
    """Permission: user has any access to child (view or add records).

    Wraps child.has_access(user) for DRF.
    Used for: list, retrieve, create tracking records.
    """

    message = "You do not have access to this child."

    def has_permission(self, request: Any, view: Any) -> bool:
        """Check permission for list/create actions.

        For list: queryset filters ensure only accessible children are returned.
        For create: any authenticated user can create a child (becomes owner).
        Specific child access checks are handled in has_object_permission
        or in view's perform_create/get_queryset methods.
        """
        return True

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        child = self._get_child(obj)
        if child is None:
            return False
        return child.has_access(request.user)

    def _get_child(self, obj: Any) -> Child | None:
        """Extract Child from object (handles Child and tracking records)."""
        if isinstance(obj, Child):
            return obj
        if hasattr(obj, "child"):
            return obj.child
        return None


class CanEditChild(HasChildAccess):
    """Permission: user can edit child or tracking records (owner/co-parent).

    Wraps child.can_edit(user) for DRF.
    Used for: update, delete tracking records.
    """

    message = "You do not have permission to edit this child's data."

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        child = self._get_child(obj)
        if child is None:
            return False
        return child.can_edit(request.user)


class CanManageSharing(HasChildAccess):
    """Permission: user can manage sharing (owner only).

    Wraps child.can_manage_sharing(user) for DRF.
    Used for: update/delete child, manage shares and invites.
    """

    message = "Only the owner can manage this child."

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        child = self._get_child(obj)
        if child is None:
            return False
        return child.can_manage_sharing(request.user)
