"""Signal handlers for cache invalidation.

Automatically invalidates analytics caches when tracking records change.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from diapers.models import DiaperChange
from feedings.models import Feeding
from naps.models import Nap

from .cache import invalidate_child_analytics


@receiver(post_save, sender=Feeding, dispatch_uid="invalidate_feeding_analytics")
def invalidate_analytics_on_feeding_save(sender, instance, **kwargs):
    """Invalidate analytics when a feeding is created or updated."""
    invalidate_child_analytics(instance.child_id)


@receiver(
    post_delete, sender=Feeding, dispatch_uid="invalidate_feeding_analytics_delete"
)
def invalidate_analytics_on_feeding_delete(sender, instance, **kwargs):
    """Invalidate analytics when a feeding is deleted."""
    invalidate_child_analytics(instance.child_id)


@receiver(post_save, sender=DiaperChange, dispatch_uid="invalidate_diaper_analytics")
def invalidate_analytics_on_diaper_save(sender, instance, **kwargs):
    """Invalidate analytics when a diaper change is created or updated."""
    invalidate_child_analytics(instance.child_id)


@receiver(
    post_delete, sender=DiaperChange, dispatch_uid="invalidate_diaper_analytics_delete"
)
def invalidate_analytics_on_diaper_delete(sender, instance, **kwargs):
    """Invalidate analytics when a diaper change is deleted."""
    invalidate_child_analytics(instance.child_id)


@receiver(post_save, sender=Nap, dispatch_uid="invalidate_nap_analytics")
def invalidate_analytics_on_nap_save(sender, instance, **kwargs):
    """Invalidate analytics when a nap is created or updated."""
    invalidate_child_analytics(instance.child_id)


@receiver(post_delete, sender=Nap, dispatch_uid="invalidate_nap_analytics_delete")
def invalidate_analytics_on_nap_delete(sender, instance, **kwargs):
    """Invalidate analytics when a nap is deleted."""
    invalidate_child_analytics(instance.child_id)
