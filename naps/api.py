"""REST API for naps app: Nap."""

from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.routers import DefaultRouter

from children.api_permissions import CanEditChild, HasChildAccess
from children.models import Child

from .models import Nap


class NapSerializer(serializers.ModelSerializer):
    """Nap serializer."""

    child_name = serializers.CharField(source="child.name", read_only=True)

    class Meta:
        model = Nap
        fields = [
            "id",
            "child",
            "child_name",
            "napped_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "child_name", "created_at", "updated_at"]


class NestedNapSerializer(serializers.ModelSerializer):
    """Nap serializer for nested routes (child from URL)."""

    class Meta:
        model = Nap
        fields = [
            "id",
            "napped_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class NapViewSet(viewsets.ModelViewSet):
    """ViewSet for Nap CRUD (nested under children)."""

    permission_classes = [IsAuthenticated, HasChildAccess]

    def get_serializer_class(self):
        """Use nested serializer when child is in URL."""
        if "child_pk" in self.kwargs:
            return NestedNapSerializer
        return NapSerializer

    def get_queryset(self):
        """Return naps for the child, filtered by user access."""
        child_pk = self.kwargs.get("child_pk")
        if child_pk:
            # Nested route: /children/{child_pk}/naps/
            child = Child.objects.filter(pk=child_pk).first()
            if child and child.has_access(self.request.user):
                return Nap.objects.filter(child=child)
            return Nap.objects.none()

        # Top-level route: /naps/ - return all accessible
        accessible_children = Child.for_user(self.request.user)
        return Nap.objects.filter(child__in=accessible_children)

    def get_permissions(self):
        """Apply edit permission for update/delete."""
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated(), CanEditChild()]
        return super().get_permissions()

    def perform_create(self, serializer):
        """Set child from URL parameter."""
        child_pk = self.kwargs.get("child_pk")
        if child_pk:
            child = Child.objects.get(pk=child_pk)
            if not child.has_access(self.request.user):
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied("You do not have access to this child.")
            serializer.save(child=child)
        else:
            # Top-level route: child must be in request data
            serializer.save()


# Router for top-level /naps/ endpoint
router = DefaultRouter()
router.register("naps", NapViewSet, basename="nap")
