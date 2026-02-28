from __future__ import annotations

import secrets
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, QuerySet

if TYPE_CHECKING:
    from accounts.models import CustomUser


class ChildShare(models.Model):
    """Through model for child sharing with role-based permissions.

    Grants a user access to a child's tracking records with a specific role.
    When created or deleted, invalidates the shared user's cached accessible_children.

    Attributes:
        child (ForeignKey): The child being shared
        user (ForeignKey): The user being granted access
        role (CharField): One of 'CO' (co-parent) or 'CG' (caregiver)
        created_at (DateTimeField): Timestamp when access was granted
        created_by (ForeignKey): The user who created this share (typically the owner)
    """

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
        db_index=True,
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

    def __str__(self) -> str:
        return f"{self.user.email} - {self.child.name} ({self.get_role_display()})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Invalidate shared user's cache when share is created/updated."""
        super().save(*args, **kwargs)
        # Invalidate cache for the shared user
        from .models import Child

        Child.invalidate_user_cache(self.user)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        """Invalidate shared user's cache when share is deleted."""
        user = self.user
        result = super().delete(*args, **kwargs)
        # Invalidate cache for the shared user
        from .models import Child

        Child.invalidate_user_cache(user)
        return result


class ShareInvite(models.Model):
    """Reusable invite links for child sharing.

    Allows owners to generate shareable tokens that grant access to their children.
    Anyone with the token can accept the invite and automatically create a ChildShare.
    Owners can deactivate invites without deleting them.

    Attributes:
        child (ForeignKey): The child being invited to share
        token (CharField): Unique URL-safe token (auto-generated via secrets.token_urlsafe)
        role (CharField): One of 'CO' (co-parent) or 'CG' (caregiver)
        created_by (ForeignKey): The owner who created this invite
        created_at (DateTimeField): Timestamp when invite was created
        is_active (BooleanField): Whether this invite can still be used
    """

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

    def __str__(self) -> str:
        return f"Invite for {self.child.name} ({self.get_role_display()})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)


class Child(models.Model):
    """Child profile with tracking records (feedings, diapers, naps).

    Owns DiaperChange, Feeding, and Nap records. Can be shared with other users
    via ChildShare (co-parent/caregiver roles) or via ShareInvite tokens.

    Access control via:
    - `has_access(user)` - Check if user can view this child
    - `get_user_role(user)` - Get user's role (owner/co-parent/caregiver)
    - `can_edit(user)` - Check if user can edit child/tracking records
    - `can_manage_sharing(user)` - Check if user is owner (can manage shares)

    Cache invalidation:
    - `for_user(user)` queries are cached for 1 hour (accessible_children_{user_id})
    - Cache invalidates automatically when child or ChildShare objects change

    Attributes:
        parent (ForeignKey): The user who created/owns this child
        name (CharField): Child's name (max 100 chars)
        date_of_birth (DateField): ISO format date (YYYY-MM-DD)
        gender (CharField): One of 'M', 'F', 'O' (optional)
        custom_bottle_low_oz (DecimalField): Custom bottle amount (oz) for low preset (0.1-50)
        custom_bottle_mid_oz (DecimalField): Custom bottle amount (oz) for mid preset (0.1-50)
        custom_bottle_high_oz (DecimalField): Custom bottle amount (oz) for high preset (0.1-50)
        feeding_reminder_interval (PositiveSmallIntegerField): Interval (hours) for feeding reminders; null = disabled
        created_at (DateTimeField): When child was created
        updated_at (DateTimeField): When child was last modified
    """

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
    custom_bottle_low_oz = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.1")), MaxValueValidator(50)],
        help_text="Custom bottle feeding amount (oz) for low/recommended-1 button",
    )
    custom_bottle_mid_oz = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.1")), MaxValueValidator(50)],
        help_text="Custom bottle feeding amount (oz) for mid/recommended button",
    )
    custom_bottle_high_oz = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.1")), MaxValueValidator(50)],
        help_text="Custom bottle feeding amount (oz) for high/recommended+1 button",
    )
    feeding_reminder_interval = models.PositiveSmallIntegerField(
        choices=[(2, "2 hours"), (3, "3 hours"), (4, "4 hours"), (6, "6 hours")],
        null=True,
        blank=True,
        default=None,
        help_text="Interval (hours) for feeding reminders; null = disabled",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "children"
        ordering = ["-date_of_birth"]
        indexes = [
            models.Index(fields=["parent", "-date_of_birth"]),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Invalidate parent's cache when child is created/updated."""
        super().save(*args, **kwargs)
        # Invalidate cache for the parent (owner)
        Child.invalidate_user_cache(self.parent)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        """Invalidate parent's cache when child is deleted."""
        parent = self.parent
        result = super().delete(*args, **kwargs)
        # Invalidate cache for the parent (owner)
        Child.invalidate_user_cache(parent)
        return result

    @classmethod
    def for_user(cls, user: CustomUser) -> QuerySet[Child]:
        """Get all children the user has access to (owned or shared).

        Implements efficient query caching to prevent expensive multi-user lookups.
        Results include both owned children and shared children (via ChildShare).
        Cache is invalidated automatically when sharing changes.

        Args:
            user: User instance to fetch children for

        Returns:
            QuerySet: Distinct children where user is owner OR has a ChildShare

        Performance:
            - First call: Database query with cache.set() for 1 hour
            - Subsequent calls: Cache hit (O(1) lookup)
            - Cache invalidates on: Child/ChildShare create/update/delete
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
    def invalidate_user_cache(cls, user: CustomUser) -> None:
        """Invalidate the cached accessible children for a user.

        Called automatically by Child/ChildShare save() and delete() methods.
        Ensures subsequent for_user() calls fetch fresh data from database.

        Args:
            user: User whose cache should be invalidated
        """
        cache_key = f"accessible_children_{user.id}"
        cache.delete(cache_key)

    def has_access(self, user: CustomUser) -> bool:
        """Check if user has any access to this child (view or manage).

        Args:
            user: User to check access for

        Returns:
            bool: True if user is owner or has a ChildShare for this child
        """
        return self.parent == user or self.shares.filter(user=user).exists()

    def get_user_role(self, user: CustomUser) -> str | None:
        """Get user's role for this child.

        Translates database role abbreviations (CO, CG) to frontend strings
        (co-parent, caregiver) for API responses.

        Args:
            user: User to get role for

        Returns:
            str: One of 'owner', 'co-parent', 'caregiver', or None if no access
        """
        if self.parent == user:
            return "owner"
        share = self.shares.filter(user=user).first()
        if share:
            # Map abbreviated roles to full strings for frontend compatibility
            role_map: dict[str, str] = {
                "CO": "co-parent",
                "CG": "caregiver",
            }
            return role_map.get(share.role)
        return None

    def can_edit(self, user: CustomUser) -> bool:
        """Check if user can edit child profile or tracking records.

        Only owners and co-parents can edit. Caregivers can only view/add.

        Args:
            user: User to check permission for

        Returns:
            bool: True if user is owner or co-parent
        """
        role = self.get_user_role(user)
        return role in ["owner", "co-parent"]

    def can_manage_sharing(self, user: CustomUser) -> bool:
        """Check if user can manage sharing (create invites, revoke access).

        Only the owner can manage sharing for a child.

        Args:
            user: User to check permission for

        Returns:
            bool: True if user is the child's owner
        """
        return self.parent == user
