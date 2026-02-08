"""REST API for feedings app: Feeding."""

from decimal import Decimal

from rest_framework import serializers
from rest_framework.routers import DefaultRouter

from children.tracking_api import TrackingViewSet

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


class FeedingViewSet(TrackingViewSet):
    """ViewSet for Feeding CRUD (nested under children)."""

    queryset = Feeding.objects.all()
    serializer_class = FeedingSerializer
    nested_serializer_class = NestedFeedingSerializer


# Router for top-level /feedings/ endpoint
router = DefaultRouter()
router.register("feedings", FeedingViewSet, basename="feeding")
