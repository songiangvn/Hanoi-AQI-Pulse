"""History page — quality-controlled trends, anomaly overlays, and category mix."""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from shiny import module, reactive, render, ui

from src.anomaly import metric_col_for_mode, quality_summary
from src.utils import AQI_BANDS, aqi_category, aqi_color, sanitize_figure


def _dark_fig(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height,
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, system-ui, sans-serif", "color": "#e8eaed"},
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(54,59,68,0.6)", zeroline=False, color="#9aa0a6")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(54,59,68,0.6)", zeroline=False, color="#9aa0a6")
    return sanitize_figure(fig)


def _blank(msg: str = "No data available") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, showarrow=False, font={"size": 14, "color": "#6b7280"})
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _dark_fig(fig)


def _plotly_html(fig: go.Figure) -> ui.HTML:
    return ui.HTML(
        fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            config={"displayModeBar": False, "responsive": True},
        )
    )


POLLUTANT_MAP = {"AQI": "aqi", "PM2.5": "pm25", "PM10": "pm10"}
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_CHOICES = {str(i): name for i, name in enumerate(MONTH_NAMES, start=1)}
YEAR_COLORS = {2022: "#7fa8ff", 2023: "#6f83aa", 2024: "#294275", 2025: "#4b9ddb", 2026: "#f6d433"}
CURRENT_YEAR_COLOR = "#f6d433"
CATEGORY_ORDER = ["Good", "Moderate", "USG", "Unhealthy", "Very Unhealthy", "Hazardous"]
CATEGORY_COLORS = {
    "Good": "#4cc51a",
    "Moderate": "#f5cf2f",
    "USG": "#f28f3b",
    "Unhealthy": "#e84d78",
    "Very Unhealthy": "#b83cc4",
    "Hazardous": "#d71f35",
}


# ── UI ──────────────────────────────────────────────────────────────────────────

@module.ui
def history_ui():
    return ui.TagList(
        ui.div(
            ui.h3("Historical Trends & Data Quality"),
            ui.div("Hanoi, Vietnam", class_="page-intro-sub"),
            ui.p("Explore quality-controlled daily patterns, seasonal shifts, and flagged anomaly periods."),
            class_="page-intro",
        ),
        # Pollutant pills + year selector
        ui.div(
            ui.input_radio_buttons("pollutant", "Metric", choices=list(POLLUTANT_MAP.keys()), selected="AQI", inline=True),
            ui.input_select("cal_year", "Calendar Year", choices=[str(y) for y in range(2025, 2021, -1)], selected="2024", width="140px"),
            ui.input_checkbox("show_anomalies", "Overlay anomaly markers", value=False),
            class_="control-bar",
        ),
        ui.div(ui.output_ui("quality_insight"), role="status", **{"aria-live": "polite"}),
        # Calendar heatmap
        ui.div(
            ui.h4(ui.output_text("cal_title")),
            ui.div(
                ui.output_ui("calendar_heatmap"),
                class_="accessible-chart",
                role="figure",
                **{"aria-label": "Calendar heatmap showing daily quality-controlled pollution levels and optional anomaly markers."},
            ),
            ui.div(
                ui.output_ui("cal_monthly_averages"),
                class_="accessible-chart",
                role="figure",
                **{"aria-label": "Monthly average bar chart for the selected metric and year."},
            ),
            class_="panel",
        ),
        # Multi-year month overlay
        ui.div(
            ui.div(
                ui.div(
                    ui.h4(ui.output_text("monthly_title")),
                    ui.input_select(
                        "season_month",
                        "Month",
                        choices=MONTH_CHOICES,
                        selected=str(pd.Timestamp.now().month),
                        width="110px",
                    ),
                    class_="panel-title-row",
                ),
                ui.div(
                    ui.output_ui("monthly_overlay"),
                    class_="accessible-chart",
                    role="figure",
                    **{"aria-label": "Multi-year monthly trend chart for the selected pollution metric."},
                ),
                ui.output_ui("monthly_insight"),
                class_="panel",
            ),
            ui.div(
                ui.h4("Peak & Low Days"),
                ui.output_ui("trends_highlights"),
                ui.h4("Yearly Average", style="margin-top:16px;"),
                ui.output_ui("annual_summary"),
                class_="panel",
            ),
            class_="grid-2",
        ),
        # Category matrix
        ui.div(
            ui.div(
                ui.h4("Air Quality Category Mix"),
                ui.input_select("category_year", "Year", choices=[str(y) for y in range(2025, 2021, -1)], selected="2025", width="120px"),
                class_="panel-title-row category-mix-title-row",
            ),
            ui.div(
                ui.div(
                    ui.h4(ui.output_text("category_donut_title"), style="margin-bottom:2px;"),
                    ui.div("Hanoi, Vietnam", class_="page-intro-sub"),
                    ui.div(
                        ui.output_ui("category_donut"),
                        class_="accessible-chart",
                        role="figure",
                        **{"aria-label": "Donut chart showing the share of days in each air quality category."},
                    ),
                    class_="category-donut-card",
                ),
                ui.output_ui("category_days_summary"),
                class_="category-days-grid",
            ),
            ui.h4("Monthly Category Distribution", style="margin-top:18px;"),
            ui.div(
                ui.output_ui("category_matrix_ui"),
                class_="accessible-chart",
                role="figure",
                **{"aria-label": "Matrix showing monthly distribution of air quality categories."},
            ),
            ui.output_ui("category_insight"),
            class_="panel",
        ),
    )


# ── Server ──────────────────────────────────────────────────────────────────────

@module.server
def history_server(
    input, output, session,
    *,
    city_hourly: pd.DataFrame,
):
    @reactive.calc
    def metric_col():
        raw_col = POLLUTANT_MAP[input.pollutant()]
        return metric_col_for_mode(city_hourly, raw_col, "cleaned")

    @reactive.calc
    def raw_metric_col():
        return POLLUTANT_MAP[input.pollutant()]

    @reactive.calc
    def daily_data():
        col = metric_col()
        raw_col = raw_metric_col()
        df = city_hourly.copy()
        if col not in df.columns:
            return pd.DataFrame()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        agg_spec = {"value": (col, "mean")}
        anomaly_col = f"{raw_col}_is_anomaly"
        sensor_col = f"{raw_col}_is_sensor_like"
        if anomaly_col in df.columns:
            agg_spec["anomaly_count"] = (anomaly_col, "sum")
        if sensor_col in df.columns:
            agg_spec["sensor_like_count"] = (sensor_col, "sum")
        if "is_extreme_episode" in df.columns:
            agg_spec["episode_count"] = ("is_extreme_episode", "sum")
        daily = df.set_index("local_time").resample("D").agg(**agg_spec).dropna(subset=["value"]).reset_index()
        daily = daily.rename(columns={"local_time": "date"})
        for count_col in ["anomaly_count", "sensor_like_count", "episode_count"]:
            if count_col not in daily.columns:
                daily[count_col] = 0
        daily["year"] = daily["date"].dt.year
        daily["month"] = daily["date"].dt.month
        daily["day"] = daily["date"].dt.day
        daily["dow"] = daily["date"].dt.dayofweek  # 0=Mon
        daily["week"] = daily["date"].dt.isocalendar().week.astype(int)
        return daily

    @reactive.calc
    def selected_season_month() -> int:
        try:
            month = int(input.season_month())
        except (TypeError, ValueError):
            month = pd.Timestamp.now().month
        return month if 1 <= month <= 12 else pd.Timestamp.now().month

    @output
    @render.ui
    def quality_insight():
        summary = quality_summary(city_hourly)
        if summary.rows == 0:
            return ui.div()
        pct = summary.anomaly_rows / summary.rows * 100
        sensor_pct = summary.sensor_like_rows / summary.rows * 100
        episode_pct = summary.episode_rows / summary.rows * 100
        return ui.div(
            ui.div("QUALITY-CONTROLLED SERIES", class_="insight-label"),
            ui.p(ui.HTML(
                "History charts use the quality-controlled series: isolated sensor-like spikes are smoothed, "
                "while likely real pollution episodes remain visible. The city-level dataset contains "
                f"<span class='insight-highlight'>{summary.anomaly_rows:,}</span> flagged rows "
                f"(<span class='insight-highlight'>{pct:.1f}%</span>): "
                f"<span class='insight-soft'>{summary.sensor_like_rows:,}</span> sensor-like rows "
                f"(<span class='insight-soft'>{sensor_pct:.1f}%</span>) and "
                f"<span class='insight-risk'>{summary.episode_rows:,}</span> multi-pollutant episode rows "
                f"(<span class='insight-risk'>{episode_pct:.1f}%</span>)."
            )),
            class_="insight-box",
        )

    # ── Calendar Heatmap ────────────────────────────────────────────────────

    @output
    @render.text
    def cal_title():
        return f"Daily {input.pollutant()} Calendar — {input.cal_year()}"

    @output
    @render.ui
    def calendar_heatmap():
        df = daily_data()
        year = int(input.cal_year())
        yr = df[df["year"] == year].copy()
        if yr.empty:
            return _plotly_html(_blank(f"No data for {year}"))

        # GitHub-style: x=week_of_year, y=day_of_week (Mon=0, Sun=6)
        yr["week_in_year"] = (yr["date"] - pd.Timestamp(f"{year}-01-01")).dt.days // 7
        dow_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        # Create matrix: 7 rows (dow) × 53 columns (weeks)
        max_week = yr["week_in_year"].max() + 1
        matrix = np.full((7, max_week), np.nan)
        text_matrix = [["" for _ in range(max_week)] for _ in range(7)]
        for _, row in yr.iterrows():
            matrix[row["dow"]][row["week_in_year"]] = row["value"]
            anomaly_note = ""
            if row.get("anomaly_count", 0) > 0:
                anomaly_note = f"<br>Flagged hours: {int(row.get('anomaly_count', 0))}"
            text_matrix[row["dow"]][row["week_in_year"]] = f"{row['date'].strftime('%b %d')}: {row['value']:.0f}{anomaly_note}"

        # Month labels on x-axis
        month_ticks = []
        month_labels = []
        for m in range(1, 13):
            first_day = pd.Timestamp(f"{year}-{m:02d}-01")
            if first_day.year == year:
                week_pos = (first_day - pd.Timestamp(f"{year}-01-01")).days // 7
                month_ticks.append(week_pos)
                month_labels.append(MONTH_NAMES[m - 1])

        fig = go.Figure(data=go.Heatmap(
            z=[[None if pd.isna(v) else float(v) for v in row] for row in matrix],
            x=list(range(max_week)),
            y=dow_labels,
            text=text_matrix,
            hovertemplate="%{text}<extra></extra>",
            colorscale=[
                [0.0, "#2bb673"], [0.2, "#f5b700"], [0.4, "#f28f3b"],
                [0.6, "#d1495b"], [0.8, "#7b2cbf"], [1.0, "#5a189a"],
            ],
            zmin=0, zmax=200,
            colorbar={"title": input.pollutant(), "thickness": 10, "len": 0.8},
            xgap=2, ygap=2,
        ))
        fig.update_xaxes(tickvals=month_ticks, ticktext=month_labels, side="top")
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(yaxis_title="")
        return _plotly_html(_dark_fig(fig, height=220))

    @output
    @render.ui
    def cal_monthly_averages():
        df = daily_data()
        year = int(input.cal_year())
        yr = df[df["year"] == year]
        if yr.empty:
            return ui.div()
        monthly = yr.groupby("month")["value"].mean()
        badges = []
        for m in range(1, 13):
            val = monthly.get(m, np.nan)
            if not pd.isna(val):
                badges.append(ui.tags.span(f"{val:.0f}", style=f"background:{aqi_color(val)};color:#fff;padding:3px 8px;border-radius:4px;font-weight:700;font-size:0.8rem;margin:2px 4px;"))
            else:
                badges.append(ui.tags.span("—", style="color:#6b7280;margin:2px 4px;"))
        return ui.div(
            *[ui.div(ui.tags.span(MONTH_NAMES[i], style="color:#6b7280;font-size:0.7rem;display:block;"), badges[i], style="display:inline-block;text-align:center;min-width:50px;") for i in range(12)],
            style="display:flex;flex-wrap:wrap;gap:2px;margin-top:8px;",
        )

    # ── Multi-year Month Overlay ────────────────────────────────────────────

    @output
    @render.text
    def monthly_title():
        month = selected_season_month()
        return f"{MONTH_NAMES[month - 1]} Seasonal Comparison"

    @output
    @render.ui
    def monthly_overlay():
        df = daily_data()
        if df.empty:
            return _plotly_html(_blank())
        month = selected_season_month()
        month_data = df[df["month"] == month].copy()
        if month_data.empty:
            return _plotly_html(_blank())

        fig = go.Figure()
        years = sorted(month_data["year"].unique())
        for yr in years:
            yr_data = month_data[month_data["year"] == yr].sort_values("day")
            is_current = bool(yr == years[-1])
            color = CURRENT_YEAR_COLOR if is_current else YEAR_COLORS.get(yr, "#6f83aa")
            fig.add_trace(go.Scatter(
                x=list(yr_data["day"]),
                y=list(yr_data["value"]),
                mode="lines+markers" if is_current else "lines",
                name=str(yr),
                line={"color": color, "width": 3 if is_current else 1.7, "shape": "spline", "smoothing": 1.2},
                marker={"size": 7, "color": color, "line": {"width": 0}} if is_current else None,
                fill="tozeroy" if is_current else None,
                fillcolor="rgba(246,211,51,0.22)" if is_current else None,
                opacity=1.0 if is_current else 0.68,
            ))
            if input.show_anomalies() and "anomaly_count" in yr_data.columns:
                flagged = yr_data[yr_data["anomaly_count"] > 0]
                if not flagged.empty:
                    fig.add_trace(go.Scatter(
                        x=list(flagged["day"]),
                        y=list(flagged["value"]),
                        mode="markers",
                        name=f"{yr} flagged",
                        marker={"symbol": "x", "size": 9 if is_current else 7, "color": "#ff5c7a", "line": {"width": 1}},
                        hovertemplate="Flagged day %{x}<br>Value %{y:.0f}<extra></extra>",
                        showlegend=is_current,
                    ))
        fig.update_xaxes(title="Day of Month", dtick=2)
        fig.update_yaxes(title=input.pollutant())
        fig.update_layout(
            hovermode="x unified",
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "font": {"color": "#9aa0a6"}},
        )
        return _plotly_html(_dark_fig(fig, height=380))

    @output
    @render.ui
    def monthly_insight():
        df = daily_data()
        if df.empty:
            return ui.div()
        now = pd.Timestamp.now()
        month = selected_season_month()
        month_data = df[df["month"] == month]
        if month_data.empty:
            return ui.div()

        # Same day analysis
        if month == now.month:
            comparison_day = min(now.day, int(month_data["day"].max()))
        else:
            latest_year = int(month_data["year"].max())
            latest_month_data = month_data[month_data["year"] == latest_year]
            comparison_day = int(latest_month_data["day"].max()) if not latest_month_data.empty else int(month_data["day"].max())
        same_day = month_data[month_data["day"] == comparison_day]
        if len(same_day) > 1:
            parts = []
            for _, r in same_day.sort_values("year").iterrows():
                color_class = "insight-highlight" if int(r["year"]) == int(same_day["year"].max()) else "insight-soft"
                parts.append(f"{int(r['year'])}: <span class='{color_class}'>{r['value']:.0f}</span>")
            text = f"Same Day Analysis ({comparison_day}{_ordinal(comparison_day)} {MONTH_NAMES[month-1]}): " + ", ".join(parts) + "."
        else:
            text = ""

        return ui.div(
            ui.div("WHAT THIS SHOWS", class_="insight-label"),
            ui.p(ui.HTML(
                f"Comparing <span class='insight-highlight'>{MONTH_NAMES[month-1]}</span> "
                f"<span class='insight-highlight'>{input.pollutant()}</span> across years reveals seasonal patterns. "
                f"The filled area shows the most recent year. {text}"
            )),
            class_="insight-box",
        )

    @output
    @render.ui
    def trends_highlights():
        df = daily_data()
        if df.empty:
            return ui.div("No data", style="color:#6b7280;")
        max_row = df.loc[df["value"].idxmax()]
        min_row = df.loc[df["value"].idxmin()]
        return ui.div(
            ui.div(
                ui.div(
                    ui.tags.span("Highest", class_="hl-label", style="color:#d1495b;"),
                    ui.div(f"{max_row['date'].strftime('%d %b %Y')}", class_="hl-detail"),
                    style="flex:1;",
                ),
                ui.tags.span(f"{max_row['value']:.0f}", style=f"background:#d1495b;color:#fff;padding:6px 14px;border-radius:6px;font-weight:900;font-size:1.1rem;"),
                class_="highlight-card",
            ),
            ui.div(
                ui.div(
                    ui.tags.span("Lowest", class_="hl-label", style="color:#2bb673;"),
                    ui.div(f"{min_row['date'].strftime('%d %b %Y')}", class_="hl-detail"),
                    style="flex:1;",
                ),
                ui.tags.span(f"{min_row['value']:.0f}", style=f"background:#2bb673;color:#fff;padding:6px 14px;border-radius:6px;font-weight:900;font-size:1.1rem;"),
                class_="highlight-card",
            ),
            style="display:flex;flex-direction:column;gap:10px;",
        )

    @output
    @render.ui
    def annual_summary():
        df = daily_data()
        if df.empty:
            return ui.div()
        yearly = df.groupby("year")["value"].mean().sort_index()
        rows = []
        prev = None
        for yr, avg in yearly.items():
            if prev is not None:
                pct = (avg - prev) / prev * 100
                arrow = "↑" if pct > 0 else "↓"
                change_color = "#d1495b" if pct > 0 else "#2bb673"
                change_text = f'<span style="color:{change_color};font-weight:700;">{arrow} {abs(pct):.0f}%</span>'
            else:
                change_text = ""
            color = aqi_color(avg)
            rows.append(
                f'<div style="display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid #363b44;">'
                f'<span style="color:#9aa0a6;min-width:40px;">{yr}</span>'
                f'<span style="background:{color};color:#fff;padding:3px 10px;border-radius:4px;font-weight:700;min-width:40px;text-align:center;">{avg:.0f}</span>'
                f'<span style="flex:1;text-align:right;">{change_text}</span></div>'
            )
            prev = avg
        return ui.HTML("".join(rows))

    # ── Category Matrix (No. of Days) ──────────────────────────────────────

    @reactive.effect
    def _sync_category_year_choices():
        df = daily_data()
        if df.empty:
            return
        choices = [str(int(y)) for y in sorted(df["year"].dropna().unique(), reverse=True)]
        if not choices:
            return
        with reactive.isolate():
            current = input.category_year()
        selected = current if current in choices else choices[0]
        ui.update_select("category_year", choices=choices, selected=selected)

    @reactive.calc
    def selected_category_year() -> int | None:
        df = daily_data()
        if df.empty:
            return None
        years = [int(y) for y in sorted(df["year"].dropna().unique(), reverse=True)]
        if not years:
            return None
        raw = input.category_year()
        try:
            year = int(raw)
        except (TypeError, ValueError):
            return years[0]
        return year if year in years else years[0]

    @output
    @render.text
    def category_donut_title():
        df = daily_data()
        year = selected_category_year()
        if df.empty or year is None:
            return "Days vs Air Quality"
        return f"{year} Days vs Air Quality"

    @output
    @render.ui
    def category_donut():
        df = daily_data()
        year = selected_category_year()
        if df.empty or year is None:
            return _plotly_html(_blank())
        yr = df[df["year"] == year].copy()
        if yr.empty:
            return _plotly_html(_blank(f"No category data for {year}"))
        yr["category"] = yr["value"].apply(aqi_category)
        counts = yr["category"].value_counts()
        category_counts = [(cat, int(counts.get(cat, 0))) for cat in CATEGORY_ORDER]
        category_counts = [(cat, cnt) for cat, cnt in category_counts if cnt > 0]
        labels = [cat for cat, _ in category_counts]
        values = [cnt for _, cnt in category_counts]
        colors = [CATEGORY_COLORS[cat] for cat in labels]

        fig = go.Figure(go.Pie(
            labels=labels,
            values=values,
            hole=0.62,
            sort=False,
            direction="clockwise",
            marker={"colors": colors, "line": {"color": "#282c34", "width": 2}},
            textinfo="percent",
            textfont={"color": "#e8eaed", "size": 12, "family": "Inter, system-ui, sans-serif"},
            hovertemplate="%{label}<br>%{value} day(s)<br>%{percent}<extra></extra>",
        ))
        fig.add_annotation(
            text=f"<b>{year}</b>",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 20, "color": "#e8eaed"},
        )
        fig.update_layout(showlegend=False)
        return _plotly_html(_dark_fig(fig, height=270))

    @output
    @render.ui
    def category_days_summary():
        df = daily_data()
        year = selected_category_year()
        if df.empty or year is None:
            return ui.div()
        yr = df[df["year"] == year].copy()
        if yr.empty:
            return ui.div("No category data for this year.", style="color:#6b7280;")
        yr["category"] = yr["value"].apply(aqi_category)
        counts = yr["category"].value_counts()
        total_days = int(len(yr))
        good_days = int(counts.get("Good", 0))
        non_good_days = total_days - good_days
        worst_cat = None
        for cat in reversed(CATEGORY_ORDER):
            if counts.get(cat, 0) > 0:
                worst_cat = cat
                break
        worst_cat = worst_cat or "Good"
        worst_color = CATEGORY_COLORS[worst_cat]
        if year == pd.Timestamp.now().year:
            remaining = max(0, 366 if pd.Timestamp.now().is_leap_year else 365)
            remaining -= total_days
            days_line = f"last {total_days} days in {year} ({remaining} days remaining)"
        else:
            days_line = f"{total_days} observed days in {year}"

        chips = []
        for cat in CATEGORY_ORDER:
            cnt = int(counts.get(cat, 0))
            chips.append(
                ui.div(
                    ui.span(cat, class_="category-chip-label", style=f"background:{CATEGORY_COLORS[cat]};"),
                    ui.span(f"{cnt} Days", class_="category-chip-count"),
                    class_="category-chip-row",
                )
            )
        good_pct = good_days / total_days * 100 if total_days else 0
        risk_text = "Low" if worst_cat == "Good" else "Moderate" if worst_cat in ["Moderate", "USG"] else "High"

        return ui.div(
            ui.p(
                "Total number of days with different AQI categories in ",
                ui.strong(days_line),
                class_="category-summary-lead",
            ),
            ui.div(*chips, class_="category-chip-grid"),
            ui.div(
                ui.div(
                    ui.span("Under safe air limit"),
                    ui.strong(f"{good_pct:.0f}%", style=f"color:{CATEGORY_COLORS['Good']};"),
                    class_="category-stat-card",
                ),
                ui.div(
                    ui.span("Health risk level"),
                    ui.strong(risk_text, style=f"color:{worst_color};"),
                    class_="category-stat-card",
                ),
                class_="category-stat-grid",
            ),
            ui.p(
                ui.HTML(
                    f"In <b>{year}</b>, <span style='color:{CATEGORY_COLORS['Good']};font-weight:800;'>{good_pct:.0f}%</span> "
                    f"of observed days were within the Good AQI range, while "
                    f"<span style='color:{worst_color};font-weight:800;'>{non_good_days}</span> day(s) required more caution. "
                    f"The strongest observed risk category was "
                    f"<span style='color:{worst_color};font-weight:800;'>{worst_cat}</span>."
                ),
                class_="category-summary-text",
            ),
            class_="category-summary-panel",
        )

    @output
    @render.ui
    def category_matrix_ui():
        df = daily_data()
        if df.empty:
            return ui.div("No data", style="color:#6b7280;")
        df = df.copy()
        df["category"] = df["value"].apply(aqi_category)
        categories = CATEGORY_ORDER
        cat_colors = CATEGORY_COLORS

        years = sorted(df["year"].unique(), reverse=True)

        # Table header
        html = '<div class="category-matrix-scroll"><table class="category-matrix-table">'
        html += '<tr>'
        html += '<th></th>'
        for yr in years:
            yr_avg = df[df["year"] == yr]["value"].mean()
            html += f'<th><div class="matrix-year">{yr}</div><div class="matrix-year-aqi">{yr_avg:.0f} AQI</div></th>'
        html += '</tr>'

        for m in range(1, 13):
            html += f'<tr><td class="matrix-month">{MONTH_NAMES[m-1]}</td>'
            for yr in years:
                month_data = df[(df["year"] == yr) & (df["month"] == m)]
                if month_data.empty:
                    html += '<td class="matrix-empty"></td>'
                    continue
                counts = month_data["category"].value_counts()
                total = counts.sum()
                bar = '<div class="matrix-stacked-bar">'
                for cat in categories:
                    cnt = counts.get(cat, 0)
                    if cnt > 0:
                        pct = cnt / total * 100
                        tip = f"{MONTH_NAMES[m-1]} {yr} · {cat}: {cnt} day(s)"
                        label = cnt if cnt > 2 else ""
                        bar += (
                            f'<div class="matrix-segment" data-tooltip="{tip}" '
                            f'style="width:{pct}%;background:{cat_colors[cat]};">{label}</div>'
                        )
                bar += '</div>'
                html += f'<td>{bar}</td>'
            html += '</tr>'

        # Total row
        html += '<tr class="matrix-total-row"><td>Total</td>'
        for yr in years:
            yr_data = df[df["year"] == yr]
            counts = yr_data["category"].value_counts()
            total = counts.sum()
            bar = '<div class="matrix-stacked-bar">'
            for cat in categories:
                cnt = counts.get(cat, 0)
                if cnt > 0:
                    pct = cnt / total * 100
                    tip = f"{yr} total · {cat}: {cnt} day(s)"
                    bar += (
                        f'<div class="matrix-segment" data-tooltip="{tip}" '
                        f'style="width:{pct}%;background:{cat_colors[cat]};">{cnt}</div>'
                    )
            bar += '</div>'
            html += f'<td>{bar}</td>'
        html += '</tr></table></div>'

        # Legend
        legend = '<div class="category-legend">'
        for cat in categories:
            legend += f'<span><span style="background:{cat_colors[cat]};"></span>{cat}</span>'
        legend += '</div>'

        return ui.HTML(html + legend)

    @output
    @render.ui
    def category_insight():
        df = daily_data()
        year = selected_category_year()
        if df.empty or year is None:
            return ui.div()
        yr = df[df["year"] == year]
        if yr.empty:
            return ui.div()
        yr_cat = yr["value"].apply(aqi_category)
        good_pct = (yr_cat == "Good").sum() / len(yr_cat) * 100 if len(yr_cat) > 0 else 0
        return ui.div(
            ui.div("WHAT THIS SHOWS", class_="insight-label"),
            ui.p(ui.HTML(
                f"In <span class='insight-highlight'>{year}</span>, only "
                f"<span class='insight-good'>{good_pct:.0f}%</span> of days had Good air quality "
                f"(<span class='insight-good'>AQI ≤ 50</span>). Each colored segment shows the proportion "
                "of days in each AQI category per month."
            )),
            class_="insight-box",
        )


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
