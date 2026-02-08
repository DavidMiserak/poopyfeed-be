"""REST API for diapers app: DiaperChange."""

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


# Router for top-level /diapers/ endpoint
router = DefaultRouter()
router.register("diapers", DiaperChangeViewSet, basename="diaperchange")
