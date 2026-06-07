# Final Live Demo Walkthrough

This file is the operational demo guide for the final presentation. It assumes the dashboard is already deployed on shinyapps.io and the realtime crawler is running on the department server.

## Pre-Demo Checklist

Run these checks before the presentation:

```bash
cd /vol/biomedic3/gn425/HaNoiAQI
squeue -u gn425
tail -n 40 logs/out/sbatch.monal04.65397.out
```

Expected crawler state:

- The SLURM job is running.
- The log shows recent AQICN / upload activity.
- `dashboard/runtime/realtime_history.csv` is being updated.
- The Hugging Face Dataset `MountainRiver/hanoi-aqi-realtime-history` contains `realtime_history.csv`.

Open before the demo:

- The shinyapps.io app in one browser tab.
- A second refreshed tab as backup.
- A local app tab only if network is unstable.

If the app appears dimmed with a loading overlay for too long, refresh once. The production app avoids session-side network crawling, so persistent loading is usually a stale browser/session issue rather than a crawler problem.

## Main Demo Path

### 1. Overview - Live Context

Show:

- AQI hero card.
- Realtime source / timestamp.
- Weather context.
- "WHAT THIS MEANS" insight.

Message:

```text
The first screen answers: what is Hanoi's air quality right now, how severe is it, and what should a viewer understand immediately?
```

Point out:

- Realtime values come from AQICN / the HF realtime history when available.
- The fallback state is explicit if live values are incomplete.
- Text and contrast were tuned for accessibility.

### 2. Overview - Realtime History and 1h Forecast

Show:

- Realtime AQI History - Last 24 Hours.
- Yellow observed line.
- Cyan dashed prediction segment and diamond marker.
- Day/night background bands.
- 24h PM2.5 exposure card.

Message:

```text
Observed history and model prediction are visually separated, so the user can tell measured data from forecast.
```

Mention:

- The external crawler stores data even when no one has the app open.
- The 1h prediction is added to the end of the realtime history chart.

### 3. Overview - Hanoi AQI Map

Show:

- Hanoi AQI Map in 3D mode.
- Live station AQI column.
- VinUni landmark in Gia Lam.
- Toggle to 2D if time.

Message:

```text
The 3D map is a spatial storytelling layer for realtime station context; the 2D version remains available for simpler reading.
```

Point out:

- Default camera is focused near the realtime station and VinUni.
- Colors are intentionally cool teal for this map so live stations and the landmark stand out.

### 4. Districts - Linked Spatial Exploration

Actions:

- Click `Top 5`.
- Change `Month`.
- Toggle District AQI Map between 3D and 2D.
- Show ranking table and monthly trend updating.

Message:

```text
This page is where interactivity is strongest: one district selection controls the spatial map, ranking heatmap, trend chart, and pollutant breakdown.
```

Point out:

- 30 districts are available.
- Month and year filters make the map more specific than a fixed annual average.
- District labels and top boundary lines make the 3D map easier to read.

### 5. History - Temporal Patterns and Data Quality

Actions:

- Change pollutant or year.
- Toggle anomaly markers.
- Change month in the seasonal comparison.
- Show Air Quality Category Mix.

Message:

```text
History is not just a static line chart; it exposes seasonal patterns, daily category mix, and unusual observations.
```

Point out:

- Cleaned data is used for final production views.
- Anomaly markers preserve visibility of unusual spikes and possible pollution episodes.

### 6. Forecast - Model Output and Interpretation

Actions:

- Change horizon: 1h, 6h, 24h.
- Switch target: AQI / PM2.5.
- Show forecast card and Lexce forecast mood.
- Show Forecast Risk Gauge.
- Show Key Prediction Drivers radar chart.
- Show Model Learning Space PCA.

Message:

```text
The forecast is not shown as a black box. The app shows the predicted risk, the current input source, driver influence, model error, and where the current case sits in historical feature space.
```

Point out:

- Lexce expression follows predicted AQI, not just the current reading.
- The radar chart uses log scaling to keep smaller drivers visible.
- The PCA chart projects engineered regression features, not a neural embedding.

## Short Technical Explanation

Use this if asked how the pieces fit together:

```text
Historical datasets are preprocessed into compact Parquet files. Forecast models are trained offline and cached as Joblib artifacts. The live app uses Python Shiny modules for each tab and Plotly for interactive visualizations. Realtime station observations are collected outside Shiny by a SLURM crawler and stored in a Hugging Face Dataset, which the app reads as a lightweight CSV. This keeps shinyapps.io deployment reliable while still allowing near-realtime behavior.
```

## Rubric Evidence Checklist

| Criterion | Evidence to show live |
|---|---|
| 2.2 Live demo quality | shinyapps.io app opens, tabs switch smoothly, 3D/2D maps and controls work |
| 2.6 Visualization quality | polished dark UI, modern map styling, insight boxes, Lexce, 3D district map |
| 2.7 Chart requirements | more than 5 charts and more than 3 chart types across tabs |
| 2.8 Interactivity | district linked filtering, year/month controls, anomaly toggle, forecast target/horizon, PCA mode |
| 2.9 Technical complexity | external crawler, HF realtime store, Parquet cache, Joblib models, modular Shiny |
| 2.10 ML / analytics | forecast card, risk gauge, radar drivers, PCA learning space, backtest/error charts |
| 2.11 Python Shiny | modular pages, reactive inputs, cached data/model outputs |
| 2.12 Reproducibility | `requirements.txt`, local run command, tests, deployment notes |

## Backup Talking Points

If realtime is temporarily unavailable:

```text
The app is designed to degrade gracefully. It shows the latest available HF realtime history or falls back to cleaned historical context, and the source label makes that transparent.
```

If a 3D map is slow:

```text
The 2D toggle is included both for accessibility and reliability. It gives the same analytical context in a lighter view.
```

If asked why the model can predict with partial realtime features:

```text
The current AQI / PM2.5 / PM10 values are the most important live signals. When AQICN does not provide every model feature, the app uses cleaned historical or fallback context for the missing values. This is a limitation, but it is explicit and production-safe.
```

If asked what the biggest contribution is:

```text
The contribution is integration: realtime monitoring, district-level spatial exploration, historical anomaly-aware analysis, and short-term ML forecasting are presented in one coherent Shiny workflow.
```
