from django.urls import path

from .views import (
    AcceptInviteView,
    ChildCreateView,
    ChildDeleteView,
    ChildListView,
    ChildSharingView,
    ChildUpdateView,
    CreateInviteView,
    DeleteInviteView,
    RevokeAccessView,
    ToggleInviteView,
)

app_name = "children"

urlpatterns = [
    path("", ChildListView.as_view(), name="child_list"),
    path("add/", ChildCreateView.as_view(), name="child_add"),
    path("<int:pk>/edit/", ChildUpdateView.as_view(), name="child_edit"),
    path("<int:pk>/delete/", ChildDeleteView.as_view(), name="child_delete"),
    # Sharing management
    path("<int:pk>/sharing/", ChildSharingView.as_view(), name="child_sharing"),
    path("<int:pk>/sharing/invite/", CreateInviteView.as_view(), name="create_invite"),
    path(
        "<int:pk>/sharing/revoke/<int:share_pk>/",
        RevokeAccessView.as_view(),
        name="revoke_access",
    ),
    path(
        "<int:pk>/sharing/invite/<int:invite_pk>/toggle/",
        ToggleInviteView.as_view(),
        name="toggle_invite",
    ),
    path(
        "<int:pk>/sharing/invite/<int:invite_pk>/delete/",
        DeleteInviteView.as_view(),
        name="delete_invite",
    ),
    # Public invite acceptance
    path(
        "accept-invite/<str:token>/", AcceptInviteView.as_view(), name="accept_invite"
    ),
]
