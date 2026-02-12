"""API URL configuration for PoopyFeed.

All API endpoints are prefixed with /api/v1/.
"""

from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from accounts.api import (
    ChangePasswordView,
    DeleteAccountView,
    UserProfileView,
    get_auth_token,
)
from analytics.views import AnalyticsViewSet
from children.api import AcceptInviteViewSet, ChildViewSet
from diapers.api import DiaperChangeViewSet
from feedings.api import FeedingViewSet
from naps.api import NapViewSet

# Main router for top-level resources
router = DefaultRouter()
router.register("children", ChildViewSet, basename="child")
router.register("invites", AcceptInviteViewSet, basename="invite")

# Tracking ViewSets will be mounted as nested routes under children
# Using custom URL patterns for nested resources

urlpatterns = [
    # Account management
    path(
        "account/profile/",
        UserProfileView.as_view(),
        name="account-profile",
    ),
    path(
        "account/password/",
        ChangePasswordView.as_view(),
        name="account-password",
    ),
    path(
        "account/delete/",
        DeleteAccountView.as_view(),
        name="account-delete",
    ),
    # DRF browsable API login (for browser testing)
    path("api-auth/", include("rest_framework.urls")),
    # django-allauth headless API endpoints (mounted at root to avoid nested /auth/)
    path("", include("allauth.headless.urls")),
    # Get auth token for current session user
    path("browser/v1/auth/token/", get_auth_token, name="get-auth-token"),
    # Main router (children, invites)
    path("", include(router.urls)),
    # Nested tracking routes under children
    path(
        "children/<int:child_pk>/diapers/",
        DiaperChangeViewSet.as_view({"get": "list", "post": "create"}),
        name="child-diapers-list",
    ),
    path(
        "children/<int:child_pk>/diapers/<int:pk>/",
        DiaperChangeViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="child-diapers-detail",
    ),
    path(
        "children/<int:child_pk>/feedings/",
        FeedingViewSet.as_view({"get": "list", "post": "create"}),
        name="child-feedings-list",
    ),
    path(
        "children/<int:child_pk>/feedings/<int:pk>/",
        FeedingViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="child-feedings-detail",
    ),
    path(
        "children/<int:child_pk>/naps/",
        NapViewSet.as_view({"get": "list", "post": "create"}),
        name="child-naps-list",
    ),
    path(
        "children/<int:child_pk>/naps/<int:pk>/",
        NapViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="child-naps-detail",
    ),
    # Analytics endpoints (read-only)
    path(
        "analytics/children/<int:pk>/feeding-trends/",
        AnalyticsViewSet.as_view({"get": "feeding_trends"}),
        name="analytics-feeding-trends",
    ),
    path(
        "analytics/children/<int:pk>/diaper-patterns/",
        AnalyticsViewSet.as_view({"get": "diaper_patterns"}),
        name="analytics-diaper-patterns",
    ),
    path(
        "analytics/children/<int:pk>/sleep-summary/",
        AnalyticsViewSet.as_view({"get": "sleep_summary"}),
        name="analytics-sleep-summary",
    ),
    path(
        "analytics/children/<int:pk>/today-summary/",
        AnalyticsViewSet.as_view({"get": "today_summary"}),
        name="analytics-today-summary",
    ),
    path(
        "analytics/children/<int:pk>/weekly-summary/",
        AnalyticsViewSet.as_view({"get": "weekly_summary"}),
        name="analytics-weekly-summary",
    ),
    # Analytics export endpoints
    path(
        "analytics/children/<int:pk>/export-csv/",
        AnalyticsViewSet.as_view({"post": "export_csv"}),
        name="analytics-export-csv",
    ),
    path(
        "analytics/children/<int:pk>/export-pdf/",
        AnalyticsViewSet.as_view({"post": "export_pdf"}),
        name="analytics-export-pdf",
    ),
    path(
        "analytics/children/<int:pk>/export-status/<str:task_id>/",
        AnalyticsViewSet.as_view({"get": "export_status"}),
        name="analytics-export-status",
    ),
    # Analytics PDF download endpoint
    re_path(
        r"^analytics/download/(?P<filename>[^/]+)/$",
        AnalyticsViewSet.as_view({"get": "download_pdf"}),
        name="analytics-download-pdf",
    ),
]
