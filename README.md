# Hanoi Air Quality Pulse

<p align="center">
  <img src="dashboard/hanoi_skyline.png" alt="Hanoi skyline" width="100%"/>
</p>

<p align="center">
  <em>Interactive spatial, temporal, realtime, and predictive visualization of Hanoi air pollution.</em>
</p>

---

## Overview

**Hanoi Air Quality Pulse** is an interactive Python Shiny dashboard that moves Hanoi's air quality story beyond a single citywide AQI number. It lets users explore pollution across **30 districts**, multiple pollutants, weather drivers, realtime stations, and short-term AQI / PM2.5 forecasts.

Central question:

> **How does air pollution vary across Hanoi districts and time, and can recent air-quality and weather signals support short-term AQI risk prediction?**

## Dashboard Tour

### 1. Overview

Realtime AQI hero, weather drivers, day-vs-night pattern, live station map, and a mood-changing mascot ("Lexce") that mirrors current AQI risk.

![Overview tab](image/overview.png)

### 2. Districts

Choropleth across Hanoi's 30 districts with multi-select filtering, ranking heatmap, monthly trends, and pollutant breakdown for the selected districts.

![Districts tab — map and picker](image/district1.png)
![Districts tab — ranking and trend](image/district2.png)

### 3. History

GitHub-style calendar heatmap, multi-year comparison, AQI-category distribution, and annual/seasonal pattern tracking.

![History tab — calendar heatmap](image/history1.png)
![History tab — multi-year overlay](image/history2.png)
![History tab — category distribution](image/history3.png)

### 4. Forecast

Short-term predictions for AQI and PM2.5 at 1h / 6h / 24h horizons, with model-vs-baseline error, feature importance, and validation plots.

![Forecast tab — prediction card](image/Forecast1.png)
![Forecast tab — model vs baseline](image/Forecast2.png)
![Forecast tab — validation plot](image/Forecast3.png)

## Datasets

| Dataset | Source | Scope | Used for |
|---|---|---|---|
| District-level Hanoi air quality | Kaggle `hau100416/vietnamese-air-quality-dataset` | 30 districts, 920,160 hourly rows, 2022-08-04 → 2026-02-01 | District map, ranking, trends, pollutant breakdown |
| City-level AQI + weather | Kaggle `phungdinhdat/aqi-in-hanoi-2022-2025` | 30,341 hourly rows, 2022-01-13 → 2025-06-30 | Overview hero, History page, Forecast model training |
| Hanoi district boundaries | `data/hanoi_districts.geojson` | 30 districts, name-matched | Choropleth boundaries |
| AQICN / WAQI | API | Realtime stations | Live station map, current AQI |
| Open-Meteo | API | Fallback weather / air | Used when AQICN is unavailable |

City-level fields include AQI, PM2.5, PM10, CO, NO2, O3, SO2, temperature, humidity, pressure, precipitation, clouds, wind speed, and UV index.

## Forecasting Method

- **Targets:** AQI (primary), PM2.5 (secondary).
- **Horizons:** 1h, 6h, 24h.
- **Features:** current pollutants, weather variables, time features (hour / day-of-week / month / weekend), lag features (1h / 6h / 24h), rolling mean & max windows (3h / 6h / 24h).
- **Models:** scikit-learn Histogram Gradient Boosting Regressor variants, selected by chronological validation MAE.
- **Baseline:** persistence / no-change forecast.
- **Explanation:** error comparison vs baseline, feature importance, and predicted-vs-actual validation chart.

Trained models are cached as `.joblib` files in `dashboard/models/` so the app starts instantly without re-training.

## Tech Stack

- **Dashboard:** Python Shiny, Plotly, custom dark CSS theme.
- **Data:** Pandas, NumPy, Parquet preprocessing.
- **Modeling:** scikit-learn, Joblib model cache.
- **Spatial / realtime:** Hanoi GeoJSON, AQICN/WAQI API, Open-Meteo fallback.

## Quick Start

```bash
git clone git@github.com:songiangvn/Hanoi-AQI-Pulse.git
cd Hanoi-AQI-Pulse/dashboard

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

shiny run app.py --host 0.0.0.0 --port 8005
```

Then open [http://localhost:8005](http://localhost:8005).

### Pretrain the forecast models (optional, faster first load)

```bash
cd dashboard
.venv/bin/python scripts/train_models.py
```

### AQICN token

The app reads the realtime token from, in order:

1. `AQICN_TOKEN` environment variable.
2. `aqicn_api_key.md` (regex-extracted).

If both are missing or AQICN is down, the dashboard falls back to Open-Meteo for the selected coordinate.

## Repository Layout

```
HaNoiAQI/
├── README.md                  ← you are here
├── project_plan.md            Full project plan (proposal + phase 2)
├── proposal_writeup.md        Short proposal write-up
├── slide_structure.md         Proposal slide outline
├── image/                     Screenshots used in slides / README
├── data/                      Datasets (only the small GeoJSON is committed)
└── dashboard/
    ├── app.py                 Shiny app entry point
    ├── styles.css             Dark theme + custom layout
    ├── hanoi_skyline.png      Hero background
    ├── modules/               Per-tab UI + server (Overview / Districts / History / Forecast)
    ├── src/                   Data loading, model, realtime API, utilities
    ├── scripts/               Preprocessing + model training scripts
    ├── processed/             Compact Parquet inputs
    ├── models/                Cached forecast models (.joblib)
    └── requirements.txt
```

## Documentation

- [Project plan](project_plan.md) — datasets, dashboard tabs, forecasting method, team plan, risks.
- [Proposal write-up](proposal_writeup.md) — concise problem statement and approach.
- [Slide structure](slide_structure.md) — 5-minute presentation outline with annotated screenshots.

## Roadmap

- Polish the wide-format Hanoi background and mobile layout.
- Strengthen model explanation and per-district forecasting.
- Deploy to shinyapps.io.
- Final 6-page LaTeX report and live demo.

## License & Acknowledgements

Datasets © their respective Kaggle authors (`hau100416`, `phungdinhdat`). Realtime data © AQICN / WAQI and Open-Meteo. Built with Python Shiny, Plotly, and scikit-learn.
