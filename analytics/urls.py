"""URL routing for analytics endpoints."""

from django.urls import path

from .views import AnalyticsViewSet

urlpatterns = [
    # Trend endpoints (child_id required)
    path(
        "children/<int:pk>/feeding-trends/",
        AnalyticsViewSet.as_view({"get": "feeding_trends"}),
        name="analytics-feeding-trends",
    ),
    path(
        "children/<int:pk>/diaper-patterns/",
        AnalyticsViewSet.as_view({"get": "diaper_patterns"}),
        name="analytics-diaper-patterns",
    ),
    path(
        "children/<int:pk>/sleep-summary/",
        AnalyticsViewSet.as_view({"get": "sleep_summary"}),
        name="analytics-sleep-summary",
    ),
    # Summary endpoints (child_id required)
    path(
        "children/<int:pk>/today-summary/",
        AnalyticsViewSet.as_view({"get": "today_summary"}),
        name="analytics-today-summary",
    ),
    path(
        "children/<int:pk>/weekly-summary/",
        AnalyticsViewSet.as_view({"get": "weekly_summary"}),
        name="analytics-weekly-summary",
    ),
    # Export endpoints
    path(
        "children/<int:pk>/export-csv/",
        AnalyticsViewSet.as_view({"post": "export_csv"}),
        name="analytics-export-csv",
    ),
    path(
        "children/<int:pk>/export-pdf/",
        AnalyticsViewSet.as_view({"post": "export_pdf"}),
        name="analytics-export-pdf",
    ),
    path(
        "children/<int:pk>/export-status/<str:task_id>/",
        AnalyticsViewSet.as_view({"get": "export_status"}),
        name="analytics-export-status",
    ),
]
