from django.urls import path

from .views import (
    NapCreateView,
    NapDeleteView,
    NapListView,
    NapUpdateView,
)

app_name = "naps"

urlpatterns = [
    path(
        "",
        NapListView.as_view(),
        name="nap_list",
    ),
    path(
        "add/",
        NapCreateView.as_view(),
        name="nap_add",
    ),
    path(
        "<int:pk>/edit/",
        NapUpdateView.as_view(),
        name="nap_edit",
    ),
    path(
        "<int:pk>/delete/",
        NapDeleteView.as_view(),
        name="nap_delete",
    ),
]
