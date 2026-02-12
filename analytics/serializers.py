"""Serializers for analytics endpoints.

Request validation and response formatting for all analytics queries.
"""

from rest_framework import serializers


class DaysQuerySerializer(serializers.Serializer):
    """Validate the 'days' query parameter for trend endpoints."""

    days = serializers.IntegerField(
        default=30,
        min_value=1,
        max_value=90,
        help_text="Number of days to retrieve analytics for (1-90, default 30)",
    )


class DailyDataSerializer(serializers.Serializer):
    """Single day's aggregated data."""

    date = serializers.DateField()
    count = serializers.IntegerField()
    average_duration = serializers.FloatField(allow_null=True)
    total_oz = serializers.FloatField(allow_null=True)


class WeeklySummaryDataSerializer(serializers.Serializer):
    """Weekly summary statistics."""

    avg_per_day = serializers.FloatField()
    trend = serializers.CharField()  # 'increasing', 'decreasing', 'stable'
    variance = serializers.FloatField()


class FeedingTrendsResponseSerializer(serializers.Serializer):
    """Response for feeding trends endpoint."""

    period = serializers.CharField()
    child_id = serializers.IntegerField()
    daily_data = DailyDataSerializer(many=True)
    weekly_summary = WeeklySummaryDataSerializer()
    last_updated = serializers.DateTimeField()


class DiaperPatternsResponseSerializer(serializers.Serializer):
    """Response for diaper patterns endpoint."""

    period = serializers.CharField()
    child_id = serializers.IntegerField()
    daily_data = DailyDataSerializer(many=True)
    weekly_summary = WeeklySummaryDataSerializer()
    breakdown = serializers.DictField()  # wet, dirty, both counts
    last_updated = serializers.DateTimeField()


class SleepSummaryResponseSerializer(serializers.Serializer):
    """Response for sleep summary endpoint."""

    period = serializers.CharField()
    child_id = serializers.IntegerField()
    daily_data = DailyDataSerializer(many=True)
    weekly_summary = WeeklySummaryDataSerializer()
    last_updated = serializers.DateTimeField()


class TodaySummaryResponseSerializer(serializers.Serializer):
    """Response for today's summary endpoint."""

    child_id = serializers.IntegerField()
    period = serializers.CharField()
    feedings = serializers.DictField()  # count, total_oz, bottle, breast
    diapers = serializers.DictField()  # count, wet, dirty, both
    sleep = serializers.DictField()  # naps, total_minutes, avg_duration
    last_updated = serializers.DateTimeField()


class WeeklySummaryFullResponseSerializer(serializers.Serializer):
    """Response for weekly summary endpoint."""

    child_id = serializers.IntegerField()
    period = serializers.CharField()
    feedings = serializers.DictField()
    diapers = serializers.DictField()
    sleep = serializers.DictField()
    last_updated = serializers.DateTimeField()


class ExportRequestSerializer(serializers.Serializer):
    """Request validation for export endpoints."""

    format = serializers.ChoiceField(choices=["csv", "pdf"])


class ExportResponseSerializer(serializers.Serializer):
    """Response for synchronous export endpoints."""

    success = serializers.BooleanField()
    filename = serializers.CharField()
    format = serializers.CharField()


class AsyncExportResponseSerializer(serializers.Serializer):
    """Response for async export endpoints."""

    task_id = serializers.CharField()
    status = serializers.CharField()
    message = serializers.CharField()


class ExportStatusResponseSerializer(serializers.Serializer):
    """Response for export status polling endpoint."""

    task_id = serializers.CharField()
    status = serializers.CharField()
    progress = serializers.IntegerField(required=False, allow_null=True)
    result = serializers.DictField(required=False, allow_null=True)
    error = serializers.CharField(required=False, allow_null=True)
