from django.contrib import admin

from .models import Child, DiaperChange, Feeding, Nap


@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "date_of_birth", "gender", "created_at"]
    list_filter = ["gender", "created_at"]
    search_fields = ["name", "parent__email"]
    date_hierarchy = "date_of_birth"


@admin.register(DiaperChange)
class DiaperChangeAdmin(admin.ModelAdmin):
    list_display = ["child", "change_type", "changed_at", "created_at"]
    list_filter = ["change_type", "changed_at", "created_at"]
    search_fields = ["child__name", "child__parent__email"]
    date_hierarchy = "changed_at"


@admin.register(Nap)
class NapAdmin(admin.ModelAdmin):
    list_display = ["child", "napped_at", "created_at"]
    list_filter = ["napped_at", "created_at"]
    search_fields = ["child__name", "child__parent__email"]
    date_hierarchy = "napped_at"


@admin.register(Feeding)
class FeedingAdmin(admin.ModelAdmin):
    list_display = ["child", "feeding_type", "fed_at", "amount_oz", "duration_minutes"]
    list_filter = ["feeding_type", "fed_at", "created_at"]
    search_fields = ["child__name", "child__parent__email"]
    date_hierarchy = "fed_at"
