from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = "notifications"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import notifications.signals  # noqa: F401
