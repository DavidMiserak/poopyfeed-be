from django.contrib import admin

from .models import Child


@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "date_of_birth", "gender", "created_at"]
    list_filter = ["gender", "created_at"]
    search_fields = ["name", "parent__email"]
    date_hierarchy = "date_of_birth"
