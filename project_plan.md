# Hanoi Air Quality Pulse - Final Project Plan and Report Notes

This document summarizes the final dashboard status and gives material that can be reused in the final report and slides.

## One-Sentence Summary

Hanoi Air Quality Pulse is a deployed Python Shiny dashboard that combines realtime AQICN station monitoring, district-level spatial analysis, historical anomaly-aware exploration, and short-term AQI / PM2.5 forecasting for Hanoi.

## Final Project Question

```text
How does air pollution vary across Hanoi districts and time, and can recent air-quality and weather signals support short-term AQI risk prediction?
```

## Final Application Status

The final dashboard has four tabs:

1. Overview
   - Realtime AQI hero with source state and weather context.
   - Realtime AQI History - Last 24 Hours with a 1h forecast extension.
   - Day/night AQI pattern and 24h PM2.5 exposure card.
   - Hanoi AQI Map with 3D / 2D modes, realtime station column, and VinUni landmark.
   - Lexce AQI buddy for accessible risk communication.

2. Districts
   - District multi-select and quick filters.
   - Year and month filters.
   - District AQI Map with 3D / 2D modes, labels, and visible boundary lines.
   - Ranking heatmap table, selected-district monthly trend, and pollutant breakdown.
   - Linked filtering across map, table, chart, and summary.

3. History
   - Pollutant and year controls.
   - Calendar heatmap, seasonal comparison, category mix, and monthly category matrix.
   - Show anomaly markers toggle.
   - Month selector for seasonal comparison.

4. Forecast
   - AQI / PM2.5 forecasts at 1h, 6h, and 24h horizons.
   - Realtime current baseline when available.
   - Forecast risk gauge.
   - Lexce forecast mood based on predicted AQI.
   - Key Prediction Drivers radar chart.
   - Model Learning Space PCA projection.
   - Backtest and model-vs-baseline error evidence.

## Data Sources

### District-Level Hanoi Air Quality

Source: Kaggle `hau100416/vietnamese-air-quality-dataset`

Use:

- District maps.
- District ranking heatmap.
- Monthly trend.
- Pollutant breakdown.

Audited local facts:

- 30 Hanoi districts.
- 920,160 hourly Hanoi rows.
- Time range: 2022-08-04 to 2026-02-01.

### City-Level AQI and Weather

Source: Kaggle `phungdinhdat/aqi-in-hanoi-2022-2025`

Use:

- Overview historical fallback.
- History charts.
- Forecast model training and validation.

Audited local facts:

- 30,341 hourly rows.
- Time range: 2022-01-13 to 2025-06-30.
- Variables include AQI, PM2.5, PM10, CO, NO2, O3, SO2, temperature, humidity, pressure, precipitation, wind, clouds, and UV index.

### Spatial Boundaries

Source: `data/hanoi_districts.geojson`

Use:

- 2D and 3D district geometry.
- Name-matched spatial joins for the 30 districts.

### Realtime Sources

Primary:

- AQICN / WAQI station observations.

Persistence layer:

- Department-server SLURM crawler.
- Hugging Face Dataset `MountainRiver/hanoi-aqi-realtime-history`.
- `realtime_history.csv`, updated by crawler approximately every 10 minutes.

Fallback:

- Open-Meteo and cleaned historical context when live station fields are unavailable.

## Technical Stack

- Python Shiny for the web app.
- Plotly for charts and maps.
- Pandas / NumPy for data processing.
- Parquet for compact processed data.
- scikit-learn for forecasting.
- Joblib for cached model artifacts.
- GeoJSON for district boundaries.
- SLURM job for long-running realtime collection.
- Hugging Face Dataset for lightweight realtime history persistence.
- shinyapps.io for final deployment.

## Forecasting Method

Targets:

- AQI.
- PM2.5.

Horizons:

- 1 hour.
- 6 hours.
- 24 hours.

Features:

- Current pollutants.
- Weather variables.
- Time features: hour, day of week, month, weekend indicator.
- Lag features: 1h, 6h, 24h.
- Rolling features: 3h, 6h, 24h mean and max.

Model:

- scikit-learn `HistGradientBoostingRegressor`.
- Chronological validation split.
- Persistence / no-change baseline.
- Cached `.joblib` artifacts for reliable deployment.

Interpretability views:

- Forecast card and risk gauge.
- Radar chart for key drivers.
- PCA learning-space chart for regression feature space.
- Backtest predicted-vs-observed chart.
- Model-vs-baseline error chart.

Important limitation:

- Realtime AQICN snapshots may not contain every training feature. The app uses available live features and fills missing values from cleaned historical / fallback context. This is shown transparently in the UI.

## Data Quality and Anomaly Handling

Final dashboard uses the cleaned, anomaly-aware series for production views and forecasting.

Approach:

- Physical plausibility checks.
- Rolling median / MAD-style robust anomaly detection.
- Separation between likely real pollution episodes and isolated sensor-like spikes.
- Show anomaly markers in History so unusual events remain visible rather than silently hidden.

Report framing:

```text
We clean the series for modeling stability while retaining anomaly visibility for interpretation.
```

## Visualization and Interaction Coverage

Chart types:

- Line / area chart.
- Calendar heatmap.
- Ranking heatmap table.
- 2D map.
- 3D map.
- Donut chart.
- Radar chart.
- Gauge chart.
- PCA scatter plot.
- Backtest / comparison chart.

Interactions:

- Page navigation.
- District multi-select and quick filter buttons.
- Linked district views.
- Year and month filters.
- Pollutant controls.
- Show anomaly markers toggle.
- 3D / 2D toggles.
- Forecast target and horizon controls.
- PCA color mode.
- Tooltips.

This comfortably satisfies the application rubric requirement of at least 5 charts and at least 3 chart types.

## Rubric Mapping

### 2a. Presentation and Demo

| Criterion | Evidence to emphasize |
|---|---|
| 2.1 Clarity | Tell the story in this order: problem, data, dashboard, interactions, ML, findings, limitations |
| 2.2 Live demo | Use shinyapps.io; show realtime history, district filtering, anomaly toggle, and forecast controls |
| 2.3 Technical understanding | Explain Shiny modules, crawler/HF realtime store, cleaned data, model cache, fallback design |
| 2.4 Q&A | Prepare answers on realtime partial features, PCA meaning, 3D map purpose, and limitations |
| 2.5 Slides coverage | Include problem, datasets, design, interactions, ML, architecture, findings, lessons |

### 2b. Application

| Criterion | Evidence in app |
|---|---|
| 2.6 Visualization quality | Polished dark UI, modern maps, narrative insight cards, accessible contrast, Lexce |
| 2.7 Chart requirements | More than 5 charts and more than 3 chart types |
| 2.8 Interactivity | Linked district filtering, 3D/2D toggles, year/month filters, anomaly toggle, forecast controls |
| 2.9 Technical complexity | Realtime crawler, HF persistence, Parquet preprocessing, model cache, 3D maps, modular app |
| 2.10 ML / analytics | Short-term forecasts, radar drivers, PCA learning space, backtest, error comparison |
| 2.11 Python Shiny | Modular pages, reactive inputs/outputs, cached heavy work |
| 2.12 Reproducibility | `requirements.txt`, run command, tests, deployment notes |
| 2.13 Repo/docs | README, deployment guide, slide guide, walkthrough, organized `dashboard/` modules |
| 2.14 Teamwork | Use commit history and slide/report roles to show balanced contributions |

### 2c. Report

Recommended six-page structure:

1. Introduction and motivation.
2. Data sources, preprocessing, and anomaly handling.
3. Visualization and interaction design.
4. Realtime architecture and deployment.
5. Forecasting method and model interpretation.
6. Findings, limitations, lessons learned, and future work.

For a complete prose draft, use [final_report_draft.md](final_report_draft.md) and convert it into the final LaTeX format.

## Suggested Report Claims

Use careful wording:

- "The dashboard reveals spatial and temporal variation" rather than "proves causation".
- "The model supports short-term risk prediction" rather than "guarantees exact future AQI".
- "Realtime AQICN values are used when available" rather than "all model features are fully realtime".
- "3D maps support spatial storytelling" rather than "represent physical terrain height".

Good findings to discuss:

- Air quality has strong time-of-day and seasonal variation.
- District views reveal uneven spatial exposure patterns.
- Anomaly markers help separate unusual episodes from normal seasonal patterns.
- Forecast interpretation views make model behavior more transparent.
- External realtime collection improves demo reliability compared with relying only on Shiny session runtime.

## Demo Team Roles

Replace names with actual teammates:

- Presenter 1: problem, data, and motivation.
- Presenter 2: Overview and Districts live demo.
- Presenter 3: History, anomaly handling, and visual design choices.
- Presenter 4: Forecasting, realtime architecture, Q&A.

## Final Limitations

- Realtime station coverage is limited and can be stale.
- Some forecast input features use fallback context when AQICN does not provide them.
- Forecasting is city-level rather than fully district-specific.
- 3D spatial views improve communication but are not exact physical elevation models.
- More formal user testing would be needed to fully validate accessibility.
