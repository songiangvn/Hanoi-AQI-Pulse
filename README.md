# Hanoi Air Quality Pulse

Interactive spatial, temporal, real-time, and predictive visualization of Hanoi air pollution.

## Team Contribution
- Le Phuong Linh: Story-telling, Preprocessing
- Luu Nguyen Chi Duc: UI/UX, Overview Module
- Nguyen Gia Hung: Districts Module
- Thai Huu Tri: History Module
- Nguyen Son Giang: Forecase Module

## Final Project Status

Hanoi Air Quality Pulse is a deployed Python Shiny dashboard for exploring Hanoi air quality across realtime station readings, 30 districts, historical temporal patterns, and short-term AQI / PM2.5 forecasts.

Primary final deployment:

```text
shinyapps.io account: giangnguyenson
app title: hanoi-aqi-pulse
```

The dashboard is designed to satisfy the final rubric requirement that the app runs live and smoothly on shinyapps.io. A department-server crawler collects real-time AQICN station history every 10 minutes and publishes it to a Hugging Face dataset, so the deployed app can show fresh history even when no Shiny session is open.

Main question:

```text
How does air pollution vary across Hanoi districts and time, and can recent air-quality and weather signals support short-term AQI risk prediction?
```

## Final Dashboard

### Overview

Purpose: explain the current Hanoi AQI situation quickly, then connect it to live station history and spatial context.

Implemented views:

- Realtime AQI hero with AQI category, timestamp, source state, weather context, and accessible text.
- Realtime AQI History - Last 24 Hours with the model's 1-hour forecast shown as a cyan dashed prediction segment and diamond marker.
- Day and night AQI pattern, peak cards, and narrative insight text.
- 24h PM2.5 exposure card using cigarette-equivalent framing.
- Hanoi AQI Map with 3D / 2D toggle, realtime station column, VinUni landmark in Gia Lam, and a cool teal district context theme.
- Lexce AQI buddy whose visual state and recommendation respond to the current AQI category.

### Districts

Purpose: compare spatial air-quality patterns across Hanoi's 30 districts.

Implemented views and interactions:

- District multi-select with Select all, Top 5, Above avg, PM2.5 hotspots, and Clear shortcuts.
- Year and month filters for district aggregation.
- District AQI Map with 3D / 2D toggle, visible district labels, top boundary lines, and selected-district highlighting.
- District ranking heatmap table with monthly AQI cells.
- Selected District - Monthly Trend rendering all selected districts from cached monthly aggregates.
- Pollutant breakdown for selected districts.
- Linked district filters update the map, ranking, trend, and pollutant summary together.

### History

Purpose: reveal long-term temporal structure and data-quality events.

Implemented views and interactions:

- Pollutant and year controls.
- Calendar heatmap for daily air-quality intensity.
- Show anomaly markers toggle for flagged spikes and unusual episodes.
- Month-selectable seasonal comparison across years.
- Air Quality Category Mix with year selector.
- Monthly category distribution matrix.
- Peak / low day summaries and narrative insight boxes.

### Forecast

Purpose: embed short-term prediction and model interpretation into the dashboard, not as a separate technical appendix.

Implemented views and interactions:

- Forecast horizon controls: 1h, 6h, 24h.
- Target controls: AQI and PM2.5.
- Forecast summary card using realtime current baseline when available, with a production-style source chip.
- Lexce forecast mood placed inside the forecast card; the expression follows predicted AQI risk.
- Forecast Risk Gauge.
- Key Prediction Drivers radar chart using log-scaled relative influence so dominant drivers do not hide smaller signals.
- Model Learning Space PCA chart, with points colored by target, error, or risk band.
- Backtest predicted-vs-observed chart and model-error comparison against persistence baseline.

## Data Sources

| Source | Scope | Role in dashboard |
|---|---:|---|
| Kaggle `hau100416/vietnamese-air-quality-dataset` | 30 Hanoi districts, 920,160 hourly rows, 2022-08-04 to 2026-02-01 | District maps, rankings, monthly trends, pollutant breakdown |
| Kaggle `phungdinhdat/aqi-in-hanoi-2022-2025` | 30,341 hourly city-level rows, 2022-01-13 to 2025-06-30 | Historical charts, anomaly-aware cleaned series, forecast model training |
| `data/hanoi_districts.geojson` | 30 district boundaries | 2D and 3D district spatial layers |
| AQICN / WAQI | Realtime station observations | Live AQI, PM2.5, PM10, station map, current forecast baseline |
| Open-Meteo | Fallback realtime context | Used when AQICN is unavailable or incomplete |
| Hugging Face Dataset `MountainRiver/hanoi-aqi-realtime-history` | Crawler-maintained realtime CSV | Near-24/7 realtime history source for the deployed app |

## Forecasting and Analytics

The forecast is framed as short-term risk prediction rather than a perfect sensor simulator.

- Models: scikit-learn `HistGradientBoostingRegressor` variants cached with Joblib.
- Targets: AQI and PM2.5.
- Horizons: 1h, 6h, 24h.
- Baseline: persistence / no-change forecast.
- Validation: chronological split to avoid future leakage.
- Features: current pollutants, weather variables, time features, lag windows, and rolling mean / max windows.
- Production input: the app uses realtime AQICN / HF history values when present and falls back to the cleaned historical feature row when live fields are missing.
- Explanation: radar driver chart, model-vs-baseline error, backtest chart, and PCA learning-space view.

Current limitation to explain in Q&A: the crawler reliably stores real-time AQI, PM2.5, PM10, station coordinates, and timestamps. Some weather and secondary pollutant features still come from fallback or historical context when real-time values are unavailable.

## Chart and Interaction Inventory

The final dashboard exceeds the rubric minimum of at least 5 charts and at least 3 chart types.

Chart types used:

- Line and area charts.
- 2D map / scatter map.
- 3D spatial map.
- Calendar heatmap.
- Ranking heatmap table.
- Donut chart.
- Radar chart.
- Gauge chart.
- PCA scatter plot.
- Bar / comparison charts.
- Category matrix.
- Narrative KPI and exposure cards.

Key interactions:

- Page navigation across Overview, Districts, History, and Forecast.
- 3D / 2D map toggles.
- District multi-select and quick filters.
- Year and month filters.
- Pollutant selector.
- Anomaly marker toggle.
- Forecast horizon and target controls.
- PCA color-mode selector.
- Hover tooltips across Plotly charts.
- Linked district selection across map, ranking, trend, and breakdown.

## Accessibility and UI/UX

The app includes accessibility-oriented design choices for visual, motor, cognitive, and neurological needs:

- Keyboard-visible focus states and skip link.
- Larger hit targets for controls.
- Higher-contrast text for insight panels and secondary labels.
- Reduced-motion support.
- ARIA labels and live-region updates for realtime AQI, station status, maps, charts, and forecast cards.
- Narrative "WHAT THIS SHOWS" / "WHAT THIS MEANS" panels to reduce interpretation burden.
- Both 3D and 2D map modes so users can switch away from depth-heavy views.

## Architecture

```text
HaNoiAQI/
├── README.md
├── DEPLOYMENT.md
├── project_plan.md
├── slide_structure.md
├── proposal_writeup.md
├── run_slurm_realtime_crawler.sh
├── image/
├── data/
└── dashboard/
    ├── app.py
    ├── styles.css
    ├── modules/
    │   ├── mod_overview.py
    │   ├── mod_district.py
    │   ├── mod_history.py
    │   └── mod_forecast.py
    ├── src/
    │   ├── anomaly.py
    │   ├── data.py
    │   ├── model.py
    │   ├── realtime_api.py
    │   └── utils.py
    ├── scripts/
    │   ├── collect_realtime_history.py
    │   ├── preprocess.py
    │   └── train_models.py
    ├── processed/
    ├── models/
    └── requirements.txt
```

## Run Locally

From the repository root:

```bash
cd dashboard
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
shiny run app.py --host 0.0.0.0 --port 8005
```

Then open:

```text
http://localhost:8005
```

## Test

From the repository root, with the dashboard virtual environment active:

```bash
pip install pytest
pytest dashboard/tests
```

The latest verification during final dashboard development passed the dashboard test suite.

## Deploy

See [DEPLOYMENT.md](DEPLOYMENT.md) for the shinyapps.io deploy command, AQICN token handling, and realtime crawler instructions.

## Documentation for Final Submission

- [project_plan.md](project_plan.md): final project status, rubric mapping, and report points.
- [final_report_draft.md](final_report_draft.md): prose draft for the final 6-page LaTeX report.
- [slide_structure.md](slide_structure.md): final presentation and live-demo slide plan.
- [dashboard/walkthrough.md](dashboard/walkthrough.md): live demo checklist and Q&A guide.
- [DEPLOYMENT.md](DEPLOYMENT.md): shinyapps.io and realtime crawler operations.

## Acknowledgements

Historical datasets are credited to their Kaggle authors (`hau100416`, `phungdinhdat`). Realtime data is from AQICN / WAQI with Open-Meteo fallback. The dashboard is built with Python Shiny, Plotly, Pandas, scikit-learn, and Joblib.
