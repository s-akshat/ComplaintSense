"""
analytics.py - statistics (Pandas) and charts (Matplotlib).

Pandas loads the complaints table into a DataFrame (a smart table in memory),
which makes counting and grouping easy. Matplotlib then draws PNG pictures.
"""

import io
from contextlib import closing

import matplotlib

matplotlib.use("Agg")  # draw to memory, not to a pop-up window (needed inside a web server)
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

import database  # noqa: E402
from complaints import CATEGORIES, STATUSES  # noqa: E402

LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
LEVEL_COLORS = {"CRITICAL": "#B42318", "HIGH": "#DC6803", "MEDIUM": "#B8860B", "LOW": "#067647"}
STATUS_COLORS = {"Pending": "#667085", "In Progress": "#2E6BE6", "Resolved": "#067647"}
CATEGORY_COLOR = "#4F46E5"
CHARTS = ("priority", "category", "status")


def load_dataframe():
    """Read the complaints table into a DataFrame."""
    with closing(database.get_connection()) as conn:
        return pd.read_sql_query(
            "SELECT complaint_id, category, priority_score, priority_level, "
            "needs_immediate_review, status FROM complaints",
            conn,
        )


def _counts(series, order):
    """Count each value and make sure every expected label appears (with 0 if missing)."""
    counts = series.value_counts().reindex(order, fill_value=0)
    return {label: int(counts[label]) for label in order}


def get_stats():
    """Numbers for the analytics dashboard (plain Python types, ready for JSON)."""
    df = load_dataframe()
    total = int(len(df))
    status_counts = _counts(df["status"], STATUSES)
    open_emergency = 0
    if total:
        open_emergency = int(((df["needs_immediate_review"] == 1) & (df["status"] != "Resolved")).sum())
    return {
        "total": total,
        "pending": status_counts["Pending"],
        "in_progress": status_counts["In Progress"],
        "resolved": status_counts["Resolved"],
        "open_emergency": open_emergency,
        "average_score": round(float(df["priority_score"].mean()), 2) if total else 0.0,
        "by_level": _counts(df["priority_level"], LEVELS),
        "by_category": _counts(df["category"], CATEGORIES),
        "by_status": status_counts,
    }


def _bar_chart(title, labels, values, colors, horizontal=False):
    fig, ax = plt.subplots(figsize=(6.4, 3.8), dpi=110)
    if sum(values) == 0:
        ax.text(0.5, 0.5, "No complaints yet", ha="center", va="center", fontsize=12, color="#667085")
        ax.set_axis_off()
    else:
        if horizontal:
            bars = ax.barh(labels, values, color=colors)
            ax.invert_yaxis()
            ax.set_xlabel("Number of complaints")
        else:
            bars = ax.bar(labels, values, color=colors)
            ax.set_ylabel("Number of complaints")
        ax.bar_label(bars, padding=3, fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.xaxis.get_major_locator().set_params(integer=True) if horizontal else ax.yaxis.get_major_locator().set_params(integer=True)
    ax.set_title(title, fontsize=12, fontweight="bold", loc="left")
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    plt.close(fig)  # free memory
    return buffer.getvalue()


def make_chart(kind):
    """Return a chart as PNG bytes. kind is one of CHARTS."""
    stats = get_stats()
    if kind == "priority":
        labels = LEVELS
        return _bar_chart("Complaints by priority level", labels,
                          [stats["by_level"][k] for k in labels], [LEVEL_COLORS[k] for k in labels])
    if kind == "status":
        labels = STATUSES
        return _bar_chart("Complaints by status", labels,
                          [stats["by_status"][k] for k in labels], [STATUS_COLORS[k] for k in labels])
    if kind == "category":
        labels = CATEGORIES
        return _bar_chart("Complaints by category", labels,
                          [stats["by_category"][k] for k in labels], CATEGORY_COLOR, horizontal=True)
    raise ValueError("Unknown chart")
