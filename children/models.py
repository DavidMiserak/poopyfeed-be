from django.conf import settings
from django.db import models


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


class DiaperChange(models.Model):
    class ChangeType(models.TextChoices):
        WET = "wet", "Wet"
        DIRTY = "dirty", "Dirty"
        BOTH = "both", "Wet + Dirty"

    child = models.ForeignKey(
        Child,
        on_delete=models.CASCADE,
        related_name="diaper_changes",
    )
    change_type = models.CharField(max_length=10, choices=ChangeType.choices)
    changed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.child.name} - {self.get_change_type_display()}"
