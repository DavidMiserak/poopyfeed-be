"""API and template views for the notifications system."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import ListView
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from children.models import Child

from .cache import (
    UNREAD_COUNT_CACHE_TTL,
    invalidate_unread_count_cache,
    unread_count_cache_key,
)
from .models import DeviceToken, Notification, NotificationPreference, QuietHours
from .serializers import (
    DeviceTokenSerializer,
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
        """Return count of unread notifications (cached 60s, same as context processor)."""
        key = unread_count_cache_key(request.user.id)
        count = cache.get(key)
        if count is None:
            count = Notification.objects.filter(
                recipient=request.user, is_read=False
            ).count()
            cache.set(key, count, UNREAD_COUNT_CACHE_TTL)
        return Response({"count": count})

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        """Mark all unread notifications as read."""
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)
        invalidate_unread_count_cache(request.user.id)
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
    pagination_class = None
    http_method_names = ["get", "patch"]

    def get_queryset(self):
        return (
            NotificationPreference.objects.filter(user=self.request.user)
            .select_related("child")
            .order_by("child__name")
        )

    def list(self, request, *args, **kwargs):
        """Ensure preferences exist for all accessible children before listing."""
        accessible_child_ids = list(
            Child.for_user(request.user).values_list("id", flat=True)
        )
        existing_child_ids = set(
            NotificationPreference.objects.filter(
                user=request.user, child_id__in=accessible_child_ids
            ).values_list("child_id", flat=True)
        )
        missing = [
            NotificationPreference(user=request.user, child_id=cid)
            for cid in accessible_child_ids
            if cid not in existing_child_ids
        ]
        if missing:
            NotificationPreference.objects.bulk_create(missing, ignore_conflicts=True)
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


class DeviceTokenView(APIView):
    """Register or unregister FCM device tokens for push notifications.

    POST   /api/v1/notifications/devices/ - Register token {"token": "...", "platform": "web"|"android"}
    DELETE /api/v1/notifications/devices/ - Unregister token {"token": "..."}
    """

    permission_classes = [IsAuthenticated]

    MAX_TOKENS_PER_USER = 10

    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]
        platform = serializer.validated_data["platform"]

        # Enforce per-user device limit (only count new registrations)
        if not DeviceToken.objects.filter(token=token).exists():
            active_count = DeviceToken.objects.filter(
                user=request.user, is_active=True
            ).count()
            if active_count >= self.MAX_TOKENS_PER_USER:
                return Response(
                    {"detail": "Maximum device limit reached."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Upsert: if token exists for another user, reassign (device handoff)
        device, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                "user": request.user,
                "platform": platform,
                "is_active": True,
            },
        )
        return Response(
            {"status": "registered"},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]

        updated = DeviceToken.objects.filter(token=token, user=request.user).update(
            is_active=False
        )

        if updated:
            return Response({"status": "unregistered"})
        return Response({"status": "not_found"}, status=status.HTTP_404_NOT_FOUND)


class NotificationsListView(LoginRequiredMixin, ListView):
    """Server-rendered notifications list for the web UI."""

    model = Notification
    template_name = "notifications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 25

    def get_queryset(self):
        return (
            Notification.objects.filter(recipient=self.request.user)
            .select_related("child", "actor")
            .order_by("-created_at")
        )


class MarkAllReadView(LoginRequiredMixin, View):
    """Mark all notifications as read for the current user and redirect back."""

    def post(self, request, *args, **kwargs):
        Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True
        )
        invalidate_unread_count_cache(request.user.id)
        return redirect("notifications:notifications_list")


class NotificationGoView(LoginRequiredMixin, View):
    """Mark a single notification as read and go to the child dashboard."""

    def post(self, request, pk, *args, **kwargs):
        notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notif.is_read = True
        notif.save(update_fields=["is_read"])
        return redirect(
            reverse("children:child_dashboard", kwargs={"pk": notif.child_id})
        )
