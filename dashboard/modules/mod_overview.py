"""Overview page — hero card, day/night trend, district quick‑cards, station map."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from shiny import module, reactive, render, ui

from src.utils import AQI_BANDS, aqi_advisory, aqi_category, aqi_color, sanitize_figure

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
GEOJSON_PATH = APP_ROOT / "data" / "hanoi_districts.geojson"
if not GEOJSON_PATH.exists():
    GEOJSON_PATH = REPO_ROOT / "data" / "hanoi_districts.geojson"

OVERVIEW_TEAL_PALETTE = [
    "#0d5f66", "#167b72", "#219a75", "#0b4656", "#1d856c",
    "#2fb27f", "#124f63", "#247a78", "#37a86f", "#0f6f7d",
]


def _dark_fig(fig: go.Figure, height: int = 360) -> go.Figure:
    existing_margin = fig.layout.margin.to_plotly_json() if fig.layout.margin else None
    fig.update_layout(
        height=height,
        margin=existing_margin or {"l": 8, "r": 8, "t": 8, "b": 8},
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


def _recent_aqi(city_hourly: pd.DataFrame) -> pd.DataFrame:
    if city_hourly.empty or "aqi" not in city_hourly.columns or "local_time" not in city_hourly.columns:
        return pd.DataFrame()
    recent = city_hourly[["local_time", "aqi"]].copy()
    recent["aqi"] = pd.to_numeric(recent["aqi"], errors="coerce")
    recent = recent.dropna(subset=["local_time", "aqi"]).sort_values("local_time").tail(24)
    if recent.empty:
        return recent
    recent["period"] = np.where(recent["local_time"].dt.hour.between(6, 17), "Day", "Night")
    return recent


def _recent_realtime_aqi(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty or "aqi" not in history.columns or "local_time" not in history.columns:
        return pd.DataFrame()
    recent = history.copy()
    recent["local_time"] = pd.to_datetime(recent["local_time"], errors="coerce")
    recent["aqi"] = pd.to_numeric(recent["aqi"], errors="coerce")
    recent = recent.dropna(subset=["local_time", "aqi"]).sort_values("local_time")
    if recent.empty:
        return recent
    cutoff = recent["local_time"].max() - pd.Timedelta(hours=24)
    recent = recent[recent["local_time"] >= cutoff].copy()
    recent["period"] = np.where(recent["local_time"].dt.hour.between(6, 17), "Day", "Night")
    return recent


def _time_label(ts: pd.Timestamp) -> str:
    if pd.isna(ts):
        return "unknown time"
    return pd.Timestamp(ts).strftime("%I %p").lstrip("0")


def _date_label(ts: pd.Timestamp) -> str:
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%d %b")


def _snapshot_aqi(snapshot_value: dict | None, city_hourly: pd.DataFrame) -> float | None:
    aqi = snapshot_value.get("aqi") if isinstance(snapshot_value, dict) else None
    if aqi is None or pd.isna(aqi):
        latest = city_hourly["aqi"].dropna() if "aqi" in city_hourly.columns else pd.Series(dtype=float)
        aqi = latest.iloc[-1] if not latest.empty else None
    if aqi is None or pd.isna(aqi):
        return None
    return float(aqi)


def _one_hour_prediction(prediction_context: Callable | None) -> float | None:
    if prediction_context is None:
        return None
    try:
        ctx = prediction_context(1, "aqi", "cleaned")
    except Exception:
        return None
    pred = ctx.get("pred") if isinstance(ctx, dict) else None
    try:
        pred = float(pred)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(pred):
        return None
    return pred


@lru_cache(maxsize=1)
def _load_hanoi_geojson() -> dict | None:
    if not GEOJSON_PATH.exists():
        return None
    with open(GEOJSON_PATH) as f:
        return json.load(f)


def _rgba_from_aqi(aqi: float | None, alpha: int = 210) -> list[int]:
    color = aqi_color(aqi)
    if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
        return [79, 195, 247, alpha]
    return [int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16), alpha]


def _rgba_from_hex(color: str, alpha: int = 222) -> list[int]:
    if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
        return [180, 210, 255, alpha]
    return [int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16), alpha]


def _district_reference_color(district: str | None, idx: int) -> list[int]:
    color = OVERVIEW_TEAL_PALETTE[idx % len(OVERVIEW_TEAL_PALETTE)]
    return _rgba_from_hex(color, 236)


def _district_3d_geojson(district_frame: pd.DataFrame, city_aqi: float | None) -> dict | None:
    geojson = _load_hanoi_geojson()
    if geojson is None:
        return None

    values: dict[str, dict[str, Any]] = {}
    if not district_frame.empty and {"district", "aqi_daily"}.issubset(district_frame.columns):
        for _, row in district_frame.iterrows():
            district = row.get("district")
            aqi = pd.to_numeric(row.get("aqi_daily"), errors="coerce")
            if isinstance(district, str) and not pd.isna(aqi):
                values[district] = {
                    "aqi": float(aqi),
                    "category": aqi_category(float(aqi)),
                    "elevation": 0,
                }

    fallback_aqi = city_aqi if city_aqi is not None and not pd.isna(city_aqi) else 80.0
    fallback = {
        "aqi": float(fallback_aqi),
        "category": aqi_category(float(fallback_aqi)),
        "elevation": 0,
    }

    features = []
    for idx, feature in enumerate(geojson.get("features", [])):
        props = dict(feature.get("properties", {}))
        name = props.get("district_ascii") or props.get("shapeName")
        metrics = values.get(name, fallback)
        props.update({
            "district": name,
            "mapRole": "district-reference",
            "aqi": round(metrics["aqi"], 1),
            "category": metrics["category"],
            "fillColor": _district_reference_color(name, idx),
            "lineColor": [141, 234, 202, 220],
            "elevation": metrics["elevation"],
        })
        new_feature = dict(feature)
        new_feature["properties"] = props
        features.append(new_feature)
    return {"type": "FeatureCollection", "features": features}


def _station_3d_rows(stations: list[dict[str, Any]], snapshot_value: dict | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, station in enumerate(stations or []):
        try:
            lat = float(station.get("lat"))
            lon = float(station.get("lon"))
            aqi = float(station.get("aqi"))
        except (TypeError, ValueError):
            continue
        rows.append({
            "name": station.get("name", "AQI station"),
            "lat": lat,
            "lon": lon,
            "aqi": aqi,
            "category": aqi_category(aqi),
            "color": _rgba_from_aqi(aqi, 245),
            "elevation": max(1100.0, min(6200.0, aqi * 28.0)),
            "label": f"AQI {aqi:.0f}",
            "labelOffset": [0, -18 - (idx % 3) * 12],
        })

    if rows:
        return rows

    snap = snapshot_value if isinstance(snapshot_value, dict) else {}
    aqi = snap.get("aqi")
    try:
        aqi = float(aqi)
    except (TypeError, ValueError):
        aqi = 80.0
    return [{
        "name": snap.get("name", "Hanoi center"),
        "lat": float(snap.get("lat", 21.0245)),
        "lon": float(snap.get("lon", 105.8412)),
        "aqi": aqi,
        "category": aqi_category(aqi),
        "color": _rgba_from_aqi(aqi, 245),
        "elevation": max(1100.0, min(6200.0, aqi * 28.0)),
        "label": f"AQI {aqi:.0f}",
        "labelOffset": [0, -18],
    }]


def _deck_map_srcdoc(geojson: dict, stations: list[dict[str, Any]], source_label: str) -> str:
    geojson_js = json.dumps(geojson, ensure_ascii=False)
    stations_js = json.dumps(stations, ensure_ascii=False)
    source_js = json.dumps(source_label, ensure_ascii=False)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    html, body, #deck-map {{
      width: 100%;
      height: 100%;
      margin: 0;
      overflow: hidden;
      position: relative;
      background:
        radial-gradient(circle at 72% 20%, rgba(89, 230, 205, 0.26), transparent 26%),
        radial-gradient(circle at 18% 82%, rgba(54, 156, 153, 0.24), transparent 30%),
        linear-gradient(145deg, #062734 0%, #0b5f64 48%, #05131f 100%);
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    #deck-map::before {{
      content: "";
      position: absolute;
      inset: -18%;
      pointer-events: none;
      opacity: 0.20;
      background:
        repeating-radial-gradient(circle at 78% 28%,
          transparent 0 32px,
          rgba(151, 255, 222, 0.32) 33px 36px,
          transparent 37px 56px),
        conic-gradient(from 8deg at 78% 28%,
          transparent 0 7deg,
          rgba(151, 255, 222, 0.24) 7deg 10deg,
          transparent 10deg 22deg,
          rgba(151, 255, 222, 0.18) 22deg 25deg,
          transparent 25deg 45deg);
    }}
    #deck-map::after {{
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      opacity: 0.16;
      background:
        linear-gradient(90deg, rgba(157, 255, 227, 0.36) 1px, transparent 1px) 0 0 / 72px 72px,
        linear-gradient(0deg, rgba(157, 255, 227, 0.22) 1px, transparent 1px) 0 0 / 72px 72px,
        repeating-linear-gradient(135deg, transparent 0 34px, rgba(157, 255, 227, 0.13) 35px 37px, transparent 38px 72px);
      mix-blend-mode: screen;
    }}
    .map-title {{
      position: absolute;
      left: 12px;
      top: 12px;
      z-index: 5;
      color: #eafff7;
      font-weight: 900;
      font-size: 12px;
      letter-spacing: 0.02em;
      padding: 8px 10px;
      border: 1px solid rgba(141,234,202,0.42);
      border-radius: 999px;
      background: rgba(4,31,43,0.78);
      backdrop-filter: blur(8px);
    }}
    .map-legend {{
      position: absolute;
      left: 12px;
      bottom: 12px;
      z-index: 5;
      color: #d7fff0;
      font-size: 11px;
      line-height: 1.35;
      padding: 9px 10px;
      border: 1px solid rgba(141,234,202,0.28);
      border-radius: 10px;
      background: rgba(4,25,35,0.78);
      backdrop-filter: blur(8px);
    }}
    .map-legend strong {{ color: #9dffe3; }}
    .deck-tooltip {{
      color: #effff9 !important;
      background: rgba(3,28,38,0.94) !important;
      border: 1px solid rgba(141,234,202,0.42) !important;
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
  <div id="deck-map"></div>
  <div id="fallback" class="map-fallback">Loading interactive 3D Hanoi AQI map...</div>
  <div class="map-title">3D Hanoi AQI · {source_label}</div>
  <div class="map-legend"><strong>Columns</strong> = live station AQI<br><strong>Cool teal base</strong> = Hanoi district context<br><strong>Landmark</strong> = VinUni, Gia Lam</div>
  <script>
    const geojson = {geojson_js};
    const stations = {stations_js};
    const sourceLabel = {source_js};
    const fallback = document.getElementById('fallback');

    if (!window.deck) {{
      fallback.textContent = 'The 3D map library could not load. The AQI data is still available in the surrounding cards.';
    }} else {{

    const districtLayer = new deck.GeoJsonLayer({{
      id: 'hanoi-district-extrusion',
      data: geojson,
      pickable: true,
      stroked: true,
      filled: true,
      extruded: false,
      wireframe: false,
      getFillColor: f => f.properties.fillColor,
      getLineColor: f => f.properties.lineColor || [141, 234, 202, 220],
      getLineWidth: 66,
      lineWidthUnits: 'meters',
      material: {{
        ambient: 0.62,
        diffuse: 0.46,
        shininess: 22,
        specularColor: [176, 255, 226]
      }}
    }});

    const VINUNI = {{lon: 105.94361111111, lat: 20.989305555556}};
    const VINUNI_SCALE = 7.0;
    const lonMeters = 103200;
    const latMeters = 111000;
    function footprint(cx, cy, widthM, heightM, angleDeg = -5) {{
      const angle = angleDeg * Math.PI / 180;
      const corners = [
        [-widthM / 2, -heightM / 2],
        [ widthM / 2, -heightM / 2],
        [ widthM / 2,  heightM / 2],
        [-widthM / 2,  heightM / 2],
      ];
      return corners.map(([x, y]) => {{
        const xr = x * Math.cos(angle) - y * Math.sin(angle);
        const yr = x * Math.sin(angle) + y * Math.cos(angle);
        return [cx + xr / lonMeters, cy + yr / latMeters];
      }});
    }}
    const vinuniBlocks = [
      {{name: 'VinUni plaza', polygon: footprint(VINUNI.lon, VINUNI.lat - 0.00008, 360 * VINUNI_SCALE, 112 * VINUNI_SCALE), elevation: 70, color: [204, 184, 128, 150]}},
      {{name: 'VinUni main hall', polygon: footprint(VINUNI.lon, VINUNI.lat, 260 * VINUNI_SCALE, 46 * VINUNI_SCALE), elevation: 720, color: [246, 238, 211, 252]}},
      {{name: 'VinUni left wing', polygon: footprint(VINUNI.lon - 0.00155 * VINUNI_SCALE, VINUNI.lat - 0.00014 * VINUNI_SCALE, 112 * VINUNI_SCALE, 56 * VINUNI_SCALE), elevation: 510, color: [235, 225, 202, 245]}},
      {{name: 'VinUni right wing', polygon: footprint(VINUNI.lon + 0.00155 * VINUNI_SCALE, VINUNI.lat + 0.00014 * VINUNI_SCALE, 112 * VINUNI_SCALE, 56 * VINUNI_SCALE), elevation: 510, color: [235, 225, 202, 245]}},
      {{name: 'VinUni central block', polygon: footprint(VINUNI.lon, VINUNI.lat, 92 * VINUNI_SCALE, 76 * VINUNI_SCALE), elevation: 1180, color: [255, 247, 222, 255]}},
      {{name: 'VinUni tower base', polygon: footprint(VINUNI.lon, VINUNI.lat + 0.00046 * VINUNI_SCALE, 44 * VINUNI_SCALE, 42 * VINUNI_SCALE), elevation: 1780, color: [255, 248, 226, 255]}},
      {{name: 'VinUni tower', polygon: footprint(VINUNI.lon, VINUNI.lat + 0.00074 * VINUNI_SCALE, 28 * VINUNI_SCALE, 30 * VINUNI_SCALE), elevation: 2440, color: [255, 250, 232, 255]}},
    ];

    const vinuniLayer = new deck.PolygonLayer({{
      id: 'vinuni-landmark-building',
      data: vinuniBlocks,
      pickable: true,
      extruded: true,
      wireframe: false,
      getPolygon: d => d.polygon,
      getElevation: d => d.elevation,
      getFillColor: d => d.color,
      getLineColor: [255, 255, 255, 210],
      getLineWidth: 78,
      lineWidthUnits: 'meters',
      material: {{
        ambient: 0.52,
        diffuse: 0.58,
        shininess: 58,
        specularColor: [255, 250, 230]
      }}
    }});

    const vinuniSpireLayer = new deck.ColumnLayer({{
      id: 'vinuni-spire',
      data: [{{name: 'VinUni tower spire', lon: VINUNI.lon, lat: VINUNI.lat + 0.00092 * VINUNI_SCALE, elevation: 3550}}],
      diskResolution: 8,
      radius: 92,
      elevationScale: 1,
      extruded: true,
      pickable: true,
      getPosition: d => [d.lon, d.lat],
      getElevation: d => d.elevation,
      getFillColor: [246, 210, 90, 255],
      getLineColor: [255, 255, 230, 255],
      stroked: true,
      lineWidthMinPixels: 1
    }});

    const vinuniGlowLayer = new deck.ScatterplotLayer({{
      id: 'vinuni-spire-glow',
      data: [{{name: 'VinUni', lon: VINUNI.lon, lat: VINUNI.lat + 0.00092 * VINUNI_SCALE, elevation: 3800}}],
      billboard: true,
      pickable: false,
      getPosition: d => [d.lon, d.lat, d.elevation],
      getRadius: 430,
      radiusUnits: 'meters',
      getFillColor: [255, 225, 95, 155],
      getLineColor: [255, 255, 210, 230],
      stroked: true,
      lineWidthMinPixels: 1
    }});

    const vinuniLabelLayer = new deck.TextLayer({{
      id: 'vinuni-label',
      data: [{{lon: VINUNI.lon + 0.0028 * VINUNI_SCALE, lat: VINUNI.lat + 0.0027 * VINUNI_SCALE, elevation: 5200, label: 'VinUni\\nGia Lam'}}],
      billboard: true,
      pickable: true,
      getPosition: d => [d.lon, d.lat, d.elevation],
      getText: d => d.label,
      getSize: 14,
      sizeUnits: 'pixels',
      getColor: [255, 252, 235, 255],
      getTextAnchor: 'middle',
      getAlignmentBaseline: 'center',
      background: true,
      getBackgroundColor: [8, 12, 18, 215],
      backgroundPadding: [6, 4],
      getBorderColor: [246, 210, 90, 170],
      getBorderWidth: 1,
      fontWeight: 900
    }});

    const stationLayer = new deck.ColumnLayer({{
      id: 'live-station-columns',
      data: stations,
      diskResolution: 24,
      radius: 420,
      elevationScale: 1,
      extruded: true,
      pickable: true,
      autoHighlight: true,
      getPosition: d => [d.lon, d.lat],
      getElevation: d => d.elevation,
      getFillColor: d => d.color,
      getLineColor: [255, 255, 255, 210],
      stroked: true,
      lineWidthMinPixels: 1
    }});

    const stationTopLayer = new deck.ScatterplotLayer({{
      id: 'live-station-top-markers',
      data: stations,
      pickable: true,
      billboard: true,
      getPosition: d => [d.lon, d.lat, d.elevation + 90],
      getRadius: 470,
      radiusUnits: 'meters',
      getFillColor: d => d.color,
      getLineColor: [255, 255, 255, 245],
      stroked: true,
      lineWidthMinPixels: 2
    }});

    const stationLabelLayer = new deck.TextLayer({{
      id: 'live-station-labels',
      data: stations,
      pickable: true,
      billboard: true,
      getPosition: d => [d.lon, d.lat, d.elevation + 520],
      getText: d => `${{d.label}}\\n${{d.category}}`,
      getSize: 10,
      sizeUnits: 'pixels',
      getPixelOffset: d => d.labelOffset || [0, -18],
      getColor: [245, 250, 255, 255],
      getTextAnchor: 'middle',
      getAlignmentBaseline: 'center',
      background: true,
      getBackgroundColor: [8, 12, 18, 205],
      backgroundPadding: [5, 3],
      getBorderColor: [79, 195, 247, 150],
      getBorderWidth: 1,
      fontWeight: 800
    }});

    const deckInstance = new deck.Deck({{
      parent: document.getElementById('deck-map'),
      initialViewState: {{
        longitude: 105.89,
        latitude: 21.015,
        zoom: 9.72,
        pitch: 58,
        bearing: 30
      }},
      controller: true,
      views: [new deck.MapView({{repeat: false}})],
      layers: [
        districtLayer,
        vinuniLayer,
        vinuniSpireLayer,
        vinuniGlowLayer,
        vinuniLabelLayer,
        stationLayer,
        stationTopLayer,
        stationLabelLayer
      ],
      getTooltip: (info) => {{
        const object = info.object;
        if (!object) return null;
        const p = object.properties || object;
        const label = p.district || p.name || 'Hanoi';
        if (p.mapRole === 'district-reference') {{
          return {{
            html: `<strong>${{label}}</strong><br><span style="color:#9dffe3">Cool teal district context</span><br><span style="color:#d7fff0">Realtime AQI is shown by station columns.</span>`
          }};
        }}
        const aqi = Number(p.aqi || 0).toFixed(0);
        const category = p.category || 'Unknown';
        return {{
          html: `<strong>${{label}}</strong><br>AQI ${{aqi}} · ${{category}}<br><span style="color:#9dffe3">${{sourceLabel}}</span>`
        }};
      }}
    }});
    fallback.style.display = 'none';
    }}
  </script>
</body>
</html>"""


# ── UI ──────────────────────────────────────────────────────────────────────────

@module.ui
def overview_ui():
    return ui.TagList(
        # Hero
        ui.div(
            ui.tags.img(src="hanoi_skyline.png", class_="hero-skyline"),
            ui.div(
                # AQI block
                ui.div(
                    ui.div("● LIVE", style="font-size:0.7rem;font-weight:700;color:#d1495b;margin-bottom:6px;letter-spacing:0.08em;"),
                    ui.output_ui("hero_aqi_value"),
                    ui.div("AQI (US)", class_="hero-aqi-label"),
                    ui.output_ui("hero_category"),
                    class_="hero-aqi-block",
                    role="status",
                    **{"aria-live": "polite", "aria-atomic": "true"},
                ),
                # Info
                ui.div(
                    ui.h2("Hanoi Air Quality Index"),
                    ui.p(ui.output_text("hero_subtitle"), style="color:#9aa0a6;font-size:0.9rem;margin:0;"),
                    # AQI scale bar
                    ui.div(
                        ui.tags.span(style="background:#2bb673"),
                        ui.tags.span(style="background:#f5b700"),
                        ui.tags.span(style="background:#f28f3b"),
                        ui.tags.span(style="background:#d1495b"),
                        ui.tags.span(style="background:#7b2cbf"),
                        ui.tags.span(style="background:#5a189a"),
                        ui.output_ui("aqi_scale_marker"),
                        class_="aqi-scale-bar",
                    ),
                    ui.div(
                        ui.tags.span("Good"), ui.tags.span("Moderate"), ui.tags.span("USG"),
                        ui.tags.span("Unhealthy"), ui.tags.span("Severe"), ui.tags.span("Hazardous"),
                        class_="aqi-scale-labels",
                    ),
                    class_="hero-info",
                ),
                # Weather
                ui.div(
                    ui.output_ui("hero_weather_card"),
                    class_="hero-weather-dock",
                ),
                class_="hero-content",
            ),
            class_="hero-card",
            role="region",
            **{"aria-label": "Realtime Hanoi air quality overview"},
        ),
        # Advisory insight
        ui.div(ui.output_ui("hero_insight"), role="status", **{"aria-live": "polite"}),
        # Day & Night + Station Map
        ui.div(
            ui.div(
                ui.h4("Realtime AQI History — Last 24 Hours"),
                ui.div(
                    ui.output_ui("daynight_plot"),
                    class_="accessible-chart",
                    role="figure",
                    **{"aria-label": "Line chart of Hanoi AQI over the last 24 hours, split into day and night periods."},
                ),
                ui.output_ui("daynight_summary"),
                ui.output_ui("hero_exposure_card"),
                class_="panel",
            ),
            ui.div(
                ui.div(
                    ui.h4("Hanoi AQI Map"),
                    ui.div(
                        ui.input_radio_buttons("map_view", None, choices=["3D", "2D"], selected="3D", inline=True),
                        ui.div(ui.output_ui("map_source_badge"), role="status", **{"aria-live": "polite"}),
                        class_="map-toolbar",
                    ),
                    class_="panel-title-row",
                ),
                ui.div(
                    ui.div(
                        ui.output_ui("map_plot"),
                        class_="station-map-frame accessible-chart",
                        role="figure",
                        **{"aria-label": "Interactive 3D Hanoi map with district height and color based on AQI, plus live station columns when available."},
                    ),
                    ui.output_ui("map_mascot_ui"),
                    class_="station-map-showcase",
                ),
                class_="panel map-panel",
            ),
            class_="grid-hero",
        ),
        # District quick cards
        ui.div(
            ui.div(
                ui.h4("District Snapshot — Top AQI"),
                ui.p("Average AQI across Hanoi's 30 districts in the latest data window.", style="color:#9aa0a6;font-size:0.85rem;margin:-6px 0 12px 0;"),
                class_="page-intro",
            ),
        ),
        ui.output_ui("district_cards_ui"),
    )


# ── Server ──────────────────────────────────────────────────────────────────────

@module.server
def overview_server(
    input, output, session,
    *,
    city_hourly: pd.DataFrame,
    station_cache: reactive.Value,
    snapshot: reactive.Value,
    realtime_history: reactive.Value,
    prediction_context: Callable | None,
    district_map_frame: Callable,
):
    @output
    @render.ui
    def hero_aqi_value():
        aqi = _snapshot_aqi(snapshot.get(), city_hourly)
        if aqi is None:
            return ui.div("—", class_="hero-aqi-number")
        color = aqi_color(aqi)
        return ui.div(str(int(aqi)), class_="hero-aqi-number", style=f"color:{color};")

    @output
    @render.ui
    def hero_category():
        aqi = _snapshot_aqi(snapshot.get(), city_hourly)
        category = aqi_category(aqi)
        color = aqi_color(aqi)
        return ui.div(category, class_="hero-category", style=f"color:{color};")

    @output
    @render.ui
    def aqi_scale_marker():
        aqi = _snapshot_aqi(snapshot.get(), city_hourly)
        if aqi is None:
            return ui.div()
        pct = min(max(aqi / 500 * 100, 0), 100)
        color = aqi_color(aqi)
        return ui.tags.span(class_="aqi-scale-marker", style=f"left:{pct}%;--marker-color:{color};")

    @output
    @render.text
    def hero_subtitle():
        snap = snapshot.get()
        ts = snap.get("time_iso", "N/A") if isinstance(snap, dict) else "N/A"
        source = snap.get("source", "Historical") if isinstance(snap, dict) else "Historical"
        return f"Real-time data from {source} · Last updated: {ts}"

    @output
    @render.ui
    def hero_weather_card():
        snap = snapshot.get()
        if not isinstance(snap, dict) or not snap:
            return ui.div()
        items = []
        for key, label, unit in [
            ("temp", "Temp", "°C"),
            ("humidity", "Humidity", "%"),
            ("wind", "Wind", "km/h"),
            ("pressure", "Pressure", "hPa"),
        ]:
            val = snap.get(key)
            if val is not None and not pd.isna(val):
                items.append(
                    ui.div(
                        ui.div(f"{float(val):.0f}{unit}", class_="weather-val"),
                        ui.div(label, class_="weather-lbl"),
                        class_="weather-item",
                    )
                )
        if not items:
            return ui.div()
        return ui.div(*items, class_="weather-card")

    @output
    @render.ui
    def hero_insight():
        snap = snapshot.get()
        aqi = snap.get("aqi") if isinstance(snap, dict) else None
        if aqi is None or pd.isna(aqi):
            latest = city_hourly["aqi"].dropna()
            aqi = latest.iloc[-1] if not latest.empty else None
        advisory = aqi_advisory(aqi)
        return ui.div(
            ui.div("WHAT THIS MEANS", class_="insight-label"),
            ui.p(advisory),
            class_="insight-box",
        )

    @output
    @render.ui
    def daynight_plot():
        recent = _recent_realtime_aqi(realtime_history.get())
        if recent.empty:
            return _plotly_html(_blank("Collecting realtime AQI history"))

        recent = recent.reset_index(drop=True)
        recent["plot_idx"] = np.arange(len(recent))
        pred_1h = _one_hour_prediction(prediction_context)
        pred_idx = len(recent)
        pred_time = recent["local_time"].iloc[-1] + pd.Timedelta(hours=1)
        fig = go.Figure()

        segments = []
        start = 0
        current_period = recent.loc[0, "period"]
        for idx in range(1, len(recent)):
            period = recent.loc[idx, "period"]
            if period != current_period:
                segments.append((start, idx - 1, current_period))
                start = idx
                current_period = period
        segments.append((start, len(recent) - 1, current_period))
        for start_idx, end_idx, period in segments:
            fill = "rgba(86,151,209,0.08)" if period == "Day" else "rgba(44,54,121,0.14)"
            fig.add_vrect(x0=start_idx - 0.5, x1=end_idx + 0.5, fillcolor=fill, line_width=0, layer="below")

        mode = "lines+markers" if len(recent) > 1 else "markers"
        fig.add_trace(go.Scatter(
            x=list(recent["plot_idx"]),
            y=list(recent["aqi"]),
            mode=mode,
            line={"color": "#f6d433", "width": 2.8, "shape": "spline", "smoothing": 0.85},
            marker={"size": 8 if len(recent) == 1 else 5, "color": "#f6d433", "line": {"width": 0}},
            fill="tozeroy",
            fillcolor="rgba(246,211,51,0.09)",
            name="AQI",
            customdata=np.stack([
                recent["local_time"].dt.strftime("%d %b, %H:%M"),
                recent["period"],
            ], axis=-1),
            hovertemplate="%{customdata[0]}<br>%{customdata[1]}<br>AQI %{y:.0f}<extra></extra>",
        ))

        if pred_1h is not None:
            fig.add_vline(
                x=pred_idx - 0.5,
                line={"color": "rgba(125,249,255,0.36)", "width": 1.4, "dash": "dot"},
            )
            fig.add_trace(go.Scatter(
                x=[recent["plot_idx"].iloc[-1], pred_idx],
                y=[recent["aqi"].iloc[-1], pred_1h],
                mode="lines",
                line={"color": "#7df9ff", "width": 3.0, "dash": "dash"},
                name="1h model prediction",
                hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=[pred_idx],
                y=[pred_1h],
                mode="markers+text",
                marker={
                    "symbol": "diamond",
                    "size": 12,
                    "color": "#7df9ff",
                    "line": {"color": "#0b1118", "width": 1.8},
                },
                text=["1h prediction"],
                textposition="top center",
                textfont={"color": "#7df9ff", "size": 11, "family": "Inter, system-ui, sans-serif"},
                name="1h model prediction",
                customdata=[[pred_time.strftime("%d %b, %H:%M"), "Model forecast"]],
                hovertemplate="<b>1h model prediction</b><br>%{customdata[0]}<br>AQI %{y:.0f}<br><span style='color:#9aa0a6'>Estimated, not observed</span><extra></extra>",
            ))
            fig.add_annotation(
                text="observed",
                x=0.02, y=1.03, xref="paper", yref="paper",
                showarrow=False,
                font={"size": 10, "color": "#f6d433"},
                align="left",
            )
            fig.add_annotation(
                text="forecast",
                x=0.98, y=1.03, xref="paper", yref="paper",
                showarrow=False,
                font={"size": 10, "color": "#7df9ff"},
                align="right",
            )

        fig.add_annotation(text="☀", x=0.31, y=0.78, xref="paper", yref="paper", showarrow=False, font={"size": 52, "color": "rgba(246,211,51,0.16)"})
        fig.add_annotation(text="☾", x=0.84, y=0.78, xref="paper", yref="paper", showarrow=False, font={"size": 52, "color": "rgba(148,163,255,0.18)"})
        fig.add_annotation(text="Day", x=0.30, y=0.96, xref="paper", yref="paper", showarrow=False, font={"size": 12, "color": "#9bdcff"})
        fig.add_annotation(text="Night", x=0.86, y=0.96, xref="paper", yref="paper", showarrow=False, font={"size": 12, "color": "#94a3ff"})
        if len(recent) == 1:
            fig.add_annotation(
                text="Collecting live AQI points every 10 minutes",
                x=0.5, y=0.08, xref="paper", yref="paper",
                showarrow=False,
                font={"size": 12, "color": "#9aa0a6"},
            )
        tick_idx = list(range(0, len(recent), 3))
        tick_vals = tick_idx.copy()
        tick_text = [recent.loc[i, "local_time"].strftime("%H:%M") for i in tick_idx]
        if pred_1h is not None:
            tick_vals.append(pred_idx)
            tick_text.append(f"{pred_time.strftime('%H:%M')} pred")
        fig.update_xaxes(
            title="Hour",
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_text,
            range=[-0.5, pred_idx + 0.5 if pred_1h is not None else len(recent) - 0.5],
        )
        fig.update_yaxes(title="AQI")
        fig.update_layout(
            showlegend=pred_1h is not None,
            hovermode="x unified",
            legend={
                "orientation": "h",
                "x": 1,
                "xanchor": "right",
                "y": 1.14,
                "yanchor": "bottom",
                "font": {"size": 10, "color": "#9aa0a6"},
                "bgcolor": "rgba(0,0,0,0)",
            },
            margin={"l": 8, "r": 8, "t": 42 if pred_1h is not None else 8, "b": 8},
        )
        return _plotly_html(_dark_fig(fig, height=260))

    @output
    @render.ui
    def daynight_summary():
        recent = _recent_realtime_aqi(realtime_history.get())
        if recent.empty:
            return ui.div(
                ui.div("REALTIME HISTORY", class_="insight-label"),
                ui.p("The deployed app has not collected a realtime AQI point yet. It starts recording after the first live refresh."),
                class_="insight-box day-night-note",
            )
        if len(recent) < 2:
            latest = recent.iloc[-1]
            pred = _one_hour_prediction(prediction_context)
            pred_sentence = (
                f" The <span class='insight-soft'>cyan diamond</span> marks the model's next-hour estimate: "
                f"<span class='insight-highlight'>{pred:.0f} AQI</span>, not an observed reading."
                if pred is not None else ""
            )
            return ui.div(
                ui.div("REALTIME HISTORY", class_="insight-label"),
                ui.p(ui.HTML(
                    f"First live AQI point recorded at <span class='insight-soft'>{_time_label(latest['local_time'])}</span>: "
                    f"<span class='insight-highlight'>{latest['aqi']:.0f}</span>. "
                    f"The trend line will become more informative as the app collects more refreshes.{pred_sentence}"
                )),
                class_="insight-box day-night-note",
            )

        day = recent[recent["period"] == "Day"]
        night = recent[recent["period"] == "Night"]
        day_max = day["aqi"].max() if not day.empty else np.nan
        day_min = day["aqi"].min() if not day.empty else np.nan
        night_max = night["aqi"].max() if not night.empty else np.nan
        night_min = night["aqi"].min() if not night.empty else np.nan
        day_avg = day["aqi"].mean() if not day.empty else np.nan
        night_avg = night["aqi"].mean() if not night.empty else np.nan
        peak = recent.loc[recent["aqi"].idxmax()]
        low = recent.loc[recent["aqi"].idxmin()]
        delta = recent["aqi"].iloc[-1] - recent["aqi"].iloc[0]
        if abs(delta) < 5:
            trend_text = "roughly stable"
        elif delta > 0:
            trend_text = f"up by {delta:.0f} points"
        else:
            trend_text = f"down by {abs(delta):.0f} points"
        pred = _one_hour_prediction(prediction_context)
        pred_sentence = (
            f" The <span class='insight-soft'>cyan dashed segment and diamond</span> show the model's 1-hour forecast "
            f"(<span class='insight-highlight'>{pred:.0f} AQI</span>), separated from observed history."
            if pred is not None else ""
        )

        def summary_card(label: str, max_val: float, min_val: float, avg_val: float, class_name: str):
            return ui.div(
                ui.div(label, class_="dn-label"),
                ui.div(f"{max_val:.0f}" if not pd.isna(max_val) else "—", class_="dn-value"),
                ui.div(
                    f"Avg {avg_val:.0f} · Low {min_val:.0f}" if not pd.isna(avg_val) and not pd.isna(min_val) else "",
                    class_="dn-detail",
                ),
                class_=class_name,
            )

        return ui.div(
            ui.div(
                summary_card("☀ Daytime Peak", day_max, day_min, day_avg, "day-summary"),
                summary_card("☾ Nighttime Peak", night_max, night_min, night_avg, "night-summary"),
                class_="day-night-container",
            ),
            ui.div(
                ui.div("WHAT THIS SHOWS", class_="insight-label"),
                ui.p(ui.HTML(
                    f"In the app's collected <span class='insight-highlight'>realtime 24-hour history</span>, Hanoi's AQI peaked at "
                    f"<span class='insight-highlight'>{peak['aqi']:.0f}</span> around "
                    f"<span class='insight-soft'>{_time_label(peak['local_time'])}</span> on {_date_label(peak['local_time'])}. "
                    f"The lowest point was <span class='insight-good'>{low['aqi']:.0f}</span> around "
                    f"<span class='insight-soft'>{_time_label(low['local_time'])}</span>. "
                    f"Compared with the first hour, the latest reading is <span class='insight-highlight'>{trend_text}</span>."
                    f"{pred_sentence}"
                )),
                class_="insight-box day-night-note",
            ),
            class_="day-night-block",
        )

    @output
    @render.ui
    def map_source_badge():
        snap = snapshot.get()
        source = snap.get("source", "Historical") if isinstance(snap, dict) else "Historical"
        stations = station_cache.get()
        count = len(stations) if stations else 0
        if count:
            label = f"{count} live stations"
        else:
            label = source
        return ui.div(label, class_="map-source-badge")

    @output
    @render.ui
    def map_mascot_ui():
        snap = snapshot.get()
        aqi = snap.get("aqi") if isinstance(snap, dict) else None
        if aqi is None or pd.isna(aqi):
            latest = city_hourly["aqi"].dropna()
            aqi = latest.iloc[-1] if not latest.empty else None

        category = aqi_category(aqi)
        color = aqi_color(aqi)
        aqi_text = "—" if aqi is None or pd.isna(aqi) else f"{float(aqi):.0f}"
        source = snap.get("source", "Historical") if isinstance(snap, dict) else "Historical"
        mood_class = {
            "Good": "mood-good",
            "Moderate": "mood-moderate",
            "USG": "mood-usg",
            "Unhealthy": "mood-unhealthy",
            "Very Unhealthy": "mood-severe",
            "Hazardous": "mood-hazardous",
        }.get(category, "mood-unknown")
        message = {
            "Good": "Great air for a campus stroll.",
            "Moderate": "Pretty okay, but Lexce is keeping one eye on the air.",
            "USG": "Lexce suggests sensitive groups take it gently outside.",
            "Unhealthy": "Lexce is worried. Short trips and masks are smarter today.",
            "Very Unhealthy": "Lexce recommends staying indoors where possible.",
            "Hazardous": "Lexce says: indoor mode, windows closed, no outdoor exertion.",
        }.get(category, "Lexce is using the latest available Hanoi context.")

        return ui.div(
            ui.div(
                ui.div(ui.span("AQI"), ui.strong(aqi_text), class_="mascot-aqi-chip", style=f"--chip:{color};"),
                ui.div(
                    ui.div(
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
                        class_=f"vinuni-owl {mood_class}",
                    ),
                    class_="mascot-stage",
                ),
                ui.div(
                    ui.div("Lexce, AQI buddy", class_="mascot-name"),
                    ui.div(f"{category} · {source}", class_="mascot-status", style=f"color:{color};"),
                    ui.p(message),
                    class_=f"mascot-bubble {mood_class}",
                ),
                class_="map-mascot-card",
            ),
            class_="map-mascot-wrap",
            role="status",
            **{"aria-live": "polite", "aria-atomic": "true"},
        )

    @output
    @render.ui
    def hero_exposure_card():
        realtime = realtime_history.get().copy()
        if not realtime.empty and "pm25" in realtime.columns:
            realtime["pm25"] = pd.to_numeric(realtime["pm25"], errors="coerce")
            recent = realtime.dropna(subset=["pm25"]).tail(24)
            source_text = "realtime PM2.5"
        else:
            recent = pd.DataFrame()
            source_text = "historical PM2.5"
        if recent.empty:
            recent = city_hourly.copy()
            if recent.empty or "pm25" not in recent.columns:
                return ui.div()
            recent = recent.dropna(subset=["pm25"]).tail(24)
            source_text = "historical PM2.5 fallback"
        if recent.empty:
            return ui.div()

        pm25_avg = float(pd.to_numeric(recent["pm25"], errors="coerce").dropna().mean())
        if pd.isna(pm25_avg):
            return ui.div()
        cigs_day = max(0.0, pm25_avg / 22.0)

        return ui.div(
            ui.div(
                ui.div("24H PM2.5 EXPOSURE", class_="hero-exposure-label"),
                ui.div(
                    ui.span(f"{cigs_day:.1f}", class_="hero-exposure-value"),
                    ui.span("cigarettes/day", class_="hero-exposure-unit"),
                    class_="hero-exposure-main",
                ),
                ui.div(class_="cigarette-visual"),
                class_="hero-exposure-metric",
            ),
            ui.div(
                ui.HTML(
                    f"Based on <strong>{pm25_avg:.1f} µg/m³</strong> average {source_text}. "
                    "Berkeley Earth rule of thumb; not a medical diagnosis."
                ),
                class_="hero-exposure-copy",
            ),
            class_="hero-exposure-card",
        )

    @output
    @render.ui
    def map_plot():
        stations = station_cache.get()
        if input.map_view() == "2D":
            if stations:
                map_df = pd.DataFrame(stations)
                hover_data = {"aqi": ":.0f"}
                for col in ("category", "source", "time_iso", "pm25", "pm10", "dominant"):
                    if col in map_df.columns:
                        hover_data[col] = True
                fig = px.scatter_mapbox(
                    map_df, lat="lat", lon="lon",
                    color="aqi", size="aqi", size_max=18,
                    hover_name="name",
                    hover_data=hover_data,
                    color_continuous_scale="Turbo",
                    zoom=10.4, height=340,
                )
            else:
                fig = px.scatter_mapbox(
                    pd.DataFrame([{"name": "Hanoi Center", "lat": 21.0245, "lon": 105.8412}]),
                    lat="lat", lon="lon", hover_name="name", zoom=10.4, height=340,
                )
            fig.update_layout(
                mapbox_style="carto-darkmatter",
                margin={"l": 0, "r": 0, "t": 0, "b": 0},
                coloraxis_colorbar={"title": "AQI", "thickness": 10, "len": 0.6, "x": 0.98},
                paper_bgcolor="rgba(0,0,0,0)",
            )
            return _plotly_html(sanitize_figure(fig))

        snap = snapshot.get()
        city_aqi = _snapshot_aqi(snap, city_hourly)
        district_geojson = _district_3d_geojson(district_map_frame(), city_aqi)
        if district_geojson is None:
            return _plotly_html(_blank("No Hanoi district geometry"))

        source = snap.get("source", "Historical") if isinstance(snap, dict) else "Historical"
        source_label = "Live stations" if stations else source
        srcdoc = _deck_map_srcdoc(district_geojson, _station_3d_rows(stations, snap), source_label)
        return ui.tags.iframe(
            srcdoc=srcdoc,
            class_="hanoi-3d-map",
            title="Interactive 3D Hanoi AQI district map",
            loading="lazy",
        )

    @output
    @render.ui
    def district_cards_ui():
        df = district_map_frame()
        if df.empty:
            return ui.div("No district data available.", style="color:#6b7280;")
        top = df.nlargest(8, "aqi_daily")
        cards = []
        for _, row in top.iterrows():
            aqi_val = row["aqi_daily"]
            color = aqi_color(aqi_val)
            cards.append(
                ui.div(
                    ui.div(row["district"], class_="dc-name"),
                    ui.div(f"{aqi_val:.0f}", class_="dc-aqi", style=f"color:{color};"),
                    class_="district-card",
                    role="listitem",
                    **{"aria-label": f"{row['district']} district AQI {aqi_val:.0f}"},
                )
            )
        return ui.div(*cards, class_="district-cards", role="list", **{"aria-label": "Districts with the highest latest AQI"})
