"""Serializers for the notifications API."""

from rest_framework import serializers

from .models import Notification, NotificationPreference, QuietHours


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notification list/detail responses."""

    actor_name = serializers.SerializerMethodField()
    child_name = serializers.CharField(source="child.name", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "event_type",
            "message",
            "is_read",
            "created_at",
            "actor_name",
            "child_name",
            "child_id",
        ]
        read_only_fields = fields

    def get_actor_name(self, obj):
        return obj.actor.first_name or obj.actor.email.split("@")[0]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for per-child notification preferences."""

    child_name = serializers.CharField(source="child.name", read_only=True)

    class Meta:
        model = NotificationPreference
        fields = [
            "id",
            "child_id",
            "child_name",
            "notify_feedings",
            "notify_diapers",
            "notify_naps",
        ]
        read_only_fields = ["id", "child_id", "child_name"]


class QuietHoursSerializer(serializers.ModelSerializer):
    """Serializer for global quiet hours."""

    class Meta:
        model = QuietHours
        fields = ["enabled", "start_time", "end_time"]
