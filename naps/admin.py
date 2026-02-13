from django.contrib import admin

from .models import Nap


@admin.register(Nap)
class NapAdmin(admin.ModelAdmin):
    list_display = ["child", "napped_at", "ended_at", "created_at"]
    list_filter = ["napped_at", "ended_at", "created_at"]
    search_fields = ["child__name", "child__parent__email"]
    date_hierarchy = "napped_at"
