from django.apps import AppConfig


class NapsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "naps"

    def ready(self):
        import naps.signals  # noqa: F401
