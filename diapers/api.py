"""REST API for diapers app: DiaperChange."""

from django.utils import timezone
from rest_framework import serializers
from rest_framework.routers import DefaultRouter

from children.tracking_api import TrackingViewSet

from .models import DiaperChange


class DiaperChangeSerializer(serializers.ModelSerializer):
    """DiaperChange serializer."""

    child_name = serializers.CharField(source="child.name", read_only=True)
    change_type_display = serializers.CharField(
        source="get_change_type_display", read_only=True
    )

    class Meta:
        model = DiaperChange
        fields = [
            "id",
            "child",
            "child_name",
            "change_type",
            "change_type_display",
            "changed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "child_name",
            "change_type_display",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        """No-future validation for changed_at when the caller submits it."""
        if "changed_at" in data and data.get("changed_at") is not None:
            changed_at = data["changed_at"]
            if getattr(changed_at, "tzinfo", None) is None:
                changed_at = timezone.make_aware(
                    changed_at, timezone.get_default_timezone()
                )
            if changed_at > timezone.now():
                raise serializers.ValidationError(
                    {"changed_at": "Date/time cannot be in the future."}
                )
        return data


class NestedDiaperChangeSerializer(serializers.ModelSerializer):
    """DiaperChange serializer for nested routes (child from URL)."""

    change_type_display = serializers.CharField(
        source="get_change_type_display", read_only=True
    )

    class Meta:
        model = DiaperChange
        fields = [
            "id",
            "change_type",
            "change_type_display",
            "changed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "change_type_display", "created_at", "updated_at"]


class DiaperChangeViewSet(TrackingViewSet):
    """ViewSet for DiaperChange CRUD (nested under children)."""

    queryset = DiaperChange.objects.all()
    serializer_class = DiaperChangeSerializer
    nested_serializer_class = NestedDiaperChangeSerializer
    datetime_filter_field = "changed_at"

    def get_queryset(self):
        """Optimize queryset to fetch only needed columns."""
        base_queryset = super().get_queryset()
        # Only fetch columns used by serializers
        return base_queryset.only(
            "id", "child_id", "change_type", "changed_at", "created_at", "updated_at"
        )


# Router for top-level /diapers/ endpoint
router = DefaultRouter()
router.register("diapers", DiaperChangeViewSet, basename="diaperchange")
