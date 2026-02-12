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

from .utils import get_diaper_patterns, get_feeding_trends, get_sleep_summary


@shared_task(bind=True, time_limit=300)
def generate_pdf_report(self, child_id: int, user_id: int):
    """Generate a PDF report with analytics data for a child.

    Args:
        child_id: The child's ID
        user_id: The user requesting the export

    Returns:
        Dict with filename, url, and expiration timestamp

    Raises:
        Exception: If child not found or user lacks access
    """
    try:
        # Verify child exists and user has access
        child = Child.objects.get(id=child_id)
        user = CustomUser.objects.get(id=user_id)
        if not child.has_access(user):
            raise PermissionError("User does not have access to this child")

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

        # Feeding Trends Section
        story.append(Paragraph("Feeding Trends (Last 30 Days)", custom_heading_style))
        feeding_data = get_feeding_trends(child_id, days=30)
        story.append(Spacer(1, 0.1 * inch))

        # Build feeding table
        feeding_rows = [["Date", "Count", "Avg Duration", "Total oz"]]
        for day_data in feeding_data.get("daily_data", [])[
            :10
        ]:  # Last 10 days for brevity
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

        story.append(PageBreak())

        # Diaper Patterns Section
        story.append(
            Paragraph("Diaper Change Patterns (Last 30 Days)", custom_heading_style)
        )
        diaper_data = get_diaper_patterns(child_id, days=30)
        story.append(Spacer(1, 0.1 * inch))

        # Build diaper table
        diaper_rows = [["Date", "Total Changes", "Wet", "Dirty", "Both"]]
        breakdown = diaper_data.get("breakdown", {})
        for day_data in diaper_data.get("daily_data", [])[:10]:
            diaper_rows.append(
                [
                    str(day_data.get("date", "")),
                    str(day_data.get("count", 0)),
                    str(day_data.get("wet_count", 0)),
                    str(day_data.get("dirty_count", 0)),
                    str(day_data.get("both_count", 0)),
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
        breakdown_text = (
            f"Wet: {breakdown.get('wet', 0)} | "
            f"Dirty: {breakdown.get('dirty', 0)} | "
            f"Both: {breakdown.get('both', 0)}"
        )
        story.append(Paragraph(breakdown_text, styles["Normal"]))

        story.append(PageBreak())

        # Sleep Summary Section
        story.append(Paragraph("Sleep Summary (Last 30 Days)", custom_heading_style))
        sleep_data = get_sleep_summary(child_id, days=30)
        story.append(Spacer(1, 0.1 * inch))

        # Build sleep table
        sleep_rows = [["Date", "Naps", "Avg Duration", "Total Minutes"]]
        for day_data in sleep_data.get("daily_data", [])[:10]:
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

        # Build PDF
        doc.build(story)

        # Save to storage
        filename = f"analytics-{child.name.replace(' ', '_')}-{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_buffer.seek(0)
        default_storage.save(f"exports/{filename}", pdf_buffer)

        # Calculate expiration time (24 hours from now)
        expires_at = timezone.now() + timedelta(hours=24)

        return {
            "filename": filename,
            "url": f"/api/v1/analytics/children/{child_id}/export/download/{filename}/",
            "expires_at": expires_at.isoformat(),
            "child_id": child_id,
        }

    except Child.DoesNotExist:
        raise ValueError(f"Child with ID {child_id} not found")
    except Exception as e:
        # Task will retry on failure
        raise
