"""API views for the notifications system."""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from children.models import Child

from .models import Notification, NotificationPreference, QuietHours
from .serializers import (
    NotificationPreferenceSerializer,
    NotificationSerializer,
    QuietHoursSerializer,
)


class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for notification list, detail, mark-read operations.

    GET  /api/v1/notifications/              - List notifications (paginated)
    GET  /api/v1/notifications/unread-count/ - Get unread count
    POST /api/v1/notifications/mark-all-read/ - Mark all as read
    PATCH /api/v1/notifications/{id}/        - Mark single as read
    """

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "post"]

    def get_queryset(self):
        return (
            Notification.objects.filter(recipient=self.request.user)
            .select_related("actor", "child")
            .order_by("-created_at")
        )

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        """Return count of unread notifications."""
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return Response({"count": count})

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        """Mark all unread notifications as read."""
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)
        return Response({"updated": updated})

    def partial_update(self, request, *args, **kwargs):
        """Only allow updating is_read field."""
        instance = self.get_object()
        instance.is_read = True
        instance.save(update_fields=["is_read"])
        return Response(self.get_serializer(instance).data)

    def create(self, request, *args, **kwargs):
        """Disable direct creation via API."""
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """ViewSet for per-child notification preferences.

    GET   /api/v1/notifications/preferences/       - List all per-child prefs
    PATCH /api/v1/notifications/preferences/{id}/  - Update a preference
    """

    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch"]

    def get_queryset(self):
        return (
            NotificationPreference.objects.filter(user=self.request.user)
            .select_related("child")
            .order_by("child__name")
        )

    def list(self, request, *args, **kwargs):
        """Ensure preferences exist for all accessible children before listing."""
        accessible_children = Child.for_user(request.user)
        for child in accessible_children:
            NotificationPreference.objects.get_or_create(user=request.user, child=child)
        return super().list(request, *args, **kwargs)


class QuietHoursView(APIView):
    """View for global quiet hours configuration.

    GET   /api/v1/notifications/quiet-hours/ - Get quiet hours
    PATCH /api/v1/notifications/quiet-hours/ - Update quiet hours
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qh, _ = QuietHours.objects.get_or_create(user=request.user)
        return Response(QuietHoursSerializer(qh).data)

    def patch(self, request):
        qh, _ = QuietHours.objects.get_or_create(user=request.user)
        serializer = QuietHoursSerializer(qh, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
