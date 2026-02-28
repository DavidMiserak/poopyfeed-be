"""REST API views for analytics endpoints.

Provides trend visualization and data insights for tracked activities
(feedings, diapers, naps).
"""

import csv
import os
from io import StringIO
from pathlib import Path

from celery.result import AsyncResult
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from children.models import Child

from .cache import invalidate_child_analytics
from .permissions import HasAnalyticsAccess
from .serializers import (
    AsyncExportResponseSerializer,
    DaysQuerySerializer,
    DiaperPatternsResponseSerializer,
    ExportStatusResponseSerializer,
    FeedingTrendsResponseSerializer,
    SleepSummaryResponseSerializer,
    TodaySummaryResponseSerializer,
    WeeklySummaryFullResponseSerializer,
)
from .tasks import generate_pdf_report
from .utils import (
    get_child_timeline_events,
    get_diaper_patterns,
    get_feeding_trends,
    get_sleep_summary,
    get_today_summary,
    get_weekly_summary,
)

# Celery status to frontend status mapping
CELERY_STATUS_MAP = {
    "PENDING": "pending",
    "STARTED": "processing",
    "SUCCESS": "completed",
    "FAILURE": "failed",
}

# Progress values for different task states
PROGRESS_BY_STATUS = {
    "pending": 0,
    "processing": 50,
    "completed": 100,
}


class AnalyticsViewSet(viewsets.ViewSet):
    """ViewSet for analytics endpoints.

    Provides trend analysis and summaries for tracked activities.
    All endpoints are read-only and use database-level aggregations.
    """

    permission_classes = [IsAuthenticated, HasAnalyticsAccess]

    def get_permissions(self):
        """Override permissions for download_pdf to allow unauthenticated access."""
        if self.action == "download_pdf":
            # Download URLs are time-limited, no auth required
            return []
        return super().get_permissions()

    def get_child(self, child_id: int) -> Child:
        """Get child and check access permissions.

        Args:
            child_id: The child's ID

        Returns:
            Child object if user has access

        Raises:
            NotFound: If child not found or user lacks access
        """
        try:
            # Use Child.for_user() to benefit from caching
            # This only returns children the user has access to
            child = Child.for_user(self.request.user).get(id=child_id)
            return child
        except Child.DoesNotExist:
            # Return 404 whether child doesn't exist or user lacks access
            raise NotFound("Child not found")

    def _get_cached_data(
        self,
        cache_key: str,
        compute_func,
        *args,
        cache_ttl: int = 3600,
        **kwargs,
    ) -> dict:
        """Get data from cache or compute and cache it.

        Args:
            cache_key: Cache key to use
            compute_func: Function to call if not cached
            cache_ttl: Cache time-to-live in seconds (default 1 hour)
            *args: Positional args for compute_func
            **kwargs: Keyword args for compute_func

        Returns:
            Computed or cached data dict
        """
        # Try cache first
        cached = cache.get(cache_key)
        if cached:
            return cached

        # Compute fresh data
        data = compute_func(*args, **kwargs)

        # Cache for 1 hour
        cache.set(cache_key, data, cache_ttl)

        return data

    def _map_celery_status(self, celery_status: str) -> str:
        """Map Celery task status to frontend-friendly status.

        Args:
            celery_status: Celery task status (PENDING, STARTED, SUCCESS, FAILURE)

        Returns:
            Frontend status (pending, processing, completed, failed)
        """
        return CELERY_STATUS_MAP.get(celery_status, "processing")

    def _get_progress_from_task(self, task_result, frontend_status: str) -> int:
        """Extract or compute progress value from task result.

        Args:
            task_result: AsyncResult from Celery
            frontend_status: Mapped frontend status

        Returns:
            Progress value (0-100)
        """
        try:
            if hasattr(task_result, "info") and isinstance(task_result.info, dict):
                progress = task_result.info.get("progress")
                if progress is not None:
                    return int(progress)
        except (AttributeError, ValueError, TypeError):
            pass

        # Use default progress for status
        return PROGRESS_BY_STATUS.get(frontend_status, 50)

    @action(detail=True, methods=["get"], url_path="feeding-trends")
    def feeding_trends(self, request, pk=None):
        """Get feeding trends for a child.

        Query Parameters:
            days: Number of days (1-90, default 30)

        Returns:
            Feeding trends with daily data and weekly summary
        """
        # Get and validate child
        child = self.get_child(pk)

        # Parse days parameter
        serializer = DaysQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        days = serializer.validated_data["days"]

        # Get cached or compute data
        cache_key = f"analytics:feeding-trends:{child.id}:{days}"
        data = self._get_cached_data(
            cache_key,
            get_feeding_trends,
            child.id,
            days,
        )

        # Validate response
        response_serializer = FeedingTrendsResponseSerializer(data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="diaper-patterns")
    def diaper_patterns(self, request, pk=None):
        """Get diaper change patterns for a child.

        Query Parameters:
            days: Number of days (1-90, default 30)

        Returns:
            Diaper patterns with daily data and type breakdown
        """
        # Get and validate child
        child = self.get_child(pk)

        # Parse days parameter
        serializer = DaysQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        days = serializer.validated_data["days"]

        # Get cached or compute data
        cache_key = f"analytics:diaper-patterns:{child.id}:{days}"
        data = self._get_cached_data(
            cache_key,
            get_diaper_patterns,
            child.id,
            days,
        )

        # Validate response
        response_serializer = DiaperPatternsResponseSerializer(data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="sleep-summary")
    def sleep_summary(self, request, pk=None):
        """Get sleep summary for a child.

        Query Parameters:
            days: Number of days (1-90, default 30)

        Returns:
            Sleep trends with daily data and weekly summary
        """
        # Get and validate child
        child = self.get_child(pk)

        # Parse days parameter
        serializer = DaysQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        days = serializer.validated_data["days"]

        # Get cached or compute data
        cache_key = f"analytics:sleep-summary:{child.id}:{days}"
        data = self._get_cached_data(
            cache_key,
            get_sleep_summary,
            child.id,
            days,
        )

        # Validate response
        response_serializer = SleepSummaryResponseSerializer(data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="today-summary")
    def today_summary(self, request, pk=None):
        """Get today's activity summary for a child.

        "Today" is the current calendar day in the authenticated user's timezone,
        so the summary matches what the user considers "today" (e.g. EST boundary).

        Returns:
            Today's feedings, diapers, and naps counts
        """
        # Get and validate child
        child = self.get_child(pk)

        user_tz = getattr(request.user, "timezone", None) or "UTC"

        # Get cached or compute data (cache key includes timezone)
        cache_key = f"analytics:today-summary:{child.id}:{user_tz}"
        data = self._get_cached_data(
            cache_key,
            get_today_summary,
            child.id,
            cache_ttl=300,  # 5-minute TTL for today's data
            user_timezone=user_tz,
        )

        # Validate response
        response_serializer = TodaySummaryResponseSerializer(data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="timeline")
    def timeline(self, request, pk=None):
        """Get a child's unified timeline (feedings, diapers, naps) with pagination.

        Query Parameters:
            page: Page number (default 1)
            page_size: Results per page (default 25, max 100)

        Returns:
            Paginated list of events, each with type, at (ISO datetime), and
            a type-specific payload (feeding, diaper, or nap).
        """
        from django.core.paginator import Paginator

        child = self.get_child(pk)
        events = get_child_timeline_events(child.id)

        page_size = min(max(int(request.query_params.get("page_size", 25)), 1), 100)
        paginator = Paginator(events, page_size)
        try:
            page_number = max(int(request.query_params.get("page", 1)), 1)
        except (ValueError, TypeError):
            page_number = 1
        page = paginator.get_page(page_number)

        # Build next/previous URLs
        base_url = request.build_absolute_uri(request.path)
        next_url = (
            f"{base_url}?page={page.next_page_number()}&page_size={page_size}"
            if page.has_next()
            else None
        )
        prev_url = (
            f"{base_url}?page={page.previous_page_number()}&page_size={page_size}"
            if page.has_previous()
            else None
        )

        # Serialize events for JSON (DRF Response handles datetime/Decimal)
        results = list(page.object_list)

        return Response(
            {
                "count": paginator.count,
                "next": next_url,
                "previous": prev_url,
                "results": results,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="weekly-summary")
    def weekly_summary(self, request, pk=None):
        """Get this week's activity summary for a child.

        Returns:
            Weekly feedings, diapers, and naps totals
        """
        # Get and validate child
        child = self.get_child(pk)

        # Get cached or compute data
        cache_key = f"analytics:weekly-summary:{child.id}"
        data = self._get_cached_data(
            cache_key,
            get_weekly_summary,
            child.id,
            cache_ttl=600,  # 10-minute TTL for weekly data
        )

        # Validate response
        response_serializer = WeeklySummaryFullResponseSerializer(data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="export-csv")
    def export_csv(self, request, pk=None):
        """Export analytics data as CSV file.

        Returns:
            CSV file attachment with feeding, diaper, and sleep data
        """
        # Get and validate child
        child = self.get_child(pk)

        # Parse days parameter (optional)
        serializer = DaysQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        days = serializer.validated_data["days"]

        # Get analytics data
        feeding_data = get_feeding_trends(child.id, days=days)
        diaper_data = get_diaper_patterns(child.id, days=days)
        sleep_data = get_sleep_summary(child.id, days=days)

        # Generate CSV in memory
        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer)

        # Write header
        writer.writerow(
            [
                "Date",
                "Feedings (count)",
                "Feedings (avg duration min)",
                "Feedings (total oz)",
                "Diaper Changes (count)",
                "Diaper Changes (wet)",
                "Diaper Changes (dirty)",
                "Diaper Changes (both)",
                "Naps (count)",
                "Naps (avg duration min)",
                "Naps (total minutes)",
            ]
        )

        # Create lookup dicts for diaper and sleep data
        feeding_by_date = {d["date"]: d for d in feeding_data.get("daily_data", [])}
        diaper_by_date = {d["date"]: d for d in diaper_data.get("daily_data", [])}
        sleep_by_date = {d["date"]: d for d in sleep_data.get("daily_data", [])}

        # Get all dates
        all_dates = (
            set(feeding_by_date.keys())
            | set(diaper_by_date.keys())
            | set(sleep_by_date.keys())
        )

        # Write data rows
        for date in sorted(all_dates):
            feeding = feeding_by_date.get(date, {})
            diaper = diaper_by_date.get(date, {})
            sleep = sleep_by_date.get(date, {})

            writer.writerow(
                [
                    date,
                    feeding.get("count", 0),
                    feeding.get("average_duration") or "",
                    feeding.get("total_oz") or "",
                    diaper.get("count", 0),
                    diaper.get("wet_count", 0),
                    diaper.get("dirty_count", 0),
                    diaper.get("both_count", 0),
                    sleep.get("count", 0),
                    sleep.get("average_duration") or "",
                    sleep.get("total_minutes") or "",
                ]
            )

        # Create HTTP response with CSV attachment
        response = HttpResponse(csv_buffer.getvalue(), content_type="text/csv")
        filename = f"analytics-{child.name.replace(' ', '_')}-{days}days.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=["post"], url_path="export-pdf")
    def export_pdf(self, request, pk=None):
        """Queue asynchronous PDF export job.

        Queues a Celery task to generate PDF report. Returns task ID for polling.

        Request body:
            days: Number of days to include (1-90, default 30)

        Returns:
            JSON with task_id and status for polling export progress
        """
        # Get and validate child
        child = self.get_child(pk)

        # Parse days parameter from request body
        serializer = DaysQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        days = serializer.validated_data["days"]

        # Queue PDF generation task with days parameter
        task = generate_pdf_report.delay(child.id, request.user.id, days)

        # Return task ID for polling
        response_serializer = AsyncExportResponseSerializer(
            {
                "task_id": task.id,
                "status": "pending",
                "message": f"PDF export for {child.name} queued. Use task_id to check status.",
            }
        )
        return Response(response_serializer.data, status=status.HTTP_202_ACCEPTED)

    def export_status(self, request, pk=None, task_id=None):
        """Poll the status of an async export job.

        Args:
            task_id: The Celery task ID from export-pdf response

        Returns:
            JSON with task status and result (if complete)
        """
        # Get task result
        task_result = AsyncResult(task_id)
        celery_status = task_result.status

        # Map to frontend status and build response
        frontend_status = self._map_celery_status(celery_status)
        response_data = {
            "task_id": task_id,
            "status": frontend_status,
        }

        # Extract or compute progress value
        progress = self._get_progress_from_task(task_result, frontend_status)
        response_data["progress"] = progress

        # Add result or error if available
        if task_result.successful():
            response_data["result"] = task_result.result
        elif task_result.failed():
            response_data["error"] = str(task_result.info)

        response_serializer = ExportStatusResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def download_pdf(self, request, filename=None):
        """Download a generated PDF export file.

        Args:
            filename: The filename to download (e.g., analytics-Child_Name-20240212_151408.pdf)

        Returns:
            PDF file as attachment or 404 if not found
        """
        # Validate filename format (prevent directory traversal)
        if (
            not filename
            or "/" in filename
            or "\\" in filename
            or filename.startswith(".")
        ):
            raise NotFound("Invalid filename")

        # Construct file path
        file_path = Path("exports") / filename

        # Use storage to get the full path
        try:
            full_path = default_storage.path(str(file_path))
        except NotImplementedError:
            # Fallback if storage backend doesn't implement path()
            from django.conf import settings

            full_path = os.path.join(settings.BASE_DIR, "exports", filename)

        # Check if file exists
        if not os.path.exists(full_path):
            raise NotFound("File not found")

        # Open and return file
        try:
            with open(full_path, "rb") as f:
                response = HttpResponse(f.read(), content_type="application/pdf")
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
                return response
        except IOError:
            raise NotFound("Unable to read file")
