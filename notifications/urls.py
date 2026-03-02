from django.urls import path

from .views import MarkAllReadView, NotificationGoView, NotificationsListView

app_name = "notifications"

urlpatterns = [
    path("", NotificationsListView.as_view(), name="notifications_list"),
    path(
        "mark-all-read/", MarkAllReadView.as_view(), name="notifications_mark_all_read"
    ),
    path("<int:pk>/go/", NotificationGoView.as_view(), name="notification_go"),
]
