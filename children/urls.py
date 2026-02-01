from django.urls import path

from .views import (
    ChildCreateView,
    ChildDeleteView,
    ChildListView,
    ChildUpdateView,
)

app_name = "children"

urlpatterns = [
    path("", ChildListView.as_view(), name="child_list"),
    path("add/", ChildCreateView.as_view(), name="child_add"),
    path("<int:pk>/edit/", ChildUpdateView.as_view(), name="child_edit"),
    path("<int:pk>/delete/", ChildDeleteView.as_view(), name="child_delete"),
]
