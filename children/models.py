import secrets

from django.conf import settings
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

    @classmethod
    def for_user(cls, user):
        """Get all children the user has access to (owned or shared)."""
        return cls.objects.filter(Q(parent=user) | Q(shares__user=user)).distinct()

    def has_access(self, user):
        """Check if user has any access to this child."""
        return self.parent == user or self.shares.filter(user=user).exists()

    def get_user_role(self, user):
        """Get user's role: 'owner', 'co_parent', 'caregiver', or None."""
        if self.parent == user:
            return "owner"
        share = self.shares.filter(user=user).first()
        if share:
            return share.role.lower()
        return None

    def can_edit(self, user):
        """Check if user can edit child or tracking records."""
        role = self.get_user_role(user)
        return role in ["owner", "co"]

    def can_manage_sharing(self, user):
        """Only owner can manage sharing."""
        return self.parent == user
