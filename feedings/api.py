"""REST API for feedings app: Feeding."""

from decimal import Decimal

from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.routers import DefaultRouter

from children.api_permissions import CanEditChild, HasChildAccess
from children.models import Child

from .models import Feeding


class FeedingSerializer(serializers.ModelSerializer):
    """Feeding serializer with conditional validation."""

    child_name = serializers.CharField(source="child.name", read_only=True)
    feeding_type_display = serializers.CharField(
        source="get_feeding_type_display", read_only=True
    )
    side_display = serializers.CharField(source="get_side_display", read_only=True)

    class Meta:
        model = Feeding
        fields = [
            "id",
            "child",
            "child_name",
            "feeding_type",
            "feeding_type_display",
            "fed_at",
            "amount_oz",
            "duration_minutes",
            "side",
            "side_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "child_name",
            "feeding_type_display",
            "side_display",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "amount_oz": {
                "min_value": Feeding.MIN_BOTTLE_OZ,
                "max_value": Feeding.MAX_BOTTLE_OZ,
            },
            "duration_minutes": {
                "min_value": Feeding.MIN_BREAST_MINUTES,
                "max_value": Feeding.MAX_BREAST_MINUTES,
            },
        }

    def _has_value(self, data, field_name):
        """Check if field has a value in submitted data or on the existing instance."""
        return data.get(field_name) or (
            self.instance and getattr(self.instance, field_name, None)
        )

    def validate(self, data):
        """Validate bottle vs breast fields."""
        feeding_type = self._has_value(data, "feeding_type")

        if feeding_type == Feeding.FeedingType.BOTTLE:
            if not self._has_value(data, "amount_oz"):
                raise serializers.ValidationError(
                    {"amount_oz": "Amount is required for bottle feedings."}
                )
            # Clear breast fields
            data["duration_minutes"] = None
            data["side"] = ""

        elif feeding_type == Feeding.FeedingType.BREAST:
            if not self._has_value(data, "duration_minutes"):
                raise serializers.ValidationError(
                    {"duration_minutes": "Duration is required for breast feedings."}
                )
            if not self._has_value(data, "side"):
                raise serializers.ValidationError(
                    {"side": "Side is required for breast feedings."}
                )
            # Clear bottle fields
            data["amount_oz"] = None

        return data


class NestedFeedingSerializer(FeedingSerializer):
    """Feeding serializer for nested routes (child from URL)."""

    class Meta(FeedingSerializer.Meta):
        fields = [
            "id",
            "feeding_type",
            "feeding_type_display",
            "fed_at",
            "amount_oz",
            "duration_minutes",
            "side",
            "side_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "feeding_type_display",
            "side_display",
            "created_at",
            "updated_at",
        ]


class FeedingViewSet(viewsets.ModelViewSet):
    """ViewSet for Feeding CRUD (nested under children)."""

    permission_classes = [IsAuthenticated, HasChildAccess]

    def get_serializer_class(self):
        """Use nested serializer when child is in URL."""
        if "child_pk" in self.kwargs:
            return NestedFeedingSerializer
        return FeedingSerializer

    def get_queryset(self):
        """Return feedings for the child, filtered by user access."""
        child_pk = self.kwargs.get("child_pk")
        if child_pk:
            # Nested route: /children/{child_pk}/feedings/
            child = Child.objects.filter(pk=child_pk).first()
            if child and child.has_access(self.request.user):
                return Feeding.objects.filter(child=child)
            return Feeding.objects.none()

        # Top-level route: /feedings/ - return all accessible
        accessible_children = Child.for_user(self.request.user)
        return Feeding.objects.filter(child__in=accessible_children)

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


# Router for top-level /feedings/ endpoint
router = DefaultRouter()
router.register("feedings", FeedingViewSet, basename="feeding")
