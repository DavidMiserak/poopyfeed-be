from django.contrib import admin

from .models import Notification, NotificationPreference, QuietHours


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["recipient", "event_type", "message", "is_read", "created_at"]
    list_filter = ["event_type", "is_read", "created_at"]
    search_fields = ["recipient__email", "message"]
    readonly_fields = ["created_at"]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ["user", "child", "notify_feedings", "notify_diapers", "notify_naps"]
    list_filter = ["notify_feedings", "notify_diapers", "notify_naps"]


@admin.register(QuietHours)
class QuietHoursAdmin(admin.ModelAdmin):
    list_display = ["user", "enabled", "start_time", "end_time"]
    list_filter = ["enabled"]
