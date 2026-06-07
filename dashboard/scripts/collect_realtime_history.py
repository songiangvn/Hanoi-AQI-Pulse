"""Collect Hanoi realtime AQI snapshots into the dashboard runtime CSV.

This script is intended to run outside shinyapps.io, for example as a long
server/SLURM job before a demo. The Shiny app reads the same CSV path when it
starts. It can also push the CSV to a public Hugging Face Dataset so the
deployed app can refresh realtime history without redeploying.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from src.realtime_api import fetch_fresh_waqi_snapshot, fetch_open_meteo_snapshot, read_aqicn_token


REPO_ROOT = APP_DIR.parent
DEFAULT_OUTPUT = APP_DIR / "runtime" / "realtime_history.csv"
DEFAULT_HF_REPO_ID = "MountainRiver/hanoi-aqi-realtime-history"
DEFAULT_HF_PATH = "realtime_history.csv"
HANOI_LAT = 21.0245
HANOI_LON = 105.8412


def nearest_station(lat: float, lon: float, stations: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not stations:
        return None
    return min(stations, key=lambda s: (float(s["lat"]) - lat) ** 2 + (float(s["lon"]) - lon) ** 2)


def snapshot_time(snapshot: dict[str, Any]) -> pd.Timestamp:
    ts = pd.to_datetime(snapshot.get("time_iso"), errors="coerce", utc=True)
    if pd.isna(ts):
        ts = pd.Timestamp.now(tz="UTC")
    return ts


def snapshot_row(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    aqi = pd.to_numeric(snapshot.get("aqi"), errors="coerce")
    if pd.isna(aqi):
        return None
    ts = snapshot_time(snapshot)
    local = ts.tz_convert("Asia/Ho_Chi_Minh").tz_localize(None)
    return {
        "timestamp_utc": ts.isoformat(),
        "local_time": local.isoformat(),
        "source": snapshot.get("source", "Unknown"),
        "name": snapshot.get("name", "Hanoi realtime"),
        "aqi": float(aqi),
        "pm25": pd.to_numeric(snapshot.get("pm25"), errors="coerce"),
        "pm10": pd.to_numeric(snapshot.get("pm10"), errors="coerce"),
        "lat": pd.to_numeric(snapshot.get("lat", HANOI_LAT), errors="coerce"),
        "lon": pd.to_numeric(snapshot.get("lon", HANOI_LON), errors="coerce"),
    }


def trim_history(history: pd.DataFrame, max_hours: int) -> pd.DataFrame:
    if history.empty:
        return history
    df = history.copy()
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], errors="coerce", utc=True)
    df["local_time"] = pd.to_datetime(df["local_time"], errors="coerce")
    df["aqi"] = pd.to_numeric(df["aqi"], errors="coerce")
    df = df.dropna(subset=["timestamp_utc", "local_time", "aqi"])
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=max_hours)
    df = df[df["timestamp_utc"] >= cutoff]
    df = df.sort_values("timestamp_utc")
    df = df.drop_duplicates(subset=["timestamp_utc", "source", "name"], keep="last")
    return df.reset_index(drop=True)


def load_history(path: Path, max_hours: int) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["timestamp_utc", "local_time", "source", "name", "aqi", "pm25", "pm10", "lat", "lon"])
    try:
        return trim_history(pd.read_csv(path), max_hours=max_hours)
    except Exception:
        return pd.DataFrame(columns=["timestamp_utc", "local_time", "source", "name", "aqi", "pm25", "pm10", "lat", "lon"])


def save_history(history: pd.DataFrame, path: Path, max_hours: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    trim_history(history, max_hours=max_hours).to_csv(tmp_path, index=False)
    tmp_path.replace(path)


def read_hf_token() -> str | None:
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    if token:
        return token.strip()
    for path in (REPO_ROOT / "hf_token.txt", APP_DIR / "hf_token.txt"):
        if path.exists():
            token = path.read_text(encoding="utf-8").strip()
            if token:
                return token
    return None


def upload_history_to_hf(
    path: Path,
    *,
    repo_id: str,
    repo_path: str,
    token: str | None,
    ensure_repo: bool,
) -> bool:
    if not token:
        return False
    if not path.exists():
        return False
    try:
        from huggingface_hub import HfApi, create_repo
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is not installed. Run: "
            "dashboard/.venv/bin/pip install -r dashboard/requirements.txt"
        ) from exc

    if ensure_repo:
        create_repo(repo_id=repo_id, repo_type="dataset", private=False, exist_ok=True, token=token)

    api = HfApi(token=token)
    api.upload_file(
        path_or_fileobj=str(path),
        path_in_repo=repo_path,
        repo_id=repo_id,
        repo_type="dataset",
        commit_message="Update Hanoi realtime AQI history",
    )
    return True


def fetch_snapshot(token: str | None, keyword: str) -> dict[str, Any]:
    if token:
        stations = fetch_fresh_waqi_snapshot(token, keyword=keyword)
        nearest = nearest_station(HANOI_LAT, HANOI_LON, stations)
        if nearest:
            nearest["station_count"] = len(stations)
            return nearest
    return fetch_open_meteo_snapshot(lat=HANOI_LAT, lon=HANOI_LON)


def collect_once(
    output: Path,
    max_hours: int,
    keyword: str,
    *,
    hf_repo_id: str,
    hf_path: str,
    hf_upload: bool,
    hf_create_repo: bool,
) -> tuple[dict[str, Any], bool] | None:
    token = read_aqicn_token(APP_DIR) or read_aqicn_token(REPO_ROOT)
    snapshot = fetch_snapshot(token=token, keyword=keyword)
    row = snapshot_row(snapshot)
    if row is None:
        return None

    current = load_history(output, max_hours=max_hours)
    incoming = pd.DataFrame([row])
    updated = incoming if current.empty else pd.concat([current, incoming], ignore_index=True)
    save_history(updated, output, max_hours=max_hours)

    uploaded = False
    if hf_upload:
        uploaded = upload_history_to_hf(
            output,
            repo_id=hf_repo_id,
            repo_path=hf_path,
            token=read_hf_token(),
            ensure_repo=hf_create_repo,
        )
    return row, uploaded


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Hanoi realtime AQI history for the Shiny dashboard.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--interval-minutes", type=float, default=10.0)
    parser.add_argument("--max-hours", type=int, default=168)
    parser.add_argument("--keyword", default="hanoi")
    parser.add_argument("--hf-repo-id", default=os.getenv("HF_REALTIME_DATASET_ID", DEFAULT_HF_REPO_ID))
    parser.add_argument("--hf-path", default=DEFAULT_HF_PATH)
    parser.add_argument("--no-hf-upload", action="store_true")
    parser.add_argument("--create-hf-repo", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    while True:
        try:
            result = collect_once(
                output=args.output,
                max_hours=args.max_hours,
                keyword=args.keyword,
                hf_repo_id=args.hf_repo_id,
                hf_path=args.hf_path,
                hf_upload=not args.no_hf_upload,
                hf_create_repo=args.create_hf_repo,
            )
            if result is None:
                print(f"[{pd.Timestamp.now(tz='UTC').isoformat()}] no valid AQI snapshot", flush=True)
            else:
                row, uploaded = result
                upload_text = "uploaded to HF" if uploaded else "HF upload skipped"
                print(
                    f"[{pd.Timestamp.now(tz='UTC').isoformat()}] "
                    f"saved {row['source']} AQI={row['aqi']:.0f} at {row['local_time']} "
                    f"-> {args.output}; {upload_text}",
                    flush=True,
                )
        except Exception as exc:
            print(f"[{pd.Timestamp.now(tz='UTC').isoformat()}] collect failed: {exc}", flush=True)

        if args.once:
            break
        time.sleep(max(60.0, args.interval_minutes * 60.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
