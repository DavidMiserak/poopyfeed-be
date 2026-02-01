from django.urls import path

from .views import (
    DiaperChangeCreateView,
    DiaperChangeDeleteView,
    DiaperChangeListView,
    DiaperChangeUpdateView,
)

app_name = "diapers"

urlpatterns = [
    path(
        "",
        DiaperChangeListView.as_view(),
        name="diaper_list",
    ),
    path(
        "add/",
        DiaperChangeCreateView.as_view(),
        name="diaper_add",
    ),
    path(
        "<int:pk>/edit/",
        DiaperChangeUpdateView.as_view(),
        name="diaper_edit",
    ),
    path(
        "<int:pk>/delete/",
        DiaperChangeDeleteView.as_view(),
        name="diaper_delete",
    ),
]
