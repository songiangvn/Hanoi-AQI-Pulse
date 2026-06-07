"""Shared AQI utilities used by the UI, server modules, and data layer."""
from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go

# ── AQI band definitions ───────────────────────────────────────────────────────
AQI_BANDS = [
    (50, "Good", "#2bb673"),
    (100, "Moderate", "#f5b700"),
    (150, "USG", "#f28f3b"),
    (200, "Unhealthy", "#d1495b"),
    (300, "Very Unhealthy", "#7b2cbf"),
]


def aqi_category(aqi: float | None) -> str:
    """Return human-readable AQI category label."""
    if aqi is None or pd.isna(aqi):
        return "Unknown"
    for threshold, label, _ in AQI_BANDS:
        if aqi <= threshold:
            return label
    return "Hazardous"


def aqi_color(aqi: float | None) -> str:
    """Return hex colour for a given AQI value."""
    if aqi is None or pd.isna(aqi):
        return "#7a8792"
    for threshold, _, color in AQI_BANDS:
        if aqi <= threshold:
            return color
    return "#5a189a"


def aqi_advisory(aqi: float | None) -> str:
    """Return a short health advisory string for the AQI level."""
    category = aqi_category(aqi)
    messages = {
        "Good": "Outdoor activity looks broadly safe.",
        "Moderate": "Sensitive groups should watch exposure during long outdoor periods.",
        "USG": "Sensitive groups should reduce prolonged outdoor exertion.",
        "Unhealthy": "Limit outdoor exercise and consider masks for long trips.",
        "Very Unhealthy": "Avoid prolonged outdoor exposure where possible.",
        "Hazardous": "Stay indoors and avoid outdoor exertion.",
    }
    return messages.get(category, "Realtime AQI unavailable; use the historical context cautiously.")


def metric_title(metric: str) -> str:
    """Pretty-print a metric column name for chart titles."""
    return metric.upper().replace("PM25", "PM2.5")


def _json_safe_value(value):
    """Convert NaN/inf/numpy/pandas scalars to strict JSON-safe values."""
    if value is None:
        return None
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, np.ndarray):
        return [_json_safe_value(v) for v in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe_value(v) for k, v in value.items()}
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    return value


def sanitize_figure(fig: go.Figure) -> go.Figure:
    """Return a Plotly figure with strict-JSON-safe data/layout.

    Plotly renderers use strict JSON paths, so NaN/inf inside traces can make
    tabs look like they never finish loading.
    """
    return go.Figure(_json_safe_value(fig.to_plotly_json()))
