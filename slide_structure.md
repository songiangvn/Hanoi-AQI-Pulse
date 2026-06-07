# Final Presentation and Live Demo Structure

Purpose: this file is for the teammate preparing the final slides and speaking script. It is written against the current final dashboard state, not the old proposal prototype.

Recommended presentation length: 8 to 10 minutes including the live demo. If the slot is shorter, keep slides 1, 2, 4, 6, 7, 8, and the demo script.

## Rubric Targets

| Rubric item | What the presentation should prove |
|---|---|
| 2.1 Clarity | Problem -> data -> dashboard -> methods -> findings -> limitations |
| 2.2 Live demo | Open the shinyapps.io app live, interact with each tab, avoid screenshot-only demo |
| 2.3 Technical understanding | Explain preprocessing, reactivity, realtime crawler, ML features, validation, and fallbacks |
| 2.4 Q&A | Prepare short answers for realtime, model, 3D maps, limitations, and accessibility |
| 2.5 Slides coverage | Cover problem, dataset, techniques, interactions, ML, architecture, findings, and lessons |

## Slide 1 - Title and Hook

Title:

```text
Hanoi Air Quality Pulse
```

Subtitle:

```text
Realtime, spatial, temporal, and predictive visual analytics for Hanoi air pollution.
```

Visual:

- Use a clean full-width screenshot of the Overview tab.
- Show the deployed shinyapps.io link in a small footer.

Speaker points:

- Hanoi AQI should not be reduced to one number.
- Exposure changes by district, time of day, season, pollutant, and current weather.
- The project turns fragmented historical and live data into an interactive decision-support dashboard.

## Slide 2 - Problem and User Need

Core question:

```text
How does air pollution vary across Hanoi districts and time, and can recent air-quality and weather signals support short-term AQI risk prediction?
```

Why it matters:

- A citywide AQI hides district-level inequality.
- Historical charts alone do not answer what is happening now.
- Forecasting only matters if users can see why the model expects risk to change.

Speaker points:

- The dashboard is aimed at public-facing exploration and analytical explanation.
- It supports overview-first exploration, then lets users drill into districts, history, and model behavior.

## Slide 3 - Data Sources and Pipeline

Use a simple left-to-right pipeline diagram:

```text
Kaggle historical data + GeoJSON + AQICN crawler + Open-Meteo fallback
-> preprocessing / anomaly-aware cleaned series
-> Parquet + Joblib model cache + HF realtime CSV
-> Python Shiny dashboard on shinyapps.io
```

Facts to include:

- District dataset: 30 Hanoi districts, 920,160 hourly rows, 2022-08-04 to 2026-02-01.
- City AQI + weather dataset: 30,341 hourly rows, 2022-01-13 to 2025-06-30.
- Realtime: AQICN / WAQI station observations collected by a SLURM crawler every 10 minutes.
- Persistence: crawler uploads `realtime_history.csv` to Hugging Face Dataset `MountainRiver/hanoi-aqi-realtime-history`.
- Fallback: Open-Meteo or cleaned historical context when live station fields are unavailable.

Speaker points:

- The dashboard is not a static Kaggle viewer; it combines historical, spatial, realtime, and model data.
- The crawler exists because shinyapps.io may sleep when no user is connected.

## Slide 4 - Dashboard Architecture

Visual:

- Use a 4-panel collage: Overview, Districts, History, Forecast.

Architecture points:

- `dashboard/app.py` handles global app assembly.
- Each page has a module: `mod_overview.py`, `mod_district.py`, `mod_history.py`, `mod_forecast.py`.
- Shared logic sits in `dashboard/src/`: data loading, anomaly handling, realtime API, model utilities.
- Cached Parquet files and Joblib model artifacts keep the app fast.
- Plotly outputs are memoized / pre-aggregated where possible to reduce recomputation.

Speaker points:

- This is idiomatic Shiny: inputs are local to the tab where they matter, and linked outputs react only to relevant state.
- Heavy data/model work is done offline or cached so the live demo stays smooth.

## Slide 5 - Visualization Design

Main design choices:

- Dark, high-contrast interface with a modern Hanoi visual identity.
- Narrative insight panels explain what each chart means.
- 2D and 3D spatial views are both available.
- Lexce mascot makes risk status memorable without replacing quantitative evidence.
- Accessibility improvements: higher contrast labels, keyboard focus, reduced-motion support, larger hit targets, and ARIA labels.

Chart inventory to mention:

- Line / area charts.
- 2D maps and 3D spatial maps.
- Calendar heatmap.
- Ranking heatmap table.
- Donut chart.
- Radar chart.
- Gauge chart.
- PCA scatter plot.
- Backtest / comparison charts.

Speaker points:

- This easily satisfies the "at least 5 charts and at least 3 chart types" rubric.
- Every chart has a purpose: current context, spatial comparison, temporal rhythm, anomaly visibility, or model interpretation.

## Slide 6 - Interactivity and Demo Preview

Key interactions:

- District multi-select, Select all, Top 5, Above avg, PM2.5 hotspots, Clear.
- Year and month filters on Districts.
- Pollutant, year, month, and anomaly marker controls on History.
- 3D / 2D map toggles.
- Forecast horizon and target controls.
- PCA color mode: target, error, or risk band.
- Hover tooltips and linked district views.

Speaker points:

- The strongest interaction story is linked filtering: district selections update map, ranking, trend, and pollutant breakdown.
- The forecast page is interactive model explanation, not just one number.

## Slide 7 - Machine Learning and Analytics

Forecast setup:

- Model family: scikit-learn `HistGradientBoostingRegressor`.
- Targets: AQI and PM2.5.
- Horizons: 1h, 6h, 24h.
- Features: current pollutants, weather, time features, lags, rolling means, rolling maxima.
- Validation: chronological split.
- Baseline: persistence / no-change forecast.

How ML is embedded visually:

- Forecast card gives the predicted risk and change from current baseline.
- Gauge shows where the prediction sits in the AQI scale.
- Radar chart shows relative driver influence with log scaling.
- PCA learning-space chart shows where the current forecast sits among historical backtest cases.
- Backtest and error panels explain model reliability.

Speaker points:

- For a regression model, the PCA chart is not a neural embedding. It is a 2D projection of the engineered feature space used by the model.
- Coloring by target, error, or risk band helps answer whether the model has learned meaningful structure and where it struggles.

## Slide 8 - Findings to Report

Use findings that can be shown live in the dashboard:

- Hanoi AQI varies across day/night windows, not only across calendar days.
- District-level patterns are uneven; selected-district maps and ranking heatmaps reveal spatial hotspots.
- The History tab shows seasonal and year-to-year differences, plus anomaly markers for unusual episodes.
- 2025 category mix can be used to discuss risk distribution in the observed data.
- Forecast outputs show short-term AQI / PM2.5 risk and whether the model improves over a persistence baseline.
- Realtime history plus the 1h forecast makes the Overview tab more operational than a static historical dashboard.

Speaker points:

- Avoid overclaiming causality. Say "associated with" or "useful signal for prediction", not "causes".
- Mention that the dashboard supports exploration and risk communication, not medical diagnosis.

## Slide 9 - Deployment and Reliability

Include:

- Primary deployment target: shinyapps.io.
- Deployed app title: `hanoi-aqi-pulse`.
- Realtime crawler: `run_slurm_realtime_crawler.sh` on department SLURM.
- Realtime persistence: Hugging Face Dataset CSV.
- Fallback design: live AQICN -> HF realtime history -> Open-Meteo / historical cleaned context.

Speaker points:

- shinyapps.io can sleep, so collecting inside the Shiny process alone is not reliable.
- The external crawler is the production-minded solution for demo freshness.
- The app remains usable if a realtime source temporarily fails.

## Slide 10 - Limitations and Future Work

Honest limitations:

- Realtime station coverage can be sparse or stale.
- The crawler currently stores AQI, PM2.5, PM10, coordinates, source, and timestamps; some secondary forecast features still use fallback context.
- City-level forecasting is more reliable than district-level forecasting with the current data.
- The 3D map is used for visual storytelling and spatial orientation, not exact physical elevation.

Future work:

- Store richer realtime weather and pollutant features.
- Add uncertainty bands around forecasts.
- Improve district-level forecasting with station-specific data.
- Add user testing for accessibility and map readability.

## Live Demo Script

Use the live shinyapps.io app. Keep a local tab open as backup only.

### 0:00-0:30 - Open App

Show:

- The shinyapps.io URL.
- The Overview hero.
- Current AQI source and timestamp.

Say:

- "This is running live on shinyapps.io. The current and recent data are read from the realtime crawler output when available."

### 0:30-1:45 - Overview

Click / show:

- Realtime AQI History - Last 24 Hours.
- The cyan dashed 1h prediction segment.
- Hanoi AQI Map 3D mode, then briefly 2D toggle if time.
- Lexce current AQI reaction.

Say:

- "Observed history and model prediction are visually separated, so the user can distinguish measured data from forecast."

### 1:45-3:00 - Districts

Click / show:

- Select Top 5.
- Change month.
- Toggle 3D / 2D District AQI Map.
- Point to linked update in ranking, trend, and pollutant breakdown.

Say:

- "This is the strongest linked-interaction page: one district selection controls several views."

### 3:00-4:15 - History

Click / show:

- Change pollutant or year.
- Toggle anomaly markers.
- Change seasonal-comparison month.
- Show category mix.

Say:

- "The anomaly markers are useful because air-quality data includes both real extreme events and possible sensor-like spikes."

### 4:15-5:45 - Forecast

Click / show:

- Change horizon from 1h to 6h or 24h.
- Switch AQI / PM2.5 if time.
- Show source chip in the forecast summary.
- Show radar chart and PCA learning space.

Say:

- "The forecast page gives the prediction, compares against a baseline, and shows how the current feature profile relates to historical model behavior."

### 5:45-6:15 - Close

Say:

- "The main contribution is combining live monitoring, spatial comparison, temporal history, and predictive analytics in one Shiny app."

## Q&A Cheat Sheet

**Why Python Shiny?**

It gives reactive UI, server-side Python data/model integration, Plotly outputs, and a deployable web app without splitting the project into a separate frontend/backend.

**Is the app really realtime?**

It is near-realtime. A SLURM crawler collects AQICN station observations every 10 minutes and uploads them to a Hugging Face Dataset. The deployed app reads that data. If the crawler or AQICN is unavailable, the app falls back gracefully.

**Why do some forecast features come from fallback data?**

AQICN station snapshots do not always provide every weather and secondary pollutant feature needed by the trained model. The app overrides available current features with live values and uses cleaned historical / fallback context for missing fields.

**What is the PCA learning-space chart?**

It is a projection of engineered model input features, not a neural embedding. It helps show where the current forecast case sits relative to historical cases and whether high-error cases cluster.

**Why 3D maps?**

The 3D mode improves spatial storytelling and makes station columns, district blocks, and the VinUni landmark more memorable. The 2D mode remains available for simpler reading and accessibility.

**Why cleaned data only?**

The final app uses quality-controlled data because raw sensor-like spikes can distort patterns and forecasts. Anomaly markers remain visible so unusual events are not hidden.

**What would you improve next?**

Richer realtime feature storage, uncertainty intervals, district-level forecasting, and more formal accessibility user testing.
