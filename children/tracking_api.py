"""Base ViewSet for tracking apps API.

This base class consolidates common API patterns across all tracking apps
(diapers, feedings, naps). Supports both nested routes (/children/{child_pk}/tracking/)
and top-level routes (/tracking/).
"""

from django.utils.dateparse import parse_datetime

from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from django_project.throttles import TrackingCreateThrottle

from .api_permissions import CanEditChild, HasChildAccess
from .models import Child


class TrackingViewSet(viewsets.ModelViewSet):
    """Base ViewSet for tracking records (nested under children).

    Subclasses must set:
        queryset: Base queryset for the tracking model
        serializer_class: Default serializer (for top-level routes like /diapers/)
        nested_serializer_class: Serializer for nested routes (child in URL, like /children/{child_pk}/diapers/)

    Subclasses may set:
        datetime_filter_field: Name of the datetime field to filter on (e.g. 'fed_at').
            When set, the list endpoint accepts query parameters:
            - {field}__gte: Filter records on or after this ISO datetime
            - {field}__lt: Filter records before this ISO datetime

    Handles:
        - Nested routing (/children/{child_pk}/tracking/)
        - Top-level routing (/tracking/)
        - Permission switching (view vs edit based on action)
        - Child access validation
        - Child assignment during create
        - Date range filtering via query parameters

    Example:
        class DiaperChangeViewSet(TrackingViewSet):
            queryset = DiaperChange.objects.all()
            serializer_class = DiaperChangeSerializer
            nested_serializer_class = NestedDiaperChangeSerializer
            datetime_filter_field = 'changed_at'
    """

    permission_classes = [IsAuthenticated, HasChildAccess]
    nested_serializer_class = None  # Must be set by subclass
    datetime_filter_field = None  # Set by subclass to enable date filtering

    def get_throttles(self):
        """Apply stricter rate limiting for create/update operations.

        Default throttle (1000/hour) applies to list and retrieve.
        Stricter throttle (120/hour) applies to create/update to prevent mass-insertion.
        """
        throttles = super().get_throttles()
        if self.action in ["create", "update", "partial_update"]:
            throttles.append(TrackingCreateThrottle())
        return throttles

    def get_serializer_class(self):
        """Use nested serializer when child is in URL."""
        if "child_pk" in self.kwargs:
            if not self.nested_serializer_class:
                raise NotImplementedError("Subclass must set nested_serializer_class")
            return self.nested_serializer_class
        return self.serializer_class

    def get_queryset(self):
        """Return records for the child, filtered by user access and optional date range."""
        child_pk = self.kwargs.get("child_pk")
        if child_pk:
            # Nested route: /children/{child_pk}/tracking/
            child = Child.objects.filter(pk=child_pk).first()
            if child and child.has_access(self.request.user):
                # Get model class from queryset
                model = self.queryset.model
                qs = model.objects.filter(child=child).select_related("child")
                return self._apply_datetime_filters(qs)
            # Return empty queryset if no access
            model = self.queryset.model
            return model.objects.none()

        # Top-level route: /tracking/ - return all accessible
        accessible_children = Child.for_user(self.request.user)
        model = self.queryset.model
        qs = model.objects.filter(child__in=accessible_children).select_related(
            "child"
        )
        return self._apply_datetime_filters(qs)

    def _apply_datetime_filters(self, queryset):
        """Apply date range filtering if datetime_filter_field is set.

        Reads query parameters {field}__gte and {field}__lt from the request
        and applies them as ORM filters. Invalid dates are silently ignored.
        """
        field = self.datetime_filter_field
        if not field:
            return queryset

        gte_param = self.request.query_params.get(f"{field}__gte")
        lt_param = self.request.query_params.get(f"{field}__lt")

        if gte_param:
            parsed = parse_datetime(gte_param)
            if parsed:
                queryset = queryset.filter(**{f"{field}__gte": parsed})

        if lt_param:
            parsed = parse_datetime(lt_param)
            if parsed:
                queryset = queryset.filter(**{f"{field}__lt": parsed})

        return queryset

    def get_permissions(self):
        """Apply edit permission for update/delete actions."""
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), CanEditChild()]
        return super().get_permissions()

    def perform_create(self, serializer):
        """Set child from URL parameter."""
        child_pk = self.kwargs.get("child_pk")
        if child_pk:
            child = Child.objects.get(pk=child_pk)
            if not child.has_access(self.request.user):
                raise PermissionDenied("You do not have access to this child.")
            serializer.save(child=child)
        else:
            # Top-level route: child must be in request data
            serializer.save()
