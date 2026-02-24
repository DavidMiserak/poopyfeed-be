"""Celery tasks for analytics operations.

Handles asynchronous export jobs (PDF generation, etc.).
"""

from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

from celery import shared_task
from django.core.files.storage import default_storage
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image as ReportLabImage
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from accounts.models import CustomUser
from children.models import Child

from .pdf_charts import (
    generate_diaper_chart,
    generate_feeding_chart,
    generate_sleep_chart,
)
from .utils import get_diaper_patterns, get_feeding_trends, get_sleep_summary


def _add_chart_to_story(story: list, chart_generator, data: dict, chart_name: str):
    """Safely add a chart to the PDF story, skipping if generation fails.

    Args:
        story: ReportLab story list to append to
        chart_generator: Function that generates chart buffer
        data: Data for the chart
        chart_name: Name of chart for error logging
    """
    try:
        chart_buffer = chart_generator(data)
        chart = ReportLabImage(chart_buffer, width=6 * inch, height=3 * inch)
        story.append(chart)
        story.append(Spacer(1, 0.2 * inch))
    except Exception as e:
        print(f"Warning: Failed to generate {chart_name} chart: {e}")
        story.append(Spacer(1, 0.2 * inch))


def _build_feeding_section(
    story: list, child_id: int, days: int, styles, custom_heading_style
) -> dict:
    """Build the feeding trends section of the PDF."""
    story.append(Paragraph(f"Feeding Trends (Last {days} Days)", custom_heading_style))
    feeding_data = get_feeding_trends(child_id, days=days)
    story.append(Spacer(1, 0.1 * inch))

    # Add chart
    _add_chart_to_story(story, generate_feeding_chart, feeding_data, "feeding")

    # Build table
    feeding_rows = [["Date", "Count", "Avg Duration", "Total oz"]]
    for day_data in feeding_data.get("daily_data", []):
        feeding_rows.append(
            [
                str(day_data.get("date", "")),
                str(day_data.get("count", 0)),
                (
                    f"{day_data.get('average_duration', 0):.1f}m"
                    if day_data.get("average_duration")
                    else "—"
                ),
                (
                    f"{day_data.get('total_oz', 0):.1f}oz"
                    if day_data.get("total_oz")
                    else "—"
                ),
            ]
        )

    if len(feeding_rows) > 1:
        feeding_table = Table(feeding_rows)
        feeding_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("FONTSIZE", (0, 1), (-1, -1), 10),
                ]
            )
        )
        story.append(feeding_table)
    story.append(Spacer(1, 0.2 * inch))

    # Add summary stats
    weekly_summary = feeding_data.get("weekly_summary", {})
    summary_text = (
        f"Average per day: {weekly_summary.get('avg_per_day', 0):.1f} feedings | "
        f"Trend: {weekly_summary.get('trend', 'unknown').capitalize()} | "
        f"Variance: {weekly_summary.get('variance', 0):.2f}"
    )
    story.append(Paragraph(summary_text, styles["Normal"]))

    return feeding_data


def _build_diaper_section(
    story: list, child_id: int, days: int, styles, custom_heading_style
) -> dict:
    """Build the diaper patterns section of the PDF."""
    story.append(
        Paragraph(f"Diaper Change Patterns (Last {days} Days)", custom_heading_style)
    )
    diaper_data = get_diaper_patterns(child_id, days=days)
    story.append(Spacer(1, 0.1 * inch))

    # Add chart
    _add_chart_to_story(story, generate_diaper_chart, diaper_data, "diaper")

    # Build table
    diaper_rows = [["Date", "Total Changes", "Wet", "Dirty", "Both"]]
    for day_data in diaper_data.get("daily_data", []):
        diaper_rows.append(
            [
                str(day_data.get("date", "")),
                str(day_data.get("count", 0)),
                str(day_data.get("wet_count") or 0),
                str(day_data.get("dirty_count") or 0),
                str(day_data.get("both_count") or 0),
            ]
        )

    if len(diaper_rows) > 1:
        diaper_table = Table(diaper_rows)
        diaper_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.lightblue),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("FONTSIZE", (0, 1), (-1, -1), 10),
                ]
            )
        )
        story.append(diaper_table)
    story.append(Spacer(1, 0.2 * inch))

    # Add breakdown summary
    breakdown = diaper_data.get("breakdown", {})
    breakdown_text = (
        f"Wet: {breakdown.get('wet', 0)} | "
        f"Dirty: {breakdown.get('dirty', 0)} | "
        f"Both: {breakdown.get('both', 0)}"
    )
    story.append(Paragraph(breakdown_text, styles["Normal"]))

    return diaper_data


def _build_sleep_section(
    story: list, child_id: int, days: int, styles, custom_heading_style
) -> dict:
    """Build the sleep summary section of the PDF."""
    story.append(Paragraph(f"Sleep Summary (Last {days} Days)", custom_heading_style))
    sleep_data = get_sleep_summary(child_id, days=days)
    story.append(Spacer(1, 0.1 * inch))

    # Add chart
    _add_chart_to_story(story, generate_sleep_chart, sleep_data, "sleep")

    # Build table
    sleep_rows = [["Date", "Naps", "Avg Duration", "Total Minutes"]]
    for day_data in sleep_data.get("daily_data", []):
        sleep_rows.append(
            [
                str(day_data.get("date", "")),
                str(day_data.get("count", 0)),
                (
                    f"{day_data.get('average_duration', 0):.0f}m"
                    if day_data.get("average_duration")
                    else "—"
                ),
                (
                    f"{day_data.get('total_minutes', 0):.0f}m"
                    if day_data.get("total_minutes")
                    else "—"
                ),
            ]
        )

    if len(sleep_rows) > 1:
        sleep_table = Table(sleep_rows)
        sleep_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.lightgreen),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("FONTSIZE", (0, 1), (-1, -1), 10),
                ]
            )
        )
        story.append(sleep_table)
    story.append(Spacer(1, 0.2 * inch))

    # Add sleep summary stats
    sleep_summary = sleep_data.get("weekly_summary", {})
    sleep_text = (
        f"Average per day: {sleep_summary.get('avg_per_day', 0):.1f} naps | "
        f"Trend: {sleep_summary.get('trend', 'unknown').capitalize()}"
    )
    story.append(Paragraph(sleep_text, styles["Normal"]))

    return sleep_data


@shared_task(bind=True, time_limit=300, track_started=True)
def generate_pdf_report(self, child_id: int, user_id: int, days: int = 30):
    """Generate a PDF report with analytics data for a child.

    Args:
        child_id: The child's ID
        user_id: The user requesting the export
        days: Number of days to include (1-90, default 30)

    Returns:
        Dict with filename, download_url, created_at, and expires_at timestamp

    Raises:
        Exception: If child not found or user lacks access
    """
    try:
        # Validate days parameter
        days = max(1, min(90, days))

        # Verify child exists and user has access
        child = Child.objects.get(id=child_id)
        user = CustomUser.objects.get(id=user_id)
        if not child.has_access(user):
            raise PermissionError("User does not have access to this child")

        # Update task status to show it's starting
        self.update_state(state="STARTED", meta={"progress": 10})

        # Generate PDF
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        story = []
        styles = getSampleStyleSheet()
        custom_title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=30,
            alignment=1,  # CENTER
        )
        custom_heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=colors.HexColor("#374151"),
            spaceAfter=12,
            spaceBefore=12,
        )

        # Title
        story.append(
            Paragraph(
                f"Analytics Report for {child.name}",
                custom_title_style,
            )
        )
        story.append(
            Paragraph(
                f"Generated on {timezone.now().strftime('%B %d, %Y at %I:%M %p')}",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 0.3 * inch))

        # Build sections
        _build_feeding_section(story, child_id, days, styles, custom_heading_style)
        story.append(PageBreak())

        _build_diaper_section(story, child_id, days, styles, custom_heading_style)
        story.append(PageBreak())

        _build_sleep_section(story, child_id, days, styles, custom_heading_style)

        # Build PDF
        self.update_state(state="STARTED", meta={"progress": 75})
        doc.build(story)

        # Save to storage
        self.update_state(state="STARTED", meta={"progress": 90})
        filename = f"analytics-{child.name.replace(' ', '_')}-{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_buffer.seek(0)
        default_storage.save(f"exports/{filename}", pdf_buffer)

        # Generate download URL using the API endpoint (no trailing slash for consistency)
        download_url = f"/api/v1/analytics/download/{filename}/"

        # Calculate timestamps
        now = timezone.now()
        expires_at = now + timedelta(hours=24)

        return {
            "filename": filename,
            "download_url": download_url,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

    except Child.DoesNotExist:
        raise ValueError(f"Child with ID {child_id} not found")
    except Exception as e:
        # Task will retry on failure
        raise
