from django.apps import AppConfig


class ChildrenConfig(AppConfig):
    name = "children"

    def ready(self):
        """Register signal handlers for cache invalidation."""
        from django.db.models.signals import post_save, post_delete
        from diapers.models import DiaperChange
        from feedings.models import Feeding
        from naps.models import Nap
        from .cache_utils import invalidate_child_activities_cache

        def invalidate_on_tracking_change(sender, instance, **kwargs):
            """Invalidate child activities cache when tracking records change."""
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"SIGNAL FIRED: {sender.__name__} saved/deleted - invalidating cache for child_id={instance.child_id}"
            )
            invalidate_child_activities_cache(instance.child_id)

        # Register signal handlers for all tracking models
        post_save.connect(
            invalidate_on_tracking_change,
            sender=DiaperChange,
            dispatch_uid="invalidate_diaper_cache",
        )
        post_delete.connect(
            invalidate_on_tracking_change,
            sender=DiaperChange,
            dispatch_uid="invalidate_diaper_cache_delete",
        )
        post_save.connect(
            invalidate_on_tracking_change,
            sender=Feeding,
            dispatch_uid="invalidate_feeding_cache",
        )
        post_delete.connect(
            invalidate_on_tracking_change,
            sender=Feeding,
            dispatch_uid="invalidate_feeding_cache_delete",
        )
        post_save.connect(
            invalidate_on_tracking_change,
            sender=Nap,
            dispatch_uid="invalidate_nap_cache",
        )
        post_delete.connect(
            invalidate_on_tracking_change,
            sender=Nap,
            dispatch_uid="invalidate_nap_cache_delete",
        )
