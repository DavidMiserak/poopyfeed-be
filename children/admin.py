from django.contrib import admin

from .models import Child, ChildShare, ShareInvite


class ChildShareInline(admin.TabularInline):
    model = ChildShare
    extra = 0
    readonly_fields = ["created_at", "created_by"]
    autocomplete_fields = ["user"]


class ShareInviteInline(admin.TabularInline):
    model = ShareInvite
    extra = 0
    readonly_fields = ["token", "created_at", "created_by"]


@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "date_of_birth", "gender", "created_at"]
    list_filter = ["gender", "created_at"]
    search_fields = ["name", "parent__email"]
    date_hierarchy = "date_of_birth"
    inlines = [ChildShareInline, ShareInviteInline]


@admin.register(ChildShare)
class ChildShareAdmin(admin.ModelAdmin):
    list_display = ["child", "user", "role", "created_at", "created_by"]
    list_filter = ["role", "created_at"]
    search_fields = ["child__name", "user__email"]
    autocomplete_fields = ["child", "user", "created_by"]


@admin.register(ShareInvite)
class ShareInviteAdmin(admin.ModelAdmin):
    list_display = ["child", "role", "is_active", "created_at", "created_by"]
    list_filter = ["role", "is_active", "created_at"]
    search_fields = ["child__name", "token"]
    readonly_fields = ["token"]
