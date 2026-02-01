from django.urls import path

from .views import (
    ChildCreateView,
    ChildDeleteView,
    ChildListView,
    ChildUpdateView,
    DiaperChangeCreateView,
    DiaperChangeDeleteView,
    DiaperChangeListView,
    DiaperChangeUpdateView,
)

app_name = "children"

urlpatterns = [
    path("", ChildListView.as_view(), name="child_list"),
    path("add/", ChildCreateView.as_view(), name="child_add"),
    path("<int:pk>/edit/", ChildUpdateView.as_view(), name="child_edit"),
    path("<int:pk>/delete/", ChildDeleteView.as_view(), name="child_delete"),
    path(
        "<int:child_pk>/diapers/",
        DiaperChangeListView.as_view(),
        name="diaper_list",
    ),
    path(
        "<int:child_pk>/diapers/add/",
        DiaperChangeCreateView.as_view(),
        name="diaper_add",
    ),
    path(
        "diapers/<int:pk>/edit/",
        DiaperChangeUpdateView.as_view(),
        name="diaper_edit",
    ),
    path(
        "diapers/<int:pk>/delete/",
        DiaperChangeDeleteView.as_view(),
        name="diaper_delete",
    ),
]
