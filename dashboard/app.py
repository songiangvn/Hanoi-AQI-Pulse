"""Hanoi Air Quality Pulse v2 — main Shiny application.

Story-driven, dark-themed, no-sidebar architecture with four pages:
  Overview | Districts | History | Forecast
"""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from shiny import App, reactive, render, ui

from modules.mod_overview import overview_ui, overview_server
from modules.mod_district import district_ui, district_server
from modules.mod_history import history_ui, history_server
from modules.mod_forecast import forecast_ui, forecast_server
from src.data import DataBundle, load_bundle
from src.model import ModelArtifacts, load_model_artifact, predict_next, save_model_artifact, train_city_model
from src.realtime_api import fetch_fresh_waqi_snapshot, fetch_open_meteo_snapshot, read_aqicn_token
from src.utils import aqi_category

# ── Paths & constants ─────────────────────────────────────────────────────────

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent if (APP_DIR.parent / "data").exists() else APP_DIR
DATA_ROOT = ROOT / "data"
PROCESSED_DIR = APP_DIR / "processed"
MODEL_DIR = APP_DIR / "models"
RUNTIME_DIR = APP_DIR / "runtime"
REALTIME_HISTORY_PATH = RUNTIME_DIR / "realtime_history.csv"
MAX_REALTIME_HISTORY_HOURS = 72
HF_REALTIME_DATASET_ID = os.getenv("HF_REALTIME_DATASET_ID", "MountainRiver/hanoi-aqi-realtime-history")
REALTIME_HISTORY_URL = os.getenv(
    "REALTIME_HISTORY_URL",
    f"https://huggingface.co/datasets/{HF_REALTIME_DATASET_ID}/resolve/main/realtime_history.csv",
)
REALTIME_HISTORY_COLUMNS = ["timestamp_utc", "local_time", "source", "name", "aqi", "pm25", "pm10", "lat", "lon"]
ENABLE_SESSION_NETWORK_REFRESH = os.getenv("ENABLE_SESSION_NETWORK_REFRESH", "0") == "1"

HANOI_LAT = 21.0245
HANOI_LON = 105.8412

HORIZONS = {"1h": 1, "6h": 6, "24h": 24}

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


# ── Helpers ──────────────────────────────────────────────────────────────────

def nearest_station(lat: float, lon: float, stations: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not stations:
        return None
    return min(stations, key=lambda s: (float(s["lat"]) - lat) ** 2 + (float(s["lon"]) - lon) ** 2)


def snapshot_overrides(snapshot: dict[str, Any] | None) -> dict[str, float]:
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


# ── Load data at module level ─────────────────────────────────────────────────

bundle: DataBundle = load_bundle(DATA_ROOT, processed_root=PROCESSED_DIR)
CITY = bundle.city_hourly.copy()
DISTRICT = bundle.district_daily.copy()
TOKEN = read_aqicn_token(ROOT)


def _snapshot_time(snapshot: dict[str, Any]) -> pd.Timestamp:
    raw_time = snapshot.get("time_iso")
    ts = pd.to_datetime(raw_time, errors="coerce", utc=True)
    if pd.isna(ts):
        ts = pd.Timestamp.now(tz="UTC")
    return ts


def _snapshot_history_row(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(snapshot, dict):
        return None
    source = str(snapshot.get("source", "Unknown"))
    if source == "Historical":
        return None
    aqi = pd.to_numeric(snapshot.get("aqi"), errors="coerce")
    if pd.isna(aqi):
        return None
    ts = _snapshot_time(snapshot)
    local = ts.tz_convert("Asia/Ho_Chi_Minh").tz_localize(None)
    return {
        "timestamp_utc": ts.isoformat(),
        "local_time": local.isoformat(),
        "source": source,
        "name": snapshot.get("name", "Hanoi realtime"),
        "aqi": float(aqi),
        "pm25": pd.to_numeric(snapshot.get("pm25"), errors="coerce"),
        "pm10": pd.to_numeric(snapshot.get("pm10"), errors="coerce"),
        "lat": pd.to_numeric(snapshot.get("lat", HANOI_LAT), errors="coerce"),
        "lon": pd.to_numeric(snapshot.get("lon", HANOI_LON), errors="coerce"),
    }


def _trim_realtime_history(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return history
    df = history.copy()
    df["local_time"] = pd.to_datetime(df["local_time"], errors="coerce")
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], errors="coerce", utc=True)
    df["aqi"] = pd.to_numeric(df["aqi"], errors="coerce")
    df = df.dropna(subset=["local_time", "timestamp_utc", "aqi"])
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=MAX_REALTIME_HISTORY_HOURS)
    df = df[df["timestamp_utc"] >= cutoff]
    df = df.sort_values("timestamp_utc")
    df = df.drop_duplicates(subset=["timestamp_utc", "source", "name"], keep="last")
    return df.reset_index(drop=True)


def _empty_realtime_history() -> pd.DataFrame:
    return pd.DataFrame(columns=REALTIME_HISTORY_COLUMNS)


def _load_remote_realtime_history() -> pd.DataFrame | None:
    if not REALTIME_HISTORY_URL:
        return None
    try:
        response = requests.get(REALTIME_HISTORY_URL, timeout=6)
        if response.status_code != 200 or not response.text.strip():
            return None
        return _trim_realtime_history(pd.read_csv(io.StringIO(response.text)))
    except Exception:
        return None


def load_realtime_history() -> pd.DataFrame:
    remote = _load_remote_realtime_history()
    if remote is not None and not remote.empty:
        return remote
    if not REALTIME_HISTORY_PATH.exists():
        return _empty_realtime_history()
    try:
        return _trim_realtime_history(pd.read_csv(REALTIME_HISTORY_PATH))
    except Exception:
        return _empty_realtime_history()


def save_realtime_history(history: pd.DataFrame) -> None:
    try:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        _trim_realtime_history(history).to_csv(REALTIME_HISTORY_PATH, index=False)
    except Exception:
        pass


def snapshot_from_realtime_history(history: pd.DataFrame) -> dict[str, Any] | None:
    history = _trim_realtime_history(history)
    if history.empty:
        return None
    latest = history.iloc[-1]

    def value(column: str, default: Any = np.nan) -> Any:
        out = latest.get(column, default)
        return default if pd.isna(out) else out

    return {
        "name": value("name", "Hanoi realtime"),
        "source": value("source", "Realtime history"),
        "aqi": value("aqi"),
        "pm25": value("pm25"),
        "pm10": value("pm10"),
        "lat": value("lat", HANOI_LAT),
        "lon": value("lon", HANOI_LON),
        "time_iso": str(value("local_time", "N/A")),
    }


def stations_from_realtime_history(history: pd.DataFrame) -> list[dict[str, Any]]:
    history = _trim_realtime_history(history)
    if history.empty:
        return []
    latest = history.drop_duplicates(subset=["source", "name"], keep="last").tail(8)
    rows: list[dict[str, Any]] = []
    for _, row in latest.iterrows():
        try:
            aqi = float(row["aqi"])
            lat = float(row.get("lat", HANOI_LAT))
            lon = float(row.get("lon", HANOI_LON))
        except (TypeError, ValueError):
            continue
        rows.append({
            "name": row.get("name", "Hanoi realtime"),
            "source": row.get("source", "Realtime history"),
            "aqi": aqi,
            "category": aqi_category(aqi),
            "pm25": row.get("pm25"),
            "pm10": row.get("pm10"),
            "lat": lat,
            "lon": lon,
            "time_iso": str(row.get("local_time", "N/A")),
        })
    return rows


def historical_snapshot() -> dict[str, Any]:
    latest = CITY.dropna(subset=["aqi"]).tail(1)
    if latest.empty:
        return {
            "name": "Hanoi historical fallback",
            "source": "Historical",
            "aqi": np.nan,
            "lat": HANOI_LAT,
            "lon": HANOI_LON,
            "time_iso": "N/A",
        }
    row = latest.iloc[0]
    return {
        "name": "Hanoi historical fallback",
        "source": "Historical",
        "aqi": row.get("aqi", np.nan),
        "pm25": row.get("pm25", np.nan),
        "pm10": row.get("pm10", np.nan),
        "temp": row.get("temperature", np.nan),
        "humidity": row.get("relative_humidity", np.nan),
        "pressure": row.get("pressure", np.nan),
        "wind": row.get("wind_speed", np.nan),
        "lat": HANOI_LAT,
        "lon": HANOI_LON,
        "time_iso": str(row.get("local_time", "N/A")),
    }


# ── UI ─────────────────────────────────────────────────────────────────────────

app_ui = ui.page_navbar(
    ui.nav_panel("Overview", overview_ui("overview")),
    ui.nav_panel("Districts", district_ui("dist")),
    ui.nav_panel("History", history_ui("hist")),
    ui.nav_panel("Forecast", forecast_ui("forecast")),
    title=ui.div(
        ui.tags.span("🏙️", style="font-size:1.2rem;margin-right:6px;"),
        ui.tags.span("Hanoi AQI", style="font-weight:800;"),
        style="display:flex;align-items:center;",
    ),
    id="main_navbar",
    header=ui.TagList(
        ui.tags.head(
            ui.tags.link(rel="stylesheet", href="styles.css?v=20260607-forecast-source-chip"),
            ui.tags.script(src="https://cdn.plot.ly/plotly-2.35.2.min.js"),
            ui.busy_indicators.options(
                spinner_color="#4fc3f7",
                spinner_size="22px",
                spinner_delay="650ms",
                fade_opacity=0.9,
            ),
            ui.tags.meta(name="description", content="Interactive air quality dashboard for Hanoi, Vietnam — real-time AQI, district analysis, historical trends, and ML-powered forecasts."),
            ui.tags.meta(name="color-scheme", content="dark"),
            ui.tags.title("Hanoi Air Quality Pulse"),
        ),
        ui.tags.a("Skip to dashboard content", href="#dashboard-main", class_="skip-link"),
        ui.tags.span(id="dashboard-main", tabindex="-1", class_="skip-target"),
    ),
    fillable=True,
)


# ── Server ────────────────────────────────────────────────────────────────────

def server(input, output, session):
    initial_history = load_realtime_history()
    station_cache: reactive.Value[list] = reactive.value(stations_from_realtime_history(initial_history))
    snapshot_val: reactive.Value[dict] = reactive.value(snapshot_from_realtime_history(initial_history) or historical_snapshot())
    realtime_history_val: reactive.Value[pd.DataFrame] = reactive.value(initial_history)
    model_cache: dict[tuple[int, str, str], ModelArtifacts] = {}
    refresh_state = {"started": False}

    for horizon in HORIZONS.values():
        for target_col in ("aqi", "pm25"):
            artifact = load_model_artifact(MODEL_DIR, horizon, target_col=target_col, data_mode="cleaned")
            if artifact is not None:
                model_cache[(horizon, target_col, "cleaned")] = artifact

    # ── Model management ──────────────────────────────────────────────────

    def get_model(horizon: int, target_col: str = "aqi", data_mode: str = "cleaned") -> ModelArtifacts | None:
        cache_key = (horizon, target_col, data_mode)
        if cache_key in model_cache:
            return model_cache[cache_key]
        artifact = load_model_artifact(MODEL_DIR, horizon, target_col=target_col, data_mode=data_mode)
        if artifact is not None:
            model_cache[cache_key] = artifact
            return artifact
        try:
            model_cache[cache_key] = train_city_model(CITY, horizon_hours=horizon, target_col=target_col, data_mode=data_mode)
            save_model_artifact(model_cache[cache_key], MODEL_DIR)
            return model_cache[cache_key]
        except Exception:
            return None

    # ── Realtime refresh ─────────────────────────────────────────────────

    def append_realtime_snapshot(snapshot: dict[str, Any]) -> None:
        row = _snapshot_history_row(snapshot)
        if row is None:
            return
        current = realtime_history_val.get()
        incoming = pd.DataFrame([row])
        updated = incoming if current.empty else pd.concat([current, incoming], ignore_index=True)
        updated = _trim_realtime_history(updated)
        realtime_history_val.set(updated)
        save_realtime_history(updated)

    def merge_remote_realtime_history() -> None:
        remote = _load_remote_realtime_history()
        if remote is None or remote.empty:
            return
        current = realtime_history_val.get()
        updated = remote if current.empty else pd.concat([current, remote], ignore_index=True)
        updated = _trim_realtime_history(updated)
        realtime_history_val.set(updated)
        save_realtime_history(updated)

    def refresh_realtime() -> None:
        source_payload: dict[str, Any] | None = None
        stations: list[dict[str, Any]] = []
        if TOKEN:
            try:
                stations = fetch_fresh_waqi_snapshot(TOKEN, keyword="hanoi")
                station_cache.set(stations)
                nearest = nearest_station(HANOI_LAT, HANOI_LON, stations)
                if nearest:
                    source_payload = nearest
            except Exception:
                station_cache.set([])
        if source_payload is None:
            try:
                source_payload = fetch_open_meteo_snapshot(lat=HANOI_LAT, lon=HANOI_LON)
            except Exception:
                source_payload = historical_snapshot()
        snapshot_val.set(source_payload)
        merge_remote_realtime_history()
        append_realtime_snapshot(source_payload)

    @reactive.effect
    def _poll_refresh():
        if not ENABLE_SESSION_NETWORK_REFRESH:
            return
        if not refresh_state["started"]:
            refresh_state["started"] = True
            reactive.invalidate_later(8)
            return
        refresh_realtime()
        reactive.invalidate_later(600)

    # ── Prediction context ───────────────────────────────────────────────

    def prediction_context(horizon: int = 6, target_col: str = "aqi", data_mode: str = "cleaned") -> dict[str, Any]:
        model = get_model(horizon, target_col=target_col, data_mode=data_mode)
        df = CITY.copy()
        if df.empty or df[target_col].dropna().empty:
            return {"model": model, "pred": np.nan, "baseline": np.nan, "delta": np.nan}
        baseline_col = f"{target_col}_clean" if data_mode == "cleaned" and f"{target_col}_clean" in df.columns else target_col
        historical_baseline = float(df[baseline_col].dropna().iloc[-1])
        baseline = historical_baseline
        baseline_source = "Historical fallback"
        pred = baseline
        snap = snapshot_val.get()
        snap_value = pd.to_numeric(snap.get(target_col) if isinstance(snap, dict) else None, errors="coerce")
        if not pd.isna(snap_value):
            baseline = float(snap_value)
            baseline_source = str(snap.get("source", "Realtime snapshot")) if isinstance(snap, dict) else "Realtime snapshot"
        if model is not None:
            pred = predict_next(df, model, overrides=snapshot_overrides(snap))
        return {
            "model": model, "pred": pred, "baseline": baseline,
            "baseline_source": baseline_source,
            "historical_baseline": historical_baseline,
            "delta": pred - baseline, "snapshot": snap,
        }

    # ── District map data ────────────────────────────────────────────────

    @reactive.calc
    def district_map_frame() -> pd.DataFrame:
        if DISTRICT.empty:
            return pd.DataFrame(columns=["district", "aqi_daily", "lat", "lon"])
        agg = DISTRICT.groupby("district", as_index=False)["aqi_daily"].mean().dropna()
        coords = pd.DataFrame([{"district": d, "lat": lat, "lon": lon} for d, (lat, lon) in DISTRICT_CENTROIDS.items()])
        return agg.merge(coords, on="district", how="inner")

    # ── Wire module servers ──────────────────────────────────────────────

    overview_server(
        "overview",
        city_hourly=CITY,
        station_cache=station_cache,
        snapshot=snapshot_val,
        realtime_history=realtime_history_val,
        prediction_context=prediction_context,
        district_map_frame=district_map_frame,
    )
    district_server(
        "dist",
        district_daily=DISTRICT,
    )
    history_server(
        "hist",
        city_hourly=CITY,
    )
    forecast_server(
        "forecast",
        prediction_context=prediction_context,
        get_model=get_model,
        snapshot=snapshot_val,
        city_hourly=CITY,
    )


app = App(app_ui, server, static_assets=APP_DIR)
