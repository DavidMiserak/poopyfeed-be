import secrets

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models import Q


class ChildShare(models.Model):
    """Through model for child sharing with role-based permissions."""

    class Role(models.TextChoices):
        CO_PARENT = "CO", "Co-parent"
        CAREGIVER = "CG", "Caregiver"

    child = models.ForeignKey(
        "Child",
        on_delete=models.CASCADE,
        related_name="shares",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shared_children",
    )
    role = models.CharField(
        max_length=2,
        choices=Role.choices,
        default=Role.CAREGIVER,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )

    class Meta:
        db_table = "children_childshare"
        unique_together = [["child", "user"]]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.child.name} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        """Invalidate shared user's cache when share is created/updated."""
        super().save(*args, **kwargs)
        # Invalidate cache for the shared user
        from .models import Child
        Child.invalidate_user_cache(self.user)

    def delete(self, *args, **kwargs):
        """Invalidate shared user's cache when share is deleted."""
        user = self.user
        super().delete(*args, **kwargs)
        # Invalidate cache for the shared user
        from .models import Child
        Child.invalidate_user_cache(user)


class ShareInvite(models.Model):
    """Reusable invite links for child sharing."""

    child = models.ForeignKey(
        "Child",
        on_delete=models.CASCADE,
        related_name="invites",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    role = models.CharField(
        max_length=2,
        choices=ChildShare.Role.choices,
        default=ChildShare.Role.CAREGIVER,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "children_shareinvite"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invite for {self.child.name} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)


class Child(models.Model):
    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"
        OTHER = "O", "Other"

    parent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="children",
    )
    name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(
        max_length=1,
        choices=Gender.choices,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "children"
        ordering = ["-date_of_birth"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Invalidate parent's cache when child is created/updated."""
        super().save(*args, **kwargs)
        # Invalidate cache for the parent (owner)
        Child.invalidate_user_cache(self.parent)

    def delete(self, *args, **kwargs):
        """Invalidate parent's cache when child is deleted."""
        parent = self.parent
        super().delete(*args, **kwargs)
        # Invalidate cache for the parent (owner)
        Child.invalidate_user_cache(parent)

    @classmethod
    def for_user(cls, user):
        """Get all children the user has access to (owned or shared).

        Results are cached to avoid expensive queries for users with many shares.
        Cache is invalidated when ChildShare or Child objects are created/updated/deleted.
        """
        cache_key = f"accessible_children_{user.id}"
        cached_ids = cache.get(cache_key)

        if cached_ids is not None:
            # Return cached child IDs as a QuerySet
            return cls.objects.filter(id__in=cached_ids)

        # Query database and cache the results
        queryset = cls.objects.filter(Q(parent=user) | Q(shares__user=user)).distinct()
        child_ids = list(queryset.values_list("id", flat=True))

        # Cache for 1 hour (3600 seconds)
        cache.set(cache_key, child_ids, 3600)

        return queryset

    @classmethod
    def invalidate_user_cache(cls, user):
        """Invalidate the cached accessible children for a user."""
        cache_key = f"accessible_children_{user.id}"
        cache.delete(cache_key)

    def has_access(self, user):
        """Check if user has any access to this child."""
        return self.parent == user or self.shares.filter(user=user).exists()

    def get_user_role(self, user):
        """Get user's role: 'owner', 'co-parent', 'caregiver', or None."""
        if self.parent == user:
            return "owner"
        share = self.shares.filter(user=user).first()
        if share:
            # Map abbreviated roles to full strings for frontend compatibility
            role_map = {
                ChildShare.Role.CO_PARENT: "co-parent",
                ChildShare.Role.CAREGIVER: "caregiver",
            }
            return role_map.get(share.role)
        return None

    def can_edit(self, user):
        """Check if user can edit child or tracking records."""
        role = self.get_user_role(user)
        return role in ["owner", "co-parent"]

    def can_manage_sharing(self, user):
        """Only owner can manage sharing."""
        return self.parent == user
