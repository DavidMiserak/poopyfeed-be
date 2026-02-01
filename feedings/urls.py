from django.urls import path

from .views import (
    FeedingCreateView,
    FeedingDeleteView,
    FeedingListView,
    FeedingUpdateView,
)

app_name = "feedings"

urlpatterns = [
    path(
        "",
        FeedingListView.as_view(),
        name="feeding_list",
    ),
    path(
        "add/",
        FeedingCreateView.as_view(),
        name="feeding_add",
    ),
    path(
        "<int:pk>/edit/",
        FeedingUpdateView.as_view(),
        name="feeding_edit",
    ),
    path(
        "<int:pk>/delete/",
        FeedingDeleteView.as_view(),
        name="feeding_delete",
    ),
]
