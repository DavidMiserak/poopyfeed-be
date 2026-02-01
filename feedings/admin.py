from django.contrib import admin

from .models import Feeding


@admin.register(Feeding)
class FeedingAdmin(admin.ModelAdmin):
    list_display = ["child", "feeding_type", "fed_at", "amount_oz", "duration_minutes"]
    list_filter = ["feeding_type", "fed_at", "created_at"]
    search_fields = ["child__name", "child__parent__email"]
    date_hierarchy = "fed_at"
