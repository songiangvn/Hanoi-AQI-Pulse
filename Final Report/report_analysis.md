# Repository Audit & Gap Analysis — Hanoi Air Quality Pulse

This document is the evidence base for `final_report.tex`. Everything below is traced to source code,
data files, or model artifacts in the repository (commit `67b443a`). Where a number could not be
verified from the code it is flagged explicitly. Model metrics were **verified by loading the actual
`.joblib` artifacts** (see §6).

---

## 1. Project Overview

**Problem.** Air quality in Hanoi is usually communicated as a single citywide AQI number, which hides
variation across districts, hours of the day, seasons, pollutants, and weather. A static figure cannot
answer the practical questions a resident, planner, or student actually has.

**Story / narrative spine.** The dashboard is organized around understanding air quality across three
axes — **space, time, and future**:
- *Space* — how pollution varies across Hanoi's 30 districts (Overview map, Districts tab).
- *Time* — how it follows day/night, seasonal, and multi-year rhythms (History tab).
- *Future* — whether recent signals support short-term risk prediction (Forecast tab).

**Research / analytical questions.**
1. What is Hanoi's air quality *right now*, and what does it mean for outdoor activity?
2. Which districts are most polluted, and how does the ranking shift by month/year?
3. What temporal patterns (daily, seasonal, annual) and anomalies exist in the historical record?
4. Can short-term (1h/6h/24h) forecasts of AQI and PM2.5 beat a naive persistence baseline?

**Intended users.** General public / Hanoi residents (overview-first, mascot, plain-language advisories);
students and instructors in the Data Visualization course (exploratory depth, coordinated views);
and analytically-minded users interested in spatial inequality and forecast interpretability.

---

## 2. Dataset Analysis

| Dataset | Source | Scope | Records | Coverage | Role |
|---|---|---|---|---|---|
| District-level | Kaggle `hau100416/vietnamese-air-quality-dataset` | 30 Hanoi districts | 920,160 hourly rows* | 2022-08-04 → 2026-02-01 | District maps, ranking table, monthly trends, pollutant breakdown |
| City-level | Kaggle `phungdinhdat/aqi-in-hanoi-2022-2025` | Hanoi citywide | 30,341 hourly rows* | 2022-01-13 → 2025-06-30 | Overview fallback, History tab, all forecast models |
| District boundaries | geoBoundaries VNM ADM2 (HDX fallback) | 30 Hanoi districts | 30 polygons | static | All choropleth maps |
| Realtime stations | AQICN / WAQI API | Hanoi stations (≤8) | live, ≤48h fresh | realtime | Overview hero, live map, forecast input |
| Weather fallback | Open-Meteo air-quality + forecast API | Hanoi center (21.0245, 105.8412) | live | realtime | Fallback when AQICN unavailable |
| Realtime history | HF dataset `MountainRiver/hanoi-aqi-realtime-history` | nearest Hanoi station | ~10-min cadence, 168h window | rolling | Overview 24h history + 1h forecast |

\* Record counts/date ranges are sourced from the project's own draft (`final_report_draft.md`) and
`proposal_writeup.md`; they are consistent with the verified `trained_rows` of ~30,316 city rows after
feature-engineering NaN-drops (see §6). The 920,160 district figure is from the raw hourly CSV and was
not independently recomputed (the hourly parquet is built by chunked read in `preprocess.py`).

**City fields** (`data.py:load_city_hourly`): AQI, PM2.5, PM10, CO, NO2, O3, SO2, temperature,
relative_humidity, pressure, precipitation, clouds, wind_speed, uv_index; derived `local_time`, `hour`,
`day_of_week`, `month`, `date`, `aqi_category`.

**District daily fields** (`data.py:load_district_daily`): time, city, district, aqi_daily, aqi_pm2_5,
aqi_pm10, aqi_sulphur_dioxide, aqi_nitrogen_dioxide, aqi_carbon_monoxide, aqi_ozone.

**Processed outputs (parquet, `dashboard/processed/`):** `hanoi_city_hourly.parquet`,
`hanoi_district_daily.parquet`, `hanoi_district_hourly.parquet`, `model_features.parquet`. Parquet is
used to cut app startup time.

**Cleaning & feature engineering** — see §3 (architecture). **Limitations:** realtime history stores only
`timestamp, source, name, aqi, pm25, pm10, lat, lon` (not the full weather/pollutant feature set);
forecasting is city-level only (no district models); 3D maps are visual encodings, not terrain.

---

## 3. Technical Architecture

**Presentation (Shiny).** `app.py` builds a navbar with four `@module` tabs (`mod_overview`,
`mod_district`, `mod_history`, `mod_forecast`), each a UI/server pair. Shared reactive state in `app.py`:
`snapshot_val` (best current reading), `station_cache` (≤8 WAQI stations), `realtime_history_val`
(72h/168h CSV), pre-loaded model artifact cache. Optional polling every 600 s gated by
`ENABLE_SESSION_NETWORK_REFRESH=1`.

**Core library (`dashboard/src/`).**
- `data.py` — load/normalize parquet/CSV, coerce numerics, derive AQI fields, `DataBundle`.
- `anomaly.py` — `apply_city_quality_flags` adds per-metric `_raw/_clean/_robust_z/_is_anomaly/_is_sensor_like`
  columns and row-level `anomaly_count`, `is_extreme_episode`, `quality_label`; `quality_summary`.
- `model.py` — `_build_features`, `train_city_model`, `predict_next`, `ModelArtifacts`, save/load.
- `realtime_api.py` — WAQI search/detail + Open-Meteo fallback; token from env or `aqicn_api_key.md`.
- `utils.py` — `aqi_category`, `aqi_color`, `aqi_advisory`, `sanitize_figure` (NaN→JSON-safe).

**Data cleaning (anomaly.py).** Physical-range validity (e.g. AQI 0–500, humidity 0–100, pressure
950–1050); robust local outlier score via 72h rolling median + MAD (σ=1.4826·MAD), flagged when
robust_z > 6 **and** |value−median| exceeds a per-pollutant minimum delta (AQI 45, PM2.5 35, PM10 60…);
distinguishes *sensor-like* isolated spikes from *extreme episodes* (≥2 pollutants high simultaneously).
Cleaned series clips/interpolates sensor-like and invalid values but **preserves real episodes**.

**Feature engineering (model.py `_build_features`).** Base = 14 pollutant/weather columns; time features
`hour, dow, month, is_weekend`; lag features for {aqi, pm25} at {1, 6, 24}h; rolling mean & max for
{aqi, pm25} over {3, 6, 24}h windows. Target = value shifted −horizon. In cleaned mode, reads `_clean`
columns. NaN rows dropped after engineering.

**ML pipeline.** `HistGradientBoostingRegressor` with three candidates (HistGB-Absolute / -Squared /
-Deep), selected by lowest test MAE on a chronological 80/20 split (no shuffling); final model retrained
on all data; persistence baseline; permutation importance (n_repeats=5) with tree-importance fallback.
`train_models.py` trains 2 targets × 3 horizons × 2 modes = 12 artifacts.

**Offline jobs (`dashboard/scripts/`).** `preprocess.py` (CSV→parquet), `train_models.py`,
`fetch_geojson.py` (geoBoundaries + 22-district diacritic name map), `collect_realtime_history.py`.

**Realtime crawler.** `collect_realtime_history.py` polls WAQI (or Open-Meteo), finds the nearest Hanoi
station, appends a row, trims to a 168h window, writes local CSV, and uploads to the HF dataset.
`run_slurm_realtime_crawler.sh` runs it on the department SLURM cluster every ~10 min, so the deployed
shinyapps.io app shows fresh history even when no session is open.

**External dependencies (`requirements.txt`):** shiny≥1.0, pandas≥2.1, numpy≥1.25, plotly≥5.20,
scikit-learn≥1.4, requests≥2.31, huggingface_hub≥0.23, pyarrow≥16, joblib≥1.3, scipy≥1.11. (deck.gl 9.0
is loaded client-side via CDN inside map iframes.)

---

## 4. Visualization Analysis (design rationale, per tab)

For each chart: why this encoding was chosen and what analytical question it answers. This is the raw
material for report §2. Charts are Plotly unless noted; 3D maps are deck.gl in an HTML iframe.

### Overview (`mod_overview.py`) — "what is the air like right now?"
| Chart | Type | Why chosen / question answered |
|---|---|---|
| AQI hero + scale marker | Big-number + 6-band color bar | Single glanceable status; positions the current value on the full 0–500 risk scale. "How bad is it now?" |
| Realtime 24h history | Spline line w/ day/night `Vrect` shading + cyan dashed 1h forecast | Time-of-day context for a short window; separates *observed* (yellow) from *predicted* (cyan dashed + diamond) so the model isn't mistaken for measured data. "How is it trending, and what's next?" |
| 3D Hanoi map | deck.gl extruded districts + station columns (height & color = AQI) | Spatial overview with magnitude encoded by *both* height and color for memorability; landmark (VinUni) for orientation. 2D scatter-mapbox fallback for accessibility. "Where is it concentrated?" |
| Day/night summary, PM2.5 exposure ("cigarettes/day"), weather card, Lexce mascot | KPI cards + CSS mascot | Translate AQI into lay-understandable risk; mascot mood + plain advisory make the number actionable for non-experts. |

### Districts (`mod_district.py`) — "which districts, and how does it shift over time?"
| Chart | Type | Why chosen / question answered |
|---|---|---|
| District choropleth | 3D extruded GeoJSON (deck.gl) / 2D `Choroplethmapbox` | Choropleth is the canonical encoding for a value-per-region; selected districts highlighted (alpha/teal outline) vs. dimmed context. "Which districts are worst?" |
| Ranking heatmap-table | HTML table, AQI-colored cells, 12 month columns | Combines exact rank/value (table) with a month×district heatmap so seasonality is visible per district. Rejected: plain sorted bar (loses monthly structure). |
| Monthly trend | Multi-line + dotted city baseline | Compares selected districts against the city mean across months; baseline gives reference. |
| Pollutant breakdown | Horizontal bar (6 pollutants) | Bars for direct magnitude comparison across pollutants for the selection. |
| Selection controls | Checkbox group + presets (Top 5, Above avg, PM2.5 hotspots, All, Clear), year/month selects | The engine of cross-filtering — one selection drives all four views (linked). |

### History (`mod_history.py`) — "what patterns and anomalies exist over time?"
| Chart | Type | Why chosen / question answered |
|---|---|---|
| Calendar heatmap | 7×53 day-of-week × week `Heatmap`, 6-step AQI colorscale | GitHub-style calendar makes a full year of daily AQI scannable at once; reveals seasonal bands & bad-day clusters. "When are the bad days?" |
| Seasonal overlay | Multi-year line for one month, current year bold + optional anomaly ✕ markers | Overlaying the same month across years isolates seasonal signal from year-to-year change; anomaly toggle exposes data-quality events without polluting the default view. |
| Category donut | `Pie` (hole 0.62), days-per-category | Part-to-whole for "how many days in each band"; center label = year. |
| Monthly category matrix | HTML stacked-bar table (month×year) | Dense small-multiples of category composition; shows how the mix of Good→Hazardous days evolves. |
| Peak/low cards, annual summary, category days | KPI cards / compact rows | Concrete anchors (worst/best day, YoY % change, % Good days). |

### Forecast (`mod_forecast.py`) — "what's the short-term risk, and can I trust it?"
| Chart | Type | Why chosen / question answered |
|---|---|---|
| Forecast hero + mini-scale + mascot + source chip | Big-number + scale + tier badge | Forecast value framed on the risk scale with an explicit *source tier* (live vs fallback) for honesty. |
| Key-Drivers radar | `Scatterpolar`, top-7 features (log-scaled importance) | Compact multivariate view of *what drives this forecast* — interpretability, not accuracy. |
| Learning-space PCA | 2D PCA scatter, current case as diamond; color modes error/target/risk | Shows where the current case sits among historical backtest cases and where high-error regions are. Explicitly labeled a feature projection, not a neural embedding. |
| Model-vs-baseline bars | Grouped `bar` (MAE, RMSE) | Direct comparison of model vs persistence — the core "is it better?" question. |
| Backtest line | Actual vs model vs baseline over last ~30 days | Honest track record over time. |
| Horizon (1h/6h/24h), target (AQI/PM2.5), PCA-color toggles | Radio groups | Let users probe the model across conditions. |

**AQI color encoding (from `utils.py:AQI_BANDS`, `<=` thresholds):** Good ≤50 `#2bb673`; Moderate ≤100
`#f5b700`; USG ≤150 `#f28f3b`; Unhealthy ≤200 `#d1495b`; Very Unhealthy ≤300 `#7b2cbf`; Hazardous >300
`#5a189a`. This one scale is reused across **every** view, which is what makes cross-view comparison work.

**Chart-type count:** ≥10 distinct types (line/area, 2D choropleth, 3D extruded map, calendar heatmap,
ranking heatmap-table, donut, radar, grouped bar, horizontal bar, PCA scatter, KPI cards) — well above
the rubric's ≥5 charts / ≥3 types.

---

## 5. Interaction Design Analysis

- **Cross-filtering / linked views (Districts):** a single district selection (checkbox or preset)
  simultaneously drives the choropleth, ranking table, monthly trend, and pollutant breakdown — the
  clearest coordinated-multiple-views story in the app. Year/month selects re-aggregate map+ranking while
  the trend keeps year context.
- **Drill-down / mode toggles:** 3D↔2D map toggle (storytelling vs accessibility); PCA color-mode toggle
  (error/target/risk) re-encodes without recompute; History pollutant radio (AQI/PM2.5/PM10) and year/month
  selects; Forecast horizon/target radios reload the relevant model.
- **Reveal-on-demand:** History "show anomaly markers" overlays flagged days only when requested, keeping
  default views clean — analytical honesty without clutter.
- **Tooltips:** deck.gl map tooltips (district/station, AQI, category, source); Plotly hover templates
  with unified hover on the backtest chart.
- **Realtime:** optional 600 s polling refreshes the snapshot and re-runs the 1h forecast.
- **Narrative insight boxes:** every major view has an `aria-live` "what this shows / what it means"
  panel that updates with filters — interactivity that improves *understanding*, not just data subsetting.

---

## 6. Verified Model Metrics

Loaded all 12 artifacts via `joblib` (sklearn 1.6.1 required to unpickle; trained_rows ≈ 30,316 for
city models, consistent with the 30,341-row city dataset minus feature NaN-drops). **Cleaned-series**
values (used in the deployed app and Table 1) match `final_report_draft.md` exactly:

| Target / horizon | Model | MAE | Baseline MAE | RMSE | Baseline RMSE | Improvement |
|---|---|---:|---:|---:|---:|---:|
| AQI 1h | HistGB-Absolute | 18.80 | 19.15 | 29.39 | 32.42 | +1.8% |
| AQI 6h | HistGB-Squared | 30.33 | 37.09 | 40.18 | 49.96 | +18.2% |
| AQI 24h | HistGB-Absolute | 35.37 | 44.43 | 46.89 | 58.33 | +20.4% |
| PM2.5 1h | HistGB-Absolute | 11.89 | 11.73 | 21.36 | 22.28 | −1.4% |
| PM2.5 6h | HistGB-Absolute | 20.82 | 25.64 | 31.35 | 38.98 | +18.8% |
| PM2.5 24h | HistGB-Absolute | 24.59 | 29.94 | 36.06 | 42.84 | +17.9% |

Raw-mode values also match `model_raw_vs_cleaned_comparison.md` (e.g. AQI 1h raw 18.70 vs cleaned 18.80).
**No metric in the report is invented** — all trace to these artifacts.

---

## 7. Existing-Report Gap Analysis

### Reusable content (valid, used in `final_report.tex`)
- `final_report_draft.md` prose §1–7 (motivation, data, realtime, viz/interaction, forecasting, findings,
  limitations) — accurate against code; lightly re-ordered to a visualization-first structure.
- Dataset numbers and Table 1 — **verified** (§6).
- `Report/main.tex` LaTeX preamble, fancyhdr header/footer, booktabs tables, VinUni logo — format only.
- `README.md` chart/interaction inventory and accessibility notes; `DEPLOYMENT.md` deployment chain.
- Team roster (Duc, Giang, Tri, Linh) from `Report/main.tex` team-contributions table.

### Outdated / must-not-claim content
- **District-level forecasting is NOT implemented** — all models are city-level. District hourly data
  exists but is not used for training.
- **The Forecast gauge (`gauge_plot`) is defined but not wired** into the UI output — do not present it
  as a live chart.
- **Realtime feature pipeline is partial** — the crawler stores only AQI/PM2.5/PM10/coords, so live
  forecasts fall back to historical/Open-Meteo context for missing weather features. Must not be
  overstated as a fully realtime feature pipeline.
- Old `Report/main.tex` content is Palmer Penguins (different project) — format reuse only; course header
  "COMP 4010 / Spring 2026" retained as-is from the precedent.

### Missing from the draft (added to the report / analysis)
- Raw-vs-cleaned **dual** model variants (12 artifacts, not 6) and the 3-candidate selection logic.
- Exact anomaly thresholds (robust_z>6, MAD scale, per-pollutant min deltas) and sensor-like vs episode
  distinction.
- Permutation-importance method behind the radar chart.
- Verified RMSE figures (§6), not just MAE.
- Concrete accessibility specifics (ARIA live regions, 2D fallbacks, reduced motion, keyboard focus).

---

## 8. Rubric Mapping (`project_2.md`)

| Rubric dimension | Evidence |
|---|---|
| Visualization & design / storytelling | 10+ chart types; consistent AQI encoding; space→time→future narrative; report §2 |
| Technical complexity / interactivity | Linked cross-filtering, 3D maps, realtime polling, anomaly-aware pipeline |
| ML & analytics (forecasting) | 12 HistGBR artifacts, 3 horizons, baseline comparison, interpretable diagnostics |
| Reproducibility & code quality | `requirements.txt`, unit tests (`dashboard/tests/`), README/DEPLOYMENT, module structure |
| Deployment | shinyapps.io `hanoi-aqi-pulse` + SLURM crawler + HF dataset |
| App minimums (≥5 charts, ≥3 types, interactive, filtering, deployed) | All satisfied/exceeded |
