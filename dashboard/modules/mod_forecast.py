"""Forecast page — anomaly-aware prediction, performance, and model drivers."""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from shiny import module, reactive, render, ui

from src.anomaly import metric_col_for_mode
from src.model import FEATURE_BASE, _build_features
from src.utils import aqi_advisory, aqi_category, aqi_color, sanitize_figure


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


def _driver_display_name(feature: str) -> str:
    name = str(feature).replace("_", " ").title()
    replacements = {
        "Aqi": "AQI",
        "Pm25": "PM2.5",
        "Pm10": "PM10",
        "No2": "NO2",
        "So2": "SO2",
        "Co": "CO",
        "O3": "O3",
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    parts = name.split()
    if len(parts) > 2:
        midpoint = int(np.ceil(len(parts) / 2))
        name = " ".join(parts[:midpoint]) + "<br>" + " ".join(parts[midpoint:])
    if len(name.replace("<br>", " ")) > 20 and "<br>" not in name:
        name = name[:18] + "..."
    return name


def _snapshot_overrides(snapshot: dict[str, Any] | None) -> dict[str, float]:
    if not isinstance(snapshot, dict):
        return {}
    mapping = {
        "aqi": "aqi", "pm25": "pm25", "pm10": "pm10", "co": "co",
        "no2": "no2", "o3": "o3", "so2": "so2", "temp": "temperature",
        "humidity": "relative_humidity", "pressure": "pressure",
        "wind": "wind_speed", "precipitation": "precipitation",
    }
    out: dict[str, float] = {}
    for src, dst in mapping.items():
        val = snapshot.get(src)
        if val is not None and not pd.isna(val):
            out[dst] = float(val)
    return out


def _latest_feature_row(city_hourly: pd.DataFrame, artifacts, snapshot: dict[str, Any] | None) -> pd.DataFrame:
    df = city_hourly.sort_values("local_time").copy()
    if getattr(artifacts, "data_mode", "raw") == "cleaned":
        for col in FEATURE_BASE:
            clean_col = metric_col_for_mode(df, col, "cleaned")
            if clean_col in df.columns:
                df[col] = pd.to_numeric(df[clean_col], errors="coerce")

    row = df.iloc[-1:].copy()
    now = pd.Timestamp.now()
    row["hour"] = now.hour
    row["dow"] = now.dayofweek
    row["month"] = now.month
    row["is_weekend"] = int(now.dayofweek >= 5)

    for col in ["aqi", "pm25"]:
        if col not in df.columns:
            continue
        for lag in [1, 6, 24]:
            row[f"{col}_lag_{lag}"] = df[col].shift(lag).iloc[-1]
        for window in [3, 6, 24]:
            roll = df[col].rolling(window)
            row[f"{col}_roll_mean_{window}"] = roll.mean().iloc[-1]
            row[f"{col}_roll_max_{window}"] = roll.max().iloc[-1]

    for key, value in _snapshot_overrides(snapshot).items():
        if key in row.columns:
            row[key] = value
    return row[artifacts.feature_cols].copy().ffill(axis=0).fillna(0.0)


def _mood_class(category: str) -> str:
    return {
        "Good": "mood-good",
        "Moderate": "mood-moderate",
        "USG": "mood-usg",
        "Unhealthy": "mood-unhealthy",
        "Very Unhealthy": "mood-severe",
        "Hazardous": "mood-hazardous",
    }.get(category, "mood-unknown")


def _lexce_owl(mood_class: str) -> ui.Tag:
    return ui.div(
        ui.div(class_="owl-ear owl-ear-left"),
        ui.div(class_="owl-ear owl-ear-right"),
        ui.div(class_="owl-face"),
        ui.div(ui.div(class_="owl-eye-shine"), class_="owl-eye owl-eye-left"),
        ui.div(ui.div(class_="owl-eye-shine"), class_="owl-eye owl-eye-right"),
        ui.div(class_="owl-brow owl-brow-left"),
        ui.div(class_="owl-brow owl-brow-right"),
        ui.div(class_="owl-beak"),
        ui.div(class_="owl-cheek owl-cheek-left"),
        ui.div(class_="owl-cheek owl-cheek-right"),
        ui.div(class_="owl-wing owl-wing-left"),
        ui.div(class_="owl-wing owl-wing-right"),
        ui.div(class_="owl-belly-mark"),
        ui.div(class_="owl-mouth"),
        ui.div(class_="owl-mask-strap owl-mask-strap-top-left"),
        ui.div(class_="owl-mask-strap owl-mask-strap-top-right"),
        ui.div(class_="owl-mask-strap owl-mask-strap-bottom-left"),
        ui.div(class_="owl-mask-strap owl-mask-strap-bottom-right"),
        ui.div(class_="owl-mask"),
        ui.div(class_="owl-foot owl-foot-left"),
        ui.div(class_="owl-foot owl-foot-right"),
        class_=f"vinuni-owl forecast-lexce-owl {mood_class}",
    )


def _input_source_chip(source: str) -> tuple[str, str]:
    source_text = str(source or "Historical fallback")
    if "AQICN" in source_text:
        return "Live input", "AQICN station"
    if "Realtime" in source_text:
        return "Live input", "HF realtime history"
    if "Open-Meteo" in source_text:
        return "Live fallback", "Open-Meteo"
    return "Historical fallback", "Cleaned dataset"


HORIZONS = {"1h": 1, "6h": 6, "24h": 24}


# ── UI ──────────────────────────────────────────────────────────────────────────

@module.ui
def forecast_ui():
    return ui.TagList(
        ui.div(
            ui.h3("Operational Forecast"),
            ui.div("Quality-controlled short-term prediction", class_="page-intro-sub"),
            ui.p("Forecasts use anomaly-aware air quality history, current conditions, weather signals, and time patterns."),
            class_="page-intro",
        ),
        # Controls
        ui.div(
            ui.input_radio_buttons("horizon", "Forecast Horizon", choices=list(HORIZONS.keys()), selected="6h", inline=True),
            ui.input_radio_buttons("target", "Metric", choices=["AQI", "PM2.5"], selected="AQI", inline=True),
            class_="control-bar",
        ),
        # Prediction hero
        ui.div(
            ui.div(
                ui.div(ui.output_ui("prediction_hero"), role="status", **{"aria-live": "polite", "aria-atomic": "true"}),
                class_="panel forecast-summary-panel",
            ),
            ui.div(
                ui.h4("Key Prediction Drivers"),
                ui.div(
                    ui.output_ui("importance_plot"),
                    class_="accessible-chart",
                    role="figure",
                    **{"aria-label": "Feature importance radar chart showing the strongest drivers of the air quality forecast."},
                ),
                ui.output_ui("importance_insight"),
                class_="panel",
            ),
            class_="grid-2",
        ),
        # Advisory insight
        ui.output_ui("forecast_insight"),
        # Model transparency + pollutant mix
        ui.div(
            ui.div(
                ui.h4("Model Error vs Baseline"),
                ui.div(
                    ui.output_ui("accuracy_chart"),
                    class_="accessible-chart",
                    role="figure",
                    **{"aria-label": "Bar chart comparing model error with a persistence baseline."},
                ),
                ui.output_ui("accuracy_text"),
                class_="panel",
            ),
            ui.div(
                ui.div(
                    ui.h4("Model Learning Space"),
                    ui.input_radio_buttons(
                        "space_color",
                        None,
                        choices={"error": "Error", "target": "Target", "risk": "Risk"},
                        selected="error",
                        inline=True,
                    ),
                    class_="panel-title-row",
                ),
                ui.div(
                    ui.output_ui("feature_space_plot"),
                    class_="accessible-chart",
                    role="figure",
                    **{"aria-label": "PCA projection of the model feature space, showing target structure and forecast errors."},
                ),
                ui.output_ui("feature_space_insight"),
                class_="panel feature-space-panel",
            ),
            class_="grid-2",
        ),
        # Validation
        ui.div(
            ui.h4("Backtest: Predictions vs Observed"),
            ui.div(
                ui.output_ui("validation_plot"),
                class_="accessible-chart",
                role="figure",
                **{"aria-label": "Backtest line chart comparing predicted and observed pollution levels."},
            ),
            ui.output_ui("validation_insight"),
            class_="panel",
        ),
    )


# ── Server ──────────────────────────────────────────────────────────────────────

@module.server
def forecast_server(
    input, output, session,
    *,
    prediction_context: Callable,
    get_model: Callable,
    snapshot: reactive.Value,
    city_hourly: pd.DataFrame,
):
    @reactive.calc
    def forecast_params() -> tuple[int, str, str]:
        target = "pm25" if input.target() == "PM2.5" else "aqi"
        horizon = HORIZONS[input.horizon()]
        data_mode = "cleaned"
        return horizon, target, data_mode

    @reactive.calc
    def current_model():
        horizon, target, data_mode = forecast_params()
        return get_model(horizon, target, data_mode)

    @reactive.calc
    def current_prediction_context() -> dict[str, Any]:
        horizon, target, data_mode = forecast_params()
        return prediction_context(horizon, target, data_mode)

    @reactive.calc
    def feature_space_context() -> dict[str, Any]:
        model = current_model()
        ctx = current_prediction_context()
        if model is None or city_hourly.empty:
            return {"frame": pd.DataFrame(), "variance": (np.nan, np.nan)}
        try:
            X, y, _feature_cols, times = _build_features(
                city_hourly,
                horizon_hours=model.horizon_hours,
                target_col=model.target_col,
                data_mode=getattr(model, "data_mode", "cleaned"),
            )
        except Exception:
            return {"frame": pd.DataFrame(), "variance": (np.nan, np.nan)}
        if len(X) < 20:
            return {"frame": pd.DataFrame(), "variance": (np.nan, np.nan)}

        split_idx = int(len(X) * 0.8)
        X_test = X.iloc[split_idx:].copy()
        times_test = pd.to_datetime(times.iloc[split_idx:], errors="coerce")
        if X_test.empty:
            return {"frame": pd.DataFrame(), "variance": (np.nan, np.nan)}

        validation = getattr(model, "validation", pd.DataFrame()).copy()
        n = min(len(X_test), len(validation)) if not validation.empty else len(X_test)
        n = min(n, 650)
        X_plot = X_test.tail(n).copy()

        if not validation.empty:
            validation = validation.tail(n).reset_index(drop=True)
            actual = pd.to_numeric(validation.get("actual"), errors="coerce")
            predicted = pd.to_numeric(validation.get("predicted"), errors="coerce")
            plot_times = pd.to_datetime(validation.get("local_time"), errors="coerce")
        else:
            y_plot = y.iloc[split_idx:].tail(n).reset_index(drop=True)
            actual = pd.to_numeric(y_plot, errors="coerce")
            predicted = pd.Series(model.model.predict(X_plot), dtype=float)
            plot_times = times_test.tail(n).reset_index(drop=True)

        latest_row = _latest_feature_row(city_hourly, model, ctx.get("snapshot"))
        combined = pd.concat([X_plot, latest_row], ignore_index=True)
        scaled = StandardScaler().fit_transform(combined)
        pca = PCA(n_components=2, random_state=42)
        coords = pca.fit_transform(scaled)

        frame = pd.DataFrame({
            "pc1": coords[:-1, 0],
            "pc2": coords[:-1, 1],
            "actual": actual.to_numpy(dtype=float),
            "predicted": predicted.to_numpy(dtype=float),
            "time": plot_times.dt.strftime("%d %b %Y, %H:%M").fillna("Unknown time"),
        })
        frame["residual"] = (frame["actual"] - frame["predicted"]).abs()
        frame["category"] = frame["actual"].map(aqi_category)
        frame["point_type"] = "Backtest case"

        pred = ctx.get("pred")
        current = pd.DataFrame({
            "pc1": [coords[-1, 0]],
            "pc2": [coords[-1, 1]],
            "actual": [np.nan],
            "predicted": [float(pred) if pred is not None and not pd.isna(pred) else np.nan],
            "time": ["Current forecast context"],
            "residual": [np.nan],
            "category": [aqi_category(pred) if pred is not None and not pd.isna(pred) else "Unknown"],
            "point_type": ["Current forecast"],
        })
        return {
            "frame": pd.concat([frame, current], ignore_index=True),
            "variance": tuple(float(v) for v in pca.explained_variance_ratio_[:2]),
        }

    @output
    @render.ui
    def prediction_hero():
        ctx = current_prediction_context()
        pred = ctx.get("pred")
        baseline = ctx.get("baseline")
        baseline_source = ctx.get("baseline_source", "Historical fallback")
        delta = ctx.get("delta", 0)
        horizon = HORIZONS[input.horizon()]

        if pred is None or pd.isna(pred):
            return ui.div(
                ui.h4("No prediction available"),
                ui.p("Enable realtime API or wait for data to load.", style="color:#6b7280;"),
            )

        color = aqi_color(pred)
        category = aqi_category(pred)
        direction = "higher" if delta >= 0 else "lower"
        mood_class = _mood_class(category)
        source_tier, source_name = _input_source_chip(baseline_source)
        lexce_message = {
            "Good": "Lexce looks relaxed: the model expects clean air.",
            "Moderate": "Lexce is calm, but watching the forecast.",
            "USG": "Lexce is alert: sensitive groups may need care.",
            "Unhealthy": "Lexce reacts with a mask: the model predicts unhealthy air.",
            "Very Unhealthy": "Lexce looks worried: the predicted risk is high.",
            "Hazardous": "Lexce is in indoor-mode: the prediction is severe.",
        }.get(category, "Lexce reacts to the model forecast.")

        return ui.div(
            ui.div(
                ui.div(
                    ui.div(f"+{horizon}h Forecast", style="font-size:0.75rem;font-weight:700;color:#9aa0a6;text-transform:uppercase;letter-spacing:0.08em;"),
                    ui.div(
                        ui.tags.span(f"{pred:.0f}", style=f"font-size:3.5rem;font-weight:900;color:{color};line-height:1;"),
                        ui.tags.span(f" {input.target()}", style="font-size:1.2rem;color:#6b7280;font-weight:600;"),
                    ),
                    ui.div(category, style=f"font-size:1.3rem;font-weight:700;color:{color};margin:4px 0;"),
                    ui.div(
                        ui.div(class_="forecast-scale-fill"),
                        ui.div(
                            class_="forecast-scale-marker",
                            style=f"left:{min(max(float(pred), 0), 500) / 500 * 100:.1f}%;--forecast-color:{color};",
                        ),
                        class_="forecast-mini-scale",
                        **{"aria-label": f"Forecast position on AQI scale: {pred:.0f}"},
                    ),
                    ui.div(
                        ui.span("Good"),
                        ui.span("Moderate"),
                        ui.span("USG"),
                        ui.span("Unhealthy"),
                        ui.span("Severe"),
                        ui.span("Hazardous"),
                        class_="forecast-scale-labels",
                    ),
                    ui.div(
                        f"{'↑' if delta >= 0 else '↓'} {abs(delta):.0f} {direction} than current ({baseline:.0f})",
                        style=f"color:{'#d1495b' if delta >= 0 else '#2bb673'};font-weight:600;font-size:0.9rem;",
                    ),
                    ui.div(
                        ui.span(class_="forecast-source-dot"),
                        ui.span(source_tier, class_="forecast-source-tier"),
                        ui.span(source_name, class_="forecast-source-name"),
                        class_="forecast-source-chip",
                    ),
                    ui.div(
                        aqi_advisory(pred),
                        style="color:#9aa0a6;margin-top:12px;font-size:0.9rem;line-height:1.5;",
                    ),
                    class_="forecast-summary-copy",
                ),
                ui.div(
                    ui.div(_lexce_owl(mood_class), class_="forecast-lexce-stage"),
                    ui.div(
                        ui.div("Lexce forecast mood", class_="forecast-lexce-title"),
                        ui.div(f"{category} prediction", class_="forecast-lexce-status", style=f"color:{color};"),
                        ui.p(lexce_message),
                        ui.div("Expression follows the predicted AQI, not just the current reading.", class_="forecast-lexce-caption"),
                        class_=f"forecast-lexce-bubble {mood_class}",
                    ),
                    class_="forecast-lexce-card",
                    role="status",
                    **{"aria-live": "polite", "aria-atomic": "true"},
                ),
                class_="forecast-summary-grid",
            ),
            class_="forecast-summary-content",
        )

    @output
    @render.ui
    def gauge_plot():
        ctx = current_prediction_context()
        pred = ctx.get("pred")
        if pred is None or pd.isna(pred):
            return _plotly_html(_blank("No forecast available"))
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=float(pred),
            number={"suffix": f" {input.target()}", "font": {"size": 24, "color": "#e8eaed"}},
            gauge={
                "axis": {"range": [0, 500], "tickfont": {"size": 10, "color": "#6b7280"}},
                "bar": {"color": aqi_color(pred), "thickness": 0.75},
                "bgcolor": "#282c34",
                "bordercolor": "#363b44",
                "steps": [
                    {"range": [0, 50], "color": "rgba(43,182,115,0.15)"},
                    {"range": [50, 100], "color": "rgba(245,183,0,0.15)"},
                    {"range": [100, 150], "color": "rgba(242,143,59,0.15)"},
                    {"range": [150, 200], "color": "rgba(209,73,91,0.15)"},
                    {"range": [200, 300], "color": "rgba(123,44,191,0.15)"},
                    {"range": [300, 500], "color": "rgba(90,24,154,0.12)"},
                ],
            },
            domain={"x": [0.05, 0.95], "y": [0.1, 0.9]},
        ))
        fig.update_layout(
            height=260,
            margin={"l": 20, "r": 20, "t": 30, "b": 10},
            paper_bgcolor="rgba(0,0,0,0)",
            font={"family": "Inter, system-ui, sans-serif"},
        )
        return _plotly_html(sanitize_figure(fig))

    @output
    @render.ui
    def feature_space_plot():
        context = feature_space_context()
        frame = context["frame"]
        if frame.empty:
            return _plotly_html(_blank("No model feature space available"))

        hist = frame[frame["point_type"] == "Backtest case"].dropna(subset=["pc1", "pc2"]).copy()
        current = frame[frame["point_type"] == "Current forecast"].copy()
        if hist.empty:
            return _plotly_html(_blank("No backtest cases available"))

        var1, var2 = context["variance"]
        mode = input.space_color()
        fig = go.Figure()
        hover = (
            "<b>%{customdata[0]}</b><br>"
            "Actual: %{customdata[1]:.1f}<br>"
            "Predicted: %{customdata[2]:.1f}<br>"
            "Residual: %{customdata[3]:.1f}<br>"
            "Risk: %{customdata[4]}"
            "<extra></extra>"
        )

        if mode == "risk":
            colors = {
                "Good": "#2bb673",
                "Moderate": "#f5b700",
                "USG": "#f28f3b",
                "Unhealthy": "#d1495b",
                "Very Unhealthy": "#7b2cbf",
                "Hazardous": "#5a189a",
                "Unknown": "#9aa0a6",
            }
            for category, one in hist.groupby("category", sort=False):
                fig.add_trace(go.Scatter(
                    x=one["pc1"],
                    y=one["pc2"],
                    mode="markers",
                    marker={
                        "size": 8,
                        "color": colors.get(category, "#9aa0a6"),
                        "opacity": 0.72,
                        "line": {"color": "rgba(255,255,255,0.20)", "width": 0.7},
                    },
                    name=category,
                    customdata=np.stack([one["time"], one["actual"], one["predicted"], one["residual"], one["category"]], axis=-1),
                    hovertemplate=hover,
                ))
        else:
            color_col = "residual" if mode == "error" else "actual"
            color_title = "Abs Error" if mode == "error" else input.target()
            colorscale = "Turbo" if mode == "error" else "Viridis"
            fig.add_trace(go.Scatter(
                x=hist["pc1"],
                y=hist["pc2"],
                mode="markers",
                marker={
                    "size": 8,
                    "color": hist[color_col],
                    "colorscale": colorscale,
                    "showscale": True,
                    "colorbar": {"title": color_title, "thickness": 10, "len": 0.72},
                    "opacity": 0.72,
                    "line": {"color": "rgba(255,255,255,0.20)", "width": 0.7},
                },
                name="Backtest cases",
                customdata=np.stack([hist["time"], hist["actual"], hist["predicted"], hist["residual"], hist["category"]], axis=-1),
                hovertemplate=hover,
            ))

        if not current.empty:
            row = current.iloc[0]
            fig.add_trace(go.Scatter(
                x=[row["pc1"]],
                y=[row["pc2"]],
                mode="markers+text",
                marker={
                    "symbol": "diamond",
                    "size": 17,
                    "color": "#7df9ff",
                    "line": {"color": "#f8fafc", "width": 2},
                },
                text=["Current"],
                textposition="top center",
                textfont={"size": 11, "color": "#7df9ff"},
                name="Current forecast",
                hovertemplate=(
                    "<b>Current forecast context</b><br>"
                    f"Predicted: {row['predicted']:.1f} {input.target()}<br>"
                    f"Risk: {row['category']}<extra></extra>"
                ),
            ))

        fig.update_xaxes(title=f"PC1 ({var1 * 100:.0f}% variance)" if np.isfinite(var1) else "PC1")
        fig.update_yaxes(title=f"PC2 ({var2 * 100:.0f}% variance)" if np.isfinite(var2) else "PC2")
        fig.update_layout(
            hovermode="closest",
            showlegend=(mode == "risk"),
            legend={
                "orientation": "h",
                "x": 0.5,
                "xanchor": "center",
                "y": 1.06,
                "yanchor": "bottom",
                "font": {"size": 10, "color": "#9aa0a6"},
                "bgcolor": "rgba(0,0,0,0)",
            },
            margin={"l": 8, "r": 8, "t": 26, "b": 8},
        )
        return _plotly_html(_dark_fig(fig, height=300))

    @output
    @render.ui
    def feature_space_insight():
        context = feature_space_context()
        frame = context["frame"]
        if frame.empty:
            return ui.div()
        hist = frame[frame["point_type"] == "Backtest case"].copy()
        current = frame[frame["point_type"] == "Current forecast"].copy()
        if hist.empty or current.empty:
            return ui.div()
        residual = hist["residual"].dropna()
        med_error = residual.median() if not residual.empty else np.nan
        return ui.div(
            ui.div("FEATURE SPACE MAP", class_="insight-label"),
            ui.p(ui.HTML(
                "Each dot is a historical backtest case projected from the same engineered features used by the "
                f"<span class='insight-highlight'>{input.horizon()}</span> model. The cyan diamond marks the current forecast context. "
                + (
                    f"Median backtest error in this view is <span class='insight-highlight'>{med_error:.1f}</span>."
                    if np.isfinite(med_error) else
                    "Use the toggle to inspect target structure, error concentration, or AQI risk bands."
                )
            )),
            class_="insight-box feature-space-note",
        )

    @output
    @render.ui
    def forecast_insight():
        ctx = current_prediction_context()
        pred = ctx.get("pred")
        model = ctx.get("model")
        horizon = HORIZONS[input.horizon()]
        if pred is None or pd.isna(pred):
            return ui.div()
        model_info = ""
        if model is not None:
            improvement = 100 * (model.baseline_mae - model.mae) / model.baseline_mae if model.baseline_mae else 0
            model_info = (
                f"The <span class='insight-highlight'>{model.model_name}</span> model trained on "
                "<span class='insight-soft'>quality-controlled, anomaly-aware</span> data is "
                f"<span class='insight-highlight'>{improvement:.0f}%</span> more accurate than the persistence baseline."
            )
        return ui.div(
            ui.div("MODEL BASIS", class_="insight-label"),
            ui.p(ui.HTML(
                f"This <span class='insight-highlight'>{horizon}-hour</span> forecast uses the latest air quality measurements, "
                f"weather data (temperature, humidity, pressure), and time-of-day patterns. {model_info}"
            )),
            class_="insight-box",
        )

    @output
    @render.ui
    def accuracy_chart():
        model = current_model()
        if model is None:
            return _plotly_html(_blank("No model available"))
        df = pd.DataFrame({
            "Metric": ["MAE", "MAE", "RMSE", "RMSE"],
            "Method": ["Forecast Model", "Persistence Baseline", "Forecast Model", "Persistence Baseline"],
            "Error": [model.mae, model.baseline_mae, model.rmse, model.baseline_rmse],
        })
        fig = px.bar(df, x="Metric", y="Error", color="Method", barmode="group",
                     color_discrete_map={"Forecast Model": "#1f9d8a", "Persistence Baseline": "#d1495b"})
        fig.update_layout(xaxis_title="", yaxis_title="Prediction Error", legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "font": {"color": "#9aa0a6"}})
        return _plotly_html(_dark_fig(fig, height=320))

    @output
    @render.ui
    def accuracy_text():
        model = current_model()
        if model is None:
            return ui.div()
        return ui.div(
            ui.div("PERFORMANCE SUMMARY", class_="insight-label"),
            ui.p(ui.HTML(
                "Lower bars = better predictions. The anomaly-aware forecast model predicts "
                f"<span class='insight-highlight'>{input.target()}</span> within "
                f"<span class='insight-highlight'>±{model.mae:.0f}</span> points on average, compared to "
                f"<span class='insight-risk'>±{model.baseline_mae:.0f}</span> for the persistence baseline."
            )),
            class_="insight-box",
        )

    @output
    @render.ui
    def importance_plot():
        model = current_model()
        if model is None or model.feature_importance.empty:
            return _plotly_html(_blank("No feature data"))
        imp = model.feature_importance.copy()
        imp["importance"] = pd.to_numeric(imp["importance"], errors="coerce")
        imp = imp.dropna(subset=["feature", "importance"])
        imp = imp[imp["importance"] > 0].nlargest(7, "importance")
        if imp.empty:
            return _plotly_html(_blank("No positive feature importance"))

        imp["log_importance"] = np.log1p(imp["importance"])
        max_log_importance = float(imp["log_importance"].max())
        imp["relative"] = imp["log_importance"] / max_log_importance * 100 if max_log_importance > 0 else 0
        imp["display"] = imp["feature"].map(_driver_display_name)

        theta = imp["display"].tolist()
        radial = imp["relative"].tolist()
        scores = imp["importance"].tolist()
        theta_closed = theta + [theta[0]]
        radial_closed = radial + [radial[0]]
        linear_relative = (imp["importance"] / float(imp["importance"].max()) * 100).tolist()
        custom_closed = list(zip(scores, radial, linear_relative)) + [(scores[0], radial[0], linear_relative[0])]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=radial_closed,
            theta=theta_closed,
            mode="lines+markers",
            fill="toself",
            fillcolor="rgba(31, 157, 138, 0.26)",
            line={"color": "#55e3c2", "width": 3},
            marker={
                "size": 9,
                "color": radial_closed,
                "colorscale": [[0, "#7dd3fc"], [0.55, "#55e3c2"], [1, "#f6d433"]],
                "line": {"color": "#0b1118", "width": 1.4},
            },
            customdata=custom_closed,
            hovertemplate=(
                "<b>%{theta}</b><br>"
                "Log-scaled influence: %{r:.0f}%<br>"
                "Linear relative: %{customdata[2]:.0f}%<br>"
                "Importance score: %{customdata[0]:.4f}"
                "<extra></extra>"
            ),
            name="Prediction driver strength",
        ))
        fig.add_trace(go.Scatterpolar(
            r=[50] * len(theta_closed),
            theta=theta_closed,
            mode="lines",
            line={"color": "rgba(155, 220, 255, 0.22)", "width": 1.2, "dash": "dot"},
            hoverinfo="skip",
            showlegend=False,
        ))
        fig.update_layout(
            showlegend=False,
            margin={"l": 88, "r": 88, "t": 50, "b": 64},
            polar={
                "bgcolor": "rgba(5, 14, 28, 0.55)",
                "domain": {"x": [0.18, 0.82], "y": [0.12, 0.90]},
                "radialaxis": {
                    "range": [0, 105],
                    "tickvals": [25, 50, 75, 100],
                    "ticktext": ["25", "50", "75", "100"],
                    "gridcolor": "rgba(155, 220, 255, 0.18)",
                    "linecolor": "rgba(155, 220, 255, 0.22)",
                    "tickfont": {"size": 10, "color": "#9aa0a6"},
                    "angle": 90,
                },
                "angularaxis": {
                    "gridcolor": "rgba(155, 220, 255, 0.14)",
                    "linecolor": "rgba(155, 220, 255, 0.24)",
                    "tickfont": {"size": 10, "color": "#dce6ee"},
                    "rotation": 90,
                    "direction": "clockwise",
                },
            },
            annotations=[
                {
                    "text": "Log-scaled relative influence",
                    "x": 0.5,
                    "y": 1.02,
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 11, "color": "#9aa0a6"},
                }
            ],
        )
        return _plotly_html(_dark_fig(fig, height=360))

    @output
    @render.ui
    def importance_insight():
        model = current_model()
        if model is None or model.feature_importance.empty:
            return ui.div()
        top_feat = model.feature_importance.nlargest(3, "importance")["feature"].tolist()
        top_names = [_driver_display_name(f).replace("<br>", " ") for f in top_feat]
        return ui.div(
            ui.div("MODEL INTERPRETATION", class_="insight-label"),
            ui.p(ui.HTML(
                "This forecast is driven most strongly by "
                + ", ".join(f"<span class='insight-highlight'>{name}</span>" for name in top_names)
                + ". The radar balances strong and secondary signals so the model's decision profile is easier to compare across horizons."
            )),
            class_="insight-box",
        )

    @output
    @render.ui
    def validation_plot():
        model = current_model()
        if model is None or model.validation.empty:
            return _plotly_html(_blank())
        val = model.validation.tail(24 * 30).copy()
        val["local_time"] = pd.to_datetime(val["local_time"], errors="coerce")
        val = val.dropna(subset=["local_time", "actual", "predicted"])
        if val.empty:
            return _plotly_html(_blank())
        # Safe datetime conversion for strict JSON serialization.
        val["plot_time"] = val["local_time"].dt.tz_localize(None).dt.strftime("%Y-%m-%dT%H:%M:%S")
        x = list(val["plot_time"])
        # Replace any remaining NaN/inf with None for JSON safety
        actual = [float(v) if np.isfinite(v) else None for v in val["actual"]]
        predicted = [float(v) if np.isfinite(v) else None for v in val["predicted"]]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x, y=actual, mode="lines", name="Actual", line={"color": "#e8eaed", "width": 1.5}))
        fig.add_trace(go.Scatter(x=x, y=predicted, mode="lines", name="Model Prediction", line={"color": "#1f9d8a", "width": 2}))
        if "baseline" in val.columns:
            baseline = [float(v) if np.isfinite(v) else None for v in val["baseline"]]
            fig.add_trace(go.Scatter(x=x, y=baseline, mode="lines", name="Persistence Baseline", line={"color": "#d1495b", "width": 1, "dash": "dot"}))
        fig.update_xaxes(type="date", tickformat="%b %d", title="")
        fig.update_yaxes(title=input.target())
        fig.update_layout(hovermode="x unified", legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "font": {"color": "#9aa0a6"}})
        return _plotly_html(_dark_fig(fig, height=340))

    @output
    @render.ui
    def validation_insight():
        model = current_model()
        if model is None:
            return ui.div()
        return ui.div(
            ui.div("BACKTEST SUMMARY", class_="insight-label"),
            ui.p(ui.HTML(
                "White line = observed values, teal line = model predictions. "
                "The <span class='insight-soft'>anomaly-aware</span> model "
                f"(<span class='insight-highlight'>MAE: {model.mae:.1f}</span>) tracks the actual values more closely than "
                f"the persistence baseline (<span class='insight-risk'>MAE: {model.baseline_mae:.1f}</span>)."
            )),
            class_="insight-box",
        )
