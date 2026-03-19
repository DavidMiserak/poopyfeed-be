"""REST API for naps app: Nap."""

from django.utils import timezone
from rest_framework import serializers
from rest_framework.routers import DefaultRouter

from children.tracking_api import TrackingViewSet

from .models import Nap


class NapSerializer(serializers.ModelSerializer):
    """Nap serializer."""

    child_name = serializers.CharField(source="child.name", read_only=True)
    duration_minutes = serializers.FloatField(read_only=True)

    class Meta:
        model = Nap
        fields = [
            "id",
            "child",
            "child_name",
            "napped_at",
            "ended_at",
            "duration_minutes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "child_name",
            "duration_minutes",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        """Validate nap datetime fields.

        - No future timestamps submitted.
        - ended_at must be after napped_at when both are provided.
        """
        now = timezone.now()

        # No-future validation only when the caller submitted the field.
        if "napped_at" in data and data.get("napped_at") is not None:
            napped_at_val = data["napped_at"]
            if getattr(napped_at_val, "tzinfo", None) is None:
                napped_at_val = timezone.make_aware(
                    napped_at_val, timezone.get_default_timezone()
                )
            if napped_at_val > now:
                raise serializers.ValidationError(
                    {"napped_at": "Date/time cannot be in the future."}
                )

        if "ended_at" in data and data.get("ended_at") is not None:
            ended_at_val = data["ended_at"]
            if getattr(ended_at_val, "tzinfo", None) is None:
                ended_at_val = timezone.make_aware(
                    ended_at_val, timezone.get_default_timezone()
                )
            if ended_at_val > now:
                raise serializers.ValidationError(
                    {"ended_at": "Date/time cannot be in the future."}
                )

        # Relationship validation: allow partial updates by falling back to instance.
        napped_at = data.get("napped_at") or (
            self.instance.napped_at if self.instance else None
        )
        ended_at = data.get("ended_at")
        if ended_at is not None and napped_at is not None and ended_at <= napped_at:
            raise serializers.ValidationError(
                {"ended_at": "End time must be after start time."}
            )
        return data


class NestedNapSerializer(NapSerializer):
    """Nap serializer for nested routes (child from URL)."""

    class Meta(NapSerializer.Meta):
        fields = [
            "id",
            "napped_at",
            "ended_at",
            "duration_minutes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "duration_minutes", "created_at", "updated_at"]


class NapViewSet(TrackingViewSet):
    """ViewSet for Nap CRUD (nested under children)."""

    queryset = Nap.objects.all()
    serializer_class = NapSerializer
    nested_serializer_class = NestedNapSerializer
    datetime_filter_field = "napped_at"

    def get_queryset(self):
        """Optimize queryset to fetch only needed columns."""
        base_queryset = super().get_queryset()
        # Only fetch columns used by serializers
        return base_queryset.only(
            "id", "child_id", "napped_at", "ended_at", "created_at", "updated_at"
        )


# Router for top-level /naps/ endpoint
router = DefaultRouter()
router.register("naps", NapViewSet, basename="nap")
