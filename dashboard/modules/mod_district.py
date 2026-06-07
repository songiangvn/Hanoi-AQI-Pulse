"""Districts page — choropleth map, ranking table with monthly heatmap, deep‑dive."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from shiny import module, reactive, render, ui

from src.utils import aqi_category, aqi_color, sanitize_figure

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
GEOJSON_PATH = APP_ROOT / "data" / "hanoi_districts.geojson"
if not GEOJSON_PATH.exists():
    GEOJSON_PATH = REPO_ROOT / "data" / "hanoi_districts.geojson"

DISTRICT_CENTROIDS = {
    "Ba Dinh": (21.0368, 105.8342), "Ba Vi": (21.1990, 105.4230),
    "Bac Tu Liem": (21.0730, 105.7700), "Cau Giay": (21.0360, 105.7900),
    "Chuong My": (20.9230, 105.7010), "Dan Phuong": (21.0870, 105.6700),
    "Dong Anh": (21.1360, 105.8490), "Dong Da": (21.0180, 105.8290),
    "Gia Lam": (21.0270, 105.9590), "Ha Dong": (20.9710, 105.7780),
    "Hai Ba Trung": (21.0060, 105.8580), "Hoai Duc": (21.0320, 105.6900),
    "Hoan Kiem": (21.0285, 105.8542), "Hoang Mai": (20.9750, 105.8650),
    "Long Bien": (21.0440, 105.9000), "Me Linh": (21.1840, 105.7200),
    "My Duc": (20.7040, 105.7400), "Nam Tu Liem": (21.0160, 105.7700),
    "Phu Xuyen": (20.7300, 105.9100), "Phuc Tho": (21.1030, 105.5600),
    "Quoc Oai": (20.9900, 105.6400), "Soc Son": (21.2570, 105.8500),
    "Son Tay": (21.1400, 105.5050), "Tay Ho": (21.0680, 105.8200),
    "Thach That": (21.0300, 105.5400), "Thanh Oai": (20.8600, 105.7700),
    "Thanh Tri": (20.9400, 105.8500), "Thanh Xuan": (20.9950, 105.8090),
    "Thuong Tin": (20.8700, 105.8700), "Ung Hoa": (20.7200, 105.7800),
}
DISTRICT_CHOICES = sorted(DISTRICT_CENTROIDS.keys())
DISTRICT_COORDS = pd.DataFrame(
    [{"district": d, "lat": lat, "lon": lon} for d, (lat, lon) in DISTRICT_CENTROIDS.items()]
)
MONTH_CHOICES = {
    "All": "All",
    "1": "Jan",
    "2": "Feb",
    "3": "Mar",
    "4": "Apr",
    "5": "May",
    "6": "Jun",
    "7": "Jul",
    "8": "Aug",
    "9": "Sep",
    "10": "Oct",
    "11": "Nov",
    "12": "Dec",
}


@lru_cache(maxsize=1)
def _load_geojson() -> dict | None:
    if not GEOJSON_PATH.exists():
        return None
    with open(GEOJSON_PATH) as f:
        return json.load(f)


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


def _rgba_from_aqi(aqi: float | None, alpha: int = 215) -> list[int]:
    color = aqi_color(aqi)
    if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
        return [79, 195, 247, alpha]
    return [int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16), alpha]


def _district_3d_geojson(map_frame: pd.DataFrame, selected: set[str]) -> dict | None:
    geojson = _load_geojson()
    if geojson is None:
        return None
    values: dict[str, float] = {}
    if not map_frame.empty and {"district", "aqi_daily"}.issubset(map_frame.columns):
        values = {
            str(row["district"]): float(row["aqi_daily"])
            for _, row in map_frame.dropna(subset=["aqi_daily"]).iterrows()
        }
    city_avg = float(np.mean(list(values.values()))) if values else 80.0
    has_focus = bool(selected)
    coord_lookup = {
        row["district"]: {"lat": float(row["lat"]), "lon": float(row["lon"])}
        for _, row in DISTRICT_COORDS.iterrows()
    }

    features = []
    for feature in geojson.get("features", []):
        props = dict(feature.get("properties", {}))
        district = props.get("district_ascii") or props.get("shapeName")
        aqi = values.get(district, city_avg)
        is_selected = district in selected if has_focus else True
        coord = coord_lookup.get(district, {"lat": 21.02, "lon": 105.75})
        alpha = 190 if is_selected else 52
        elevation_scale = 22 if is_selected else 8
        props.update({
            "district": district,
            "aqi": round(float(aqi), 1),
            "category": aqi_category(float(aqi)),
            "selected": is_selected,
            "fillColor": _rgba_from_aqi(float(aqi), alpha),
            "lineColor": [224, 244, 255, 230 if is_selected else 108],
            "topLineColor": [155, 220, 255, 235 if is_selected else 120],
            "elevation": max(90.0, min(4700.0, float(aqi) * elevation_scale)),
            "labelPosition": [coord["lon"], coord["lat"], max(90.0, min(4700.0, float(aqi) * elevation_scale)) + 320],
            "labelColor": [245, 250, 255, 245 if is_selected else 118],
            "labelBackground": [8, 12, 18, 198 if is_selected else 120],
        })
        new_feature = dict(feature)
        new_feature["properties"] = props
        features.append(new_feature)
    return {"type": "FeatureCollection", "features": features}


def _district_map_srcdoc(geojson: dict, selected_count: int, period_label: str) -> str:
    geojson_js = json.dumps(geojson, ensure_ascii=False)
    period_js = json.dumps(period_label, ensure_ascii=False)
    focus_text = "all districts" if selected_count == len(DISTRICT_CHOICES) else f"{selected_count} selected"
    focus_js = json.dumps(focus_text, ensure_ascii=False)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    html, body, #district-map {{
      width: 100%;
      height: 100%;
      margin: 0;
      overflow: hidden;
      background:
        radial-gradient(circle at 52% 38%, rgba(79,195,247,0.13), transparent 30%),
        linear-gradient(145deg, #0b1118 0%, #111827 54%, #080b10 100%);
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .map-title {{
      position: absolute;
      left: 14px;
      top: 14px;
      z-index: 5;
      color: #e8eaed;
      font-weight: 900;
      font-size: 12px;
      padding: 8px 10px;
      border: 1px solid rgba(79,195,247,0.34);
      border-radius: 999px;
      background: rgba(8,12,18,0.74);
      backdrop-filter: blur(8px);
    }}
    .map-legend {{
      position: absolute;
      left: 14px;
      bottom: 14px;
      z-index: 5;
      color: #c6d3df;
      font-size: 11px;
      line-height: 1.35;
      padding: 9px 10px;
      border: 1px solid rgba(255,255,255,0.10);
      border-radius: 10px;
      background: rgba(8,12,18,0.76);
      backdrop-filter: blur(8px);
    }}
    .map-legend strong {{ color: #9bdcff; }}
    .deck-tooltip {{
      color: #f8fafc !important;
      background: rgba(10,14,20,0.92) !important;
      border: 1px solid rgba(79,195,247,0.35) !important;
      border-radius: 8px !important;
      box-shadow: 0 12px 28px rgba(0,0,0,0.35) !important;
      font-size: 12px !important;
      line-height: 1.4 !important;
      max-width: 220px !important;
    }}
    .map-fallback {{
      position: absolute;
      inset: 0;
      z-index: 4;
      display: grid;
      place-items: center;
      padding: 24px;
      color: #c6d3df;
      text-align: center;
      background: rgba(8,12,18,0.35);
      font-size: 13px;
      line-height: 1.45;
    }}
  </style>
  <script src="https://unpkg.com/deck.gl@9.0.0/dist.min.js"></script>
</head>
<body>
  <div id="district-map"></div>
  <div id="fallback" class="map-fallback">Loading interactive 3D district AQI map...</div>
  <div class="map-title">3D District AQI · {period_label} · {focus_text}</div>
  <div class="map-legend"><strong>Height</strong> = average AQI<br><strong>Color</strong> = AQI risk band<br><strong>Top lines</strong> = district boundaries</div>
  <script>
    const geojson = {geojson_js};
    const periodLabel = {period_js};
    const focusLabel = {focus_js};
    const fallback = document.getElementById('fallback');

    if (!window.deck) {{
      fallback.textContent = 'The 3D map library could not load. District rankings and trends remain available in the dashboard.';
    }} else {{
      const layer = new deck.GeoJsonLayer({{
        id: 'district-aqi-extrusion',
        data: geojson,
        pickable: true,
        stroked: false,
        filled: true,
        extruded: true,
        wireframe: false,
        getElevation: f => f.properties.elevation,
        getFillColor: f => f.properties.fillColor,
        material: {{
          ambient: 0.44,
          diffuse: 0.64,
          shininess: 32,
          specularColor: [210, 230, 255]
        }}
      }});

      function ringsForFeature(feature) {{
        const geom = feature.geometry || {{}};
        if (geom.type === 'Polygon') return geom.coordinates || [];
        if (geom.type === 'MultiPolygon') return (geom.coordinates || []).flat();
        return [];
      }}

      const topBoundaryData = geojson.features.flatMap(feature => {{
        const props = feature.properties || {{}};
        const elevation = Number(props.elevation || 0) + 42;
        return ringsForFeature(feature)
          .filter(ring => Array.isArray(ring) && ring.length > 2)
          .map(ring => ({{
            district: props.district,
            selected: props.selected,
            color: props.topLineColor,
            path: ring.map(point => [point[0], point[1], elevation])
          }}));
      }});

      const topBoundaryLayer = new deck.PathLayer({{
        id: 'district-roof-boundaries',
        data: topBoundaryData,
        pickable: false,
        getPath: d => d.path,
        getColor: d => d.color,
        getWidth: d => d.selected ? 88 : 46,
        widthUnits: 'meters',
        widthMinPixels: 1.2,
        rounded: true,
        parameters: {{depthTest: false}}
      }});

      const labelData = geojson.features
        .map(f => f.properties)
        .filter(p => p && p.labelPosition);

      const labelLayer = new deck.TextLayer({{
        id: 'district-name-labels',
        data: labelData,
        pickable: true,
        billboard: true,
        getPosition: d => d.labelPosition,
        getText: d => d.district,
        getSize: d => d.selected ? 10 : 8,
        sizeUnits: 'pixels',
        getColor: d => d.labelColor,
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'center',
        background: true,
        getBackgroundColor: d => d.labelBackground,
        backgroundPadding: [4, 2],
        getBorderColor: [79, 195, 247, 90],
        getBorderWidth: 1,
        fontWeight: 800
      }});

      const deckInstance = new deck.Deck({{
        parent: document.getElementById('district-map'),
        initialViewState: {{
          longitude: 105.75,
          latitude: 21.02,
          zoom: 8.95,
          pitch: 60,
          bearing: 28
        }},
        controller: true,
        views: [new deck.MapView({{repeat: false}})],
        layers: [layer, topBoundaryLayer, labelLayer],
        getTooltip: (info) => {{
          const p = info.object && info.object.properties;
          if (!p) return null;
          const state = p.selected ? 'Selected' : 'Context';
          return {{
            html: `<strong>${{p.district}}</strong><br>AQI ${{Number(p.aqi).toFixed(0)}} · ${{p.category}}<br><span style="color:#9bdcff">${{state}} · ${{periodLabel}}</span>`
          }};
        }}
      }});
      fallback.style.display = 'none';
    }}
  </script>
</body>
</html>"""


def _district_2d_figure(mdf: pd.DataFrame, selected: set[str]) -> go.Figure:
    selected_df = mdf[mdf["district"].isin(selected)].copy()
    dim_df = mdf[~mdf["district"].isin(selected)].copy()
    geojson = _load_geojson()
    if geojson is not None:
        fig = go.Figure()
        if not dim_df.empty:
            fig.add_trace(go.Choroplethmapbox(
                geojson=geojson,
                locations=list(dim_df["district"]),
                z=[1] * len(dim_df),
                featureidkey="properties.shapeName",
                colorscale=[[0, "rgba(39,44,52,0.22)"], [1, "rgba(78,86,99,0.34)"]],
                marker={"opacity": 0.34, "line": {"color": "rgba(255,255,255,0.08)", "width": 0.8}},
                hoverinfo="skip",
                showscale=False,
                name="Not selected",
            ))
        if not selected_df.empty:
            fig.add_trace(go.Choroplethmapbox(
                geojson=geojson,
                locations=list(selected_df["district"]),
                z=list(selected_df["aqi_daily"]),
                featureidkey="properties.shapeName",
                colorscale="YlOrRd",
                zmin=30,
                zmax=180,
                marker={"opacity": 0.84, "line": {"color": "rgba(255,255,255,0.50)", "width": 1.2}},
                colorbar={"title": "AQI", "thickness": 10, "len": 0.62},
                customdata=np.stack(
                    [selected_df["district"], selected_df["aqi_daily"]],
                    axis=-1,
                ),
                hovertemplate="<b>%{customdata[0]}</b><br>AQI %{customdata[1]:.1f}<extra></extra>",
                name="Selected districts",
            ))
            label_df = selected_df if len(selected_df) <= 12 else selected_df.nlargest(12, "aqi_daily")
            fig.add_trace(go.Scattermapbox(
                lat=list(label_df["lat"]),
                lon=list(label_df["lon"]),
                mode="text",
                text=list(label_df["district"]),
                textposition="middle center",
                textfont={"size": 9, "color": "#f8fafc"},
                hoverinfo="skip",
                showlegend=False,
            ))
        fig.update_layout(
            mapbox={"style": "carto-darkmatter", "zoom": 9.2, "center": {"lat": 21.0, "lon": 105.75}},
            height=500,
        )
    else:
        mdf["picked"] = np.where(mdf["district"].isin(selected), "Selected", "Dimmed")
        fig = px.scatter_mapbox(
            mdf, lat="lat", lon="lon",
            color="aqi_daily", size="aqi_daily", size_max=22,
            hover_name="district",
            color_continuous_scale="YlOrRd",
            zoom=9.2, height=500,
        )

    fig.update_layout(
        mapbox_style="carto-darkmatter",
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        coloraxis_colorbar={"title": "AQI", "thickness": 10, "len": 0.6},
        paper_bgcolor="rgba(0,0,0,0)",
        transition={"duration": 500, "easing": "cubic-in-out"},
        uirevision="district-map-2d",
    )
    return sanitize_figure(fig)


def _aqi_bg_style(val: float) -> str:
    """Return inline CSS for a cell background based on AQI value."""
    color = aqi_color(val)
    return f"background:{color};color:#fff;font-weight:700;padding:4px 8px;border-radius:4px;text-align:center;display:inline-block;min-width:36px;font-size:0.8rem;"


# ── UI ──────────────────────────────────────────────────────────────────────────

@module.ui
def district_ui():
    return ui.TagList(
        ui.div(
            ui.h3("District Explorer"),
            ui.div("Compare air quality across Hanoi's 30 districts", class_="page-intro-sub"),
            class_="page-intro",
        ),
        # Inline controls
        ui.div(
            ui.div(
                ui.div(
                    ui.div(
                        ui.div("Districts", class_="district-picker-title"),
                        ui.output_text("selected_count"),
                        class_="district-picker-head",
                    ),
                    ui.div(
                        ui.input_action_button("select_all", "Select all", class_="picker-action"),
                        ui.input_action_button("focus_top5", "Top 5", class_="picker-action picker-action-hot"),
                        ui.input_action_button("focus_above_avg", "Above avg", class_="picker-action picker-action-hot"),
                        ui.input_action_button("focus_pm25", "PM2.5 hotspots", class_="picker-action picker-action-hot"),
                        ui.input_action_button("clear_all", "Clear", class_="picker-action picker-action-muted"),
                        class_="district-picker-tools",
                    ),
                    ui.input_checkbox_group(
                        "districts",
                        "Choose districts to include",
                        choices=DISTRICT_CHOICES,
                        selected=DISTRICT_CHOICES,
                    ),
                    ui.div(ui.output_ui("selection_hint"), role="status", **{"aria-live": "polite"}),
                    class_="district-picker",
                ),
                class_="district-filter-box",
            ),
            ui.input_select("year", "Year", choices=["All"] + [str(y) for y in range(2026, 2021, -1)], selected="All", width="100px"),
            ui.input_select("month", "Month", choices=MONTH_CHOICES, selected="All", width="110px"),
            class_="control-bar district-control-bar",
        ),
        # Map + ranking
        ui.div(
            ui.div(
                ui.div(
                    ui.h4("District AQI Map"),
                    ui.input_radio_buttons("map_view", None, choices=["3D", "2D"], selected="3D", inline=True),
                    class_="panel-title-row",
                ),
                ui.div(
                    ui.output_ui("choropleth"),
                    class_="accessible-chart",
                    role="figure",
                    **{"aria-label": "Interactive 3D map comparing average AQI across Hanoi districts. Selected districts are emphasized and unselected districts are dimmed."},
                ),
                class_="panel",
            ),
            ui.div(
                ui.h4("District Ranking"),
                ui.div(ui.output_ui("ranking_table_ui"), role="region", **{"aria-label": "District ranking table by annual air quality metrics"}),
                class_="panel",
            ),
            class_="grid-2",
        ),
        # Insight
        ui.output_ui("district_insight"),
        # Deep dive
        ui.div(
            ui.div(
                ui.h4("Selected District — Monthly Trend"),
                ui.div(
                    ui.output_ui("district_trend"),
                    class_="accessible-chart",
                    role="figure",
                    **{"aria-label": "Monthly AQI trend chart for the selected Hanoi districts."},
                ),
                class_="panel",
            ),
            ui.div(
                ui.h4("Pollutant Breakdown"),
                ui.div(
                    ui.output_ui("pollutant_breakdown"),
                    class_="accessible-chart",
                    role="figure",
                    **{"aria-label": "Bar chart comparing AQI, PM2.5, PM10, nitrogen dioxide, ozone, and carbon monoxide for selected districts."},
                ),
                class_="panel",
            ),
            class_="grid-2",
        ),
    )


# ── Server ──────────────────────────────────────────────────────────────────────

@module.server
def district_server(
    input, output, session,
    *,
    district_daily: pd.DataFrame,
):
    @reactive.effect
    @reactive.event(input.select_all)
    def _select_all_districts():
        ui.update_checkbox_group("districts", selected=DISTRICT_CHOICES)

    @reactive.effect
    @reactive.event(input.clear_all)
    def _clear_all_districts():
        ui.update_checkbox_group("districts", selected=[])

    @reactive.effect
    @reactive.event(input.focus_top5)
    def _focus_top5():
        mdf = map_data()
        selected = mdf.nlargest(5, "aqi_daily")["district"].tolist()
        ui.update_checkbox_group("districts", selected=selected)

    @reactive.effect
    @reactive.event(input.focus_above_avg)
    def _focus_above_average():
        mdf = map_data()
        if mdf.empty:
            ui.update_checkbox_group("districts", selected=[])
            return
        city_avg = float(mdf["aqi_daily"].mean())
        selected = mdf[mdf["aqi_daily"] >= city_avg]["district"].tolist()
        ui.update_checkbox_group("districts", selected=selected)

    @reactive.effect
    @reactive.event(input.focus_pm25)
    def _focus_pm25_hotspots():
        df = filtered()
        if df.empty or "aqi_pm2_5" not in df.columns:
            mdf = map_data()
            selected = mdf.nlargest(5, "aqi_daily")["district"].tolist()
            ui.update_checkbox_group("districts", selected=selected)
            return
        selected = (
            df.groupby("district", as_index=False)["aqi_pm2_5"]
            .mean()
            .dropna()
            .nlargest(5, "aqi_pm2_5")["district"]
            .tolist()
        )
        ui.update_checkbox_group("districts", selected=selected)

    @reactive.calc
    def selected_districts() -> list[str]:
        raw = input.districts()
        if raw is None:
            return []
        if isinstance(raw, str):
            raw = [raw]
        selected = [d for d in raw if d in DISTRICT_CENTROIDS]
        return selected

    @output
    @render.text
    def selected_count():
        n = len(selected_districts())
        return f"{n}/30 selected"

    @reactive.calc
    def year_filtered():
        df = district_daily.copy()
        if input.year() != "All":
            year = int(input.year())
            df = df[df["time"].dt.year == year]
        return df

    @reactive.calc
    def filtered():
        df = year_filtered()
        if input.month() != "All":
            month = int(input.month())
            df = df[df["time"].dt.month == month]
        return df

    @reactive.calc
    def period_label() -> str:
        year = "All years" if input.year() == "All" else input.year()
        month = "All months" if input.month() == "All" else MONTH_CHOICES.get(str(input.month()), "Selected month")
        return f"{year} · {month}"

    @reactive.calc
    def map_data():
        df = filtered()
        if df.empty:
            return pd.DataFrame(columns=["district", "aqi_daily", "lat", "lon"])
        agg = df.groupby("district", as_index=False)["aqi_daily"].mean().dropna()
        return agg.merge(DISTRICT_COORDS, on="district", how="inner")

    @reactive.calc
    def monthly_trend_data() -> tuple[pd.DataFrame, pd.DataFrame]:
        df = year_filtered()
        if df.empty:
            empty = pd.DataFrame(columns=["district", "period", "aqi", "month_str"])
            return empty, pd.DataFrame(columns=["period", "aqi", "month_str"])

        base = df[["district", "time", "aqi_daily"]].dropna(subset=["district", "time", "aqi_daily"]).copy()
        base["period"] = base["time"].dt.to_period("M")
        monthly = base.groupby(["district", "period"], as_index=False).agg(aqi=("aqi_daily", "mean"))
        monthly["month_str"] = monthly["period"].astype(str)

        city_monthly = base.groupby("period", as_index=False).agg(aqi=("aqi_daily", "mean"))
        city_monthly["month_str"] = city_monthly["period"].astype(str)
        return monthly, city_monthly

    @output
    @render.ui
    def selection_hint():
        selected = selected_districts()
        if not selected:
            return ui.div("No districts selected; maps stay in context mode.", class_="selection-hint")
        mdf = map_data()
        if mdf.empty:
            return ui.div()
        focus = mdf[mdf["district"].isin(selected)].copy()
        city_avg = float(mdf["aqi_daily"].mean())
        focus_avg = float(focus["aqi_daily"].mean()) if not focus.empty else np.nan
        if pd.isna(focus_avg):
            return ui.div()
        delta = focus_avg - city_avg
        direction = "above" if delta >= 0 else "below"
        return ui.div(
            ui.HTML(
                f"Linked focus: <strong>{len(selected)}</strong> district(s), "
                f"avg <strong>{focus_avg:.0f}</strong> AQI "
                f"({abs(delta):.0f} {direction} city avg)."
            ),
            class_="selection-hint",
        )

    @output
    @render.ui
    def choropleth():
        mdf = map_data()
        if mdf.empty:
            return _plotly_html(_blank("No district data"))

        selected = set(selected_districts())
        if input.map_view() == "2D":
            return _plotly_html(_district_2d_figure(mdf, selected))

        district_geojson = _district_3d_geojson(mdf, selected)
        if district_geojson is None:
            return _plotly_html(_district_2d_figure(mdf, selected))

        srcdoc = _district_map_srcdoc(district_geojson, len(selected), period_label())
        return ui.tags.iframe(
            srcdoc=srcdoc,
            class_="hanoi-3d-map hanoi-3d-map-large",
            title="Interactive 3D Hanoi district AQI map",
            loading="lazy",
        )

    @output
    @render.ui
    def ranking_table_ui():
        df_period = filtered()
        df_context = year_filtered()
        if df_period.empty:
            return ui.div("No data", style="color:#6b7280;")

        df_context = df_context.copy()
        df_context["month"] = df_context["time"].dt.month
        monthly = df_context.groupby(["district", "month"], as_index=False)["aqi_daily"].mean()
        monthly_lookup = monthly.pivot(index="district", columns="month", values="aqi_daily")
        period_avg = df_period.groupby("district", as_index=False)["aqi_daily"].mean()
        period_avg = period_avg.sort_values("aqi_daily", ascending=False).reset_index(drop=True)
        period_avg["rank"] = range(1, len(period_avg) + 1)
        selected = selected_districts()
        if not selected:
            return ui.div("No district selected. Use Select all or tick districts to populate the ranking.", class_="ranking-empty")
        period_avg = period_avg[period_avg["district"].isin(selected)]

        # Build HTML table
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        selected_month = None if input.month() == "All" else int(input.month())
        avg_header = "Avg" if selected_month is None else f"{months[selected_month - 1]} avg"
        header = f"<tr><th>Rank</th><th>District</th><th>{avg_header}</th>"
        header += "".join(
            f'<th class="month-selected">{m}</th>' if selected_month == idx else f"<th>{m}</th>"
            for idx, m in enumerate(months, start=1)
        )
        header += "</tr>"

        rows = []
        for _, row in period_avg.iterrows():
            dist = row["district"]
            avg = row["aqi_daily"]
            r = f'<tr><td>{row["rank"]}</td><td>{dist}</td>'
            r += f'<td><span style="{_aqi_bg_style(avg)}">{avg:.0f}</span></td>'
            for m in range(1, 13):
                cell_class = ' class="month-selected"' if selected_month == m else ""
                val = monthly_lookup.loc[dist, m] if dist in monthly_lookup.index and m in monthly_lookup.columns else np.nan
                if not pd.isna(val):
                    r += f'<td{cell_class}><span style="{_aqi_bg_style(val)}">{val:.0f}</span></td>'
                else:
                    r += f'<td{cell_class} style="color:#6b7280;">—</td>'
            r += "</tr>"
            rows.append(r)

        html = f'<div class="ranking-scroll"><table class="ranking-table">{header}{"".join(rows)}</table></div>'
        return ui.HTML(html)

    @output
    @render.ui
    def district_insight():
        selected = selected_districts()
        df = filtered()
        if df.empty:
            return ui.div()
        if not selected:
            city_avg = df["aqi_daily"].mean()
            return ui.div(
                ui.div("WHAT THIS SHOWS", class_="insight-label"),
                ui.p(ui.HTML(
                    f"No district is selected for <span class='insight-soft'>{period_label()}</span>. "
                    "The map keeps Hanoi in a muted context layer; "
                    f"city-wide average is <span class='insight-highlight'>{city_avg:.0f} AQI</span>."
                )),
                class_="insight-box",
            )
        if len(selected) == len(DISTRICT_CHOICES):
            city_avg = df["aqi_daily"].mean() if not df.empty else 0
            return ui.div(
                ui.div("WHAT THIS SHOWS", class_="insight-label"),
                ui.p(ui.HTML(
                    f"For <span class='insight-soft'>{period_label()}</span>, the map shows average AQI across Hanoi's "
                    f"<span class='insight-highlight'>30 districts</span>. City-wide average is "
                    f"<span class='insight-highlight'>{city_avg:.0f} AQI</span>. Untick districts to isolate local AQI hotspots."
                )),
                class_="insight-box",
            )
        dist_data = df[df["district"].isin(selected)]
        dist_avg = dist_data["aqi_daily"].mean() if not dist_data.empty else 0
        city_avg = df["aqi_daily"].mean()
        pct = (dist_avg - city_avg) / city_avg * 100 if city_avg > 0 else 0
        direction = "above" if pct > 0 else "below"
        label = selected[0] if len(selected) == 1 else f"{len(selected)} selected districts"
        return ui.div(
            ui.div("DISTRICT INSIGHT", class_="insight-label"),
            ui.p(ui.HTML(
                f"For <span class='insight-soft'>{period_label()}</span>, {label}' average AQI "
                f"(<span class='insight-highlight'>{dist_avg:.0f}</span>) is "
                f"<span class='insight-highlight'>{abs(pct):.0f}%</span> {direction} the city average "
                f"(<span class='insight-soft'>{city_avg:.0f}</span>). Category: "
                f"<span class='insight-highlight'>{aqi_category(dist_avg)}</span>."
            )),
            class_="insight-box",
        )

    @output
    @render.ui
    def district_trend():
        selected = selected_districts()
        if not selected:
            return _plotly_html(_blank("Tick one or more districts"))

        monthly, city_monthly = monthly_trend_data()
        if monthly.empty:
            return _plotly_html(_blank("No data for selected districts"))

        selected_monthly = monthly[monthly["district"].isin(selected)].copy()
        if selected_monthly.empty:
            return _plotly_html(_blank("No data for selected districts"))

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(city_monthly["month_str"]), y=list(city_monthly["aqi"]),
            mode="lines",
            line={"color": "rgba(232,234,237,0.58)", "width": 2.4, "dash": "dot"},
            name="City avg",
            hovertemplate="City avg<br>%{x}: %{y:.1f} AQI<extra></extra>",
        ))

        district_order_all = (
            selected_monthly.groupby("district", as_index=False)["aqi"]
            .mean()
            .sort_values("aqi", ascending=False)["district"]
            .tolist()
        )
        dense = len(district_order_all) > 12
        district_order = district_order_all
        palette = px.colors.qualitative.Dark24 + px.colors.qualitative.Set3
        for idx, district in enumerate(district_order):
            one = selected_monthly[selected_monthly["district"] == district]
            if one.empty:
                continue
            fig.add_trace(go.Scatter(
                x=list(one["month_str"]), y=list(one["aqi"]),
                mode="lines" if dense else "lines+markers",
                line={
                    "color": palette[idx % len(palette)],
                    "width": 1.55 if dense else 2.5,
                },
                marker={"size": 4 if not dense else 0},
                opacity=0.62 if dense else 0.9,
                name=district,
                showlegend=True,
                hovertemplate=f"{district}<br>%{{x}}: %{{y:.1f}} AQI<extra></extra>",
            ))
        notes = []
        if dense:
            notes.append(f"{len(district_order)} districts selected · all rendered from cached monthly aggregates")
        if input.month() != "All":
            notes.append(f"Map and ranking filtered to {MONTH_CHOICES.get(str(input.month()), 'selected month')}; trend keeps year context")
        if notes:
            fig.add_annotation(
                text=" · ".join(notes),
                x=0.01, y=1.06, xref="paper", yref="paper",
                showarrow=False,
                font={"size": 11, "color": "#9aa0a6"},
                align="left",
            )
        fig.update_xaxes(title="", tickangle=45)
        fig.update_yaxes(title="AQI")
        fig.update_layout(
            showlegend=True,
            legend={
                "font": {"color": "#9aa0a6", "size": 10},
                "orientation": "h",
                "x": 0.5,
                "xanchor": "center",
                "y": -0.42,
                "yanchor": "top",
                "bgcolor": "rgba(0,0,0,0)",
            },
            margin={"l": 8, "r": 8, "t": 36, "b": 92},
            transition={"duration": 350, "easing": "cubic-in-out"},
        )
        return _plotly_html(_dark_fig(fig, height=320))

    @output
    @render.ui
    def pollutant_breakdown():
        selected = selected_districts()
        df = filtered()
        if not selected:
            return _plotly_html(_blank("Tick one or more districts"))
        if len(selected) != len(DISTRICT_CHOICES):
            df = df[df["district"].isin(selected)]
        if df.empty:
            return _plotly_html(_blank())

        pollutants = {
            "PM2.5": "aqi_pm2_5", "PM10": "aqi_pm10",
            "NO₂": "aqi_nitrogen_dioxide", "O₃": "aqi_ozone",
            "SO₂": "aqi_sulphur_dioxide", "CO": "aqi_carbon_monoxide",
        }
        rows = []
        for label, col in pollutants.items():
            if col in df.columns:
                val = df[col].mean()
                if not pd.isna(val) and np.isfinite(val):
                    rows.append({"pollutant": label, "value": float(val)})
        if not rows:
            return _plotly_html(_blank("No pollutant data"))
        pdf = pd.DataFrame(rows).sort_values("value", ascending=True)
        fig = px.bar(pdf, x="value", y="pollutant", orientation="h",
                     color="value", color_continuous_scale="Tealgrn")
        fig.update_layout(xaxis_title="Average AQI", yaxis_title="", coloraxis_showscale=False)
        return _plotly_html(_dark_fig(fig, height=320))
