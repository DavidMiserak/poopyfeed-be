"""REST API for naps app: Nap."""

from rest_framework import serializers
from rest_framework.routers import DefaultRouter

from children.tracking_api import TrackingViewSet

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


class NapViewSet(TrackingViewSet):
    """ViewSet for Nap CRUD (nested under children)."""

    queryset = Nap.objects.all()
    serializer_class = NapSerializer
    nested_serializer_class = NestedNapSerializer

    def get_queryset(self):
        """Optimize queryset to fetch only needed columns."""
        base_queryset = super().get_queryset()
        # Only fetch columns used by serializers
        return base_queryset.only("id", "child_id", "napped_at", "created_at", "updated_at")


# Router for top-level /naps/ endpoint
router = DefaultRouter()
router.register("naps", NapViewSet, basename="nap")
