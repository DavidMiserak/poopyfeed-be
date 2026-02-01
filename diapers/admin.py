from django.contrib import admin

from .models import DiaperChange


@admin.register(DiaperChange)
class DiaperChangeAdmin(admin.ModelAdmin):
    list_display = ["child", "change_type", "changed_at", "created_at"]
    list_filter = ["change_type", "changed_at", "created_at"]
    search_fields = ["child__name", "child__parent__email"]
    date_hierarchy = "changed_at"
