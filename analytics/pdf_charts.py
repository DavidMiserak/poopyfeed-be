"""Chart generation utilities for PDF exports.

Generates matplotlib charts embedded as PNG images for inclusion in PDFs.
"""

from datetime import datetime
from io import BytesIO
from typing import Any

import matplotlib
import matplotlib.pyplot as plt

# Use non-interactive backend to avoid display issues in production
matplotlib.use("Agg")

# Define consistent colors matching the brand
COLORS = {
    "feeding": "#F97316",  # Orange
    "diaper_wet": "#3B82F6",  # Blue
    "diaper_dirty": "#DC2626",  # Red
    "diaper_both": "#8B5CF6",  # Purple
    "sleep": "#10B981",  # Green
    "chart_bg": "#FFFFFF",
    "grid": "#E5E7EB",
    "text": "#374151",
}


def _format_date(date_obj: datetime) -> str:
    """Format a date object for chart labels.

    Args:
        date_obj: Date object to format

    Returns:
        Formatted date string (e.g., "Jan 15")
    """
    if isinstance(date_obj, datetime):
        date_obj = date_obj.date()
    return date_obj.strftime("%b %d")


def generate_feeding_chart(feeding_data: dict[str, Any]) -> BytesIO:
    """Generate a line chart of feeding trends.

    Args:
        feeding_data: Dict with 'daily_data' containing date and count

    Returns:
        BytesIO object with PNG chart image
    """
    daily_data = feeding_data.get("daily_data", [])

    if not daily_data:
        return _create_empty_chart("No feeding data available")

    dates = [_format_date(d["date"]) for d in daily_data]
    counts = [d["count"] for d in daily_data]

    fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
    ax.set_facecolor(COLORS["chart_bg"])
    fig.patch.set_facecolor(COLORS["chart_bg"])

    # Plot line with markers
    ax.plot(
        dates,
        counts,
        marker="o",
        linewidth=2,
        markersize=6,
        color=COLORS["feeding"],
        markerfacecolor=COLORS["feeding"],
    )

    # Styling
    ax.set_title("Feeding Trends", fontsize=14, fontweight="bold", color=COLORS["text"])
    ax.set_xlabel("Date", fontsize=11, color=COLORS["text"])
    ax.set_ylabel("Count", fontsize=11, color=COLORS["text"])
    ax.grid(True, alpha=0.3, color=COLORS["grid"])
    ax.set_axisbelow(True)

    # Rotate x labels for readability
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # Add value labels on points
    for i, (date, count) in enumerate(zip(dates, counts)):
        if i % max(1, len(dates) // 6) == 0:  # Show every ~6th label to avoid crowding
            ax.text(
                i, count + 0.1, str(int(count)), ha="center", va="bottom", fontsize=9
            )

    plt.tight_layout()

    # Save to bytes
    img_buffer = BytesIO()
    fig.savefig(
        img_buffer, format="png", bbox_inches="tight", facecolor=COLORS["chart_bg"]
    )
    img_buffer.seek(0)
    plt.close(fig)

    return img_buffer


def generate_diaper_chart(diaper_data: dict[str, Any]) -> BytesIO:
    """Generate a stacked bar chart of diaper change patterns.

    Args:
        diaper_data: Dict with 'daily_data' containing date and change type counts

    Returns:
        BytesIO object with PNG chart image
    """
    daily_data = diaper_data.get("daily_data", [])

    if not daily_data:
        return _create_empty_chart("No diaper data available")

    dates = [_format_date(d["date"]) for d in daily_data]
    wet = [d.get("wet_count") or 0 for d in daily_data]
    dirty = [d.get("dirty_count") or 0 for d in daily_data]
    both = [d.get("both_count") or 0 for d in daily_data]

    fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
    ax.set_facecolor(COLORS["chart_bg"])
    fig.patch.set_facecolor(COLORS["chart_bg"])

    # Create stacked bar chart
    x = range(len(dates))
    width = 0.6

    ax.bar(x, wet, width, label="Wet", color=COLORS["diaper_wet"], alpha=0.8)
    ax.bar(
        x,
        dirty,
        width,
        bottom=wet,
        label="Dirty",
        color=COLORS["diaper_dirty"],
        alpha=0.8,
    )

    both_bottom = [w + d for w, d in zip(wet, dirty)]
    ax.bar(
        x,
        both,
        width,
        bottom=both_bottom,
        label="Both",
        color=COLORS["diaper_both"],
        alpha=0.8,
    )

    # Styling
    ax.set_title(
        "Diaper Change Patterns", fontsize=14, fontweight="bold", color=COLORS["text"]
    )
    ax.set_xlabel("Date", fontsize=11, color=COLORS["text"])
    ax.set_ylabel("Count", fontsize=11, color=COLORS["text"])
    ax.set_xticks(x)
    ax.set_xticklabels(dates, rotation=45, ha="right")
    ax.legend(loc="upper left", fontsize=10)
    ax.grid(True, alpha=0.3, axis="y", color=COLORS["grid"])
    ax.set_axisbelow(True)

    plt.tight_layout()

    # Save to bytes
    img_buffer = BytesIO()
    fig.savefig(
        img_buffer, format="png", bbox_inches="tight", facecolor=COLORS["chart_bg"]
    )
    img_buffer.seek(0)
    plt.close(fig)

    return img_buffer


def generate_sleep_chart(sleep_data: dict[str, Any]) -> BytesIO:
    """Generate a line chart of sleep (nap) patterns.

    Args:
        sleep_data: Dict with 'daily_data' containing date and count

    Returns:
        BytesIO object with PNG chart image
    """
    daily_data = sleep_data.get("daily_data", [])

    if not daily_data:
        return _create_empty_chart("No sleep data available")

    dates = [_format_date(d["date"]) for d in daily_data]
    counts = [d["count"] for d in daily_data]

    fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
    ax.set_facecolor(COLORS["chart_bg"])
    fig.patch.set_facecolor(COLORS["chart_bg"])

    # Plot line with markers
    ax.plot(
        dates,
        counts,
        marker="o",
        linewidth=2,
        markersize=6,
        color=COLORS["sleep"],
        markerfacecolor=COLORS["sleep"],
    )

    # Styling
    ax.set_title(
        "Sleep Summary (Naps)", fontsize=14, fontweight="bold", color=COLORS["text"]
    )
    ax.set_xlabel("Date", fontsize=11, color=COLORS["text"])
    ax.set_ylabel("Count", fontsize=11, color=COLORS["text"])
    ax.grid(True, alpha=0.3, color=COLORS["grid"])
    ax.set_axisbelow(True)

    # Rotate x labels for readability
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # Add value labels on points
    for i, (date, count) in enumerate(zip(dates, counts)):
        if i % max(1, len(dates) // 6) == 0:
            ax.text(
                i, count + 0.1, str(int(count)), ha="center", va="bottom", fontsize=9
            )

    plt.tight_layout()

    # Save to bytes
    img_buffer = BytesIO()
    fig.savefig(
        img_buffer, format="png", bbox_inches="tight", facecolor=COLORS["chart_bg"]
    )
    img_buffer.seek(0)
    plt.close(fig)

    return img_buffer


def _create_empty_chart(message: str) -> BytesIO:
    """Create a placeholder chart for empty data.

    Args:
        message: Message to display

    Returns:
        BytesIO object with PNG placeholder image
    """
    fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
    ax.set_facecolor(COLORS["chart_bg"])
    fig.patch.set_facecolor(COLORS["chart_bg"])

    ax.text(
        0.5,
        0.5,
        message,
        ha="center",
        va="center",
        fontsize=12,
        color=COLORS["text"],
        transform=ax.transAxes,
    )
    ax.axis("off")

    plt.tight_layout()

    img_buffer = BytesIO()
    fig.savefig(
        img_buffer, format="png", bbox_inches="tight", facecolor=COLORS["chart_bg"]
    )
    img_buffer.seek(0)
    plt.close(fig)

    return img_buffer
