# Hanoi Air Quality Pulse: Final Report Draft

This Markdown draft is intended to be converted into the final 6-page LaTeX report. It is written to match the final dashboard state on shinyapps.io.

## Abstract

Hanoi Air Quality Pulse is a Python Shiny dashboard for exploring Hanoi air pollution through realtime monitoring, district-level spatial comparison, historical pattern analysis, and short-term forecasting. The project addresses the question: how does air pollution vary across Hanoi districts and time, and can recent air-quality and weather signals support short-term AQI risk prediction? The final application combines two historical Kaggle datasets, Hanoi district GeoJSON boundaries, AQICN / WAQI realtime station readings, Open-Meteo fallback context, and cached scikit-learn forecasting models. The deployed shinyapps.io dashboard contains four linked pages: Overview, Districts, History, and Forecast. Its main contribution is integration: users can move from a live AQI reading to district maps, anomaly-aware historical charts, and interpretable model forecasts in one workflow.

## 1. Motivation and Problem

Air quality is usually communicated as a single citywide number, but that number hides important variation. In Hanoi, exposure can change by district, hour of day, season, pollutant, and weather condition. A static chart is therefore not sufficient for understanding the public-health context. Users need to know what is happening now, where pollution appears concentrated, how current conditions compare with historical patterns, and whether short-term risk is expected to change.

The dashboard is designed around three goals. First, it should make current AQI interpretable without requiring technical knowledge. Second, it should support exploratory comparison across Hanoi's 30 districts and multiple time scales. Third, it should embed short-term machine learning forecasts into the visual workflow rather than presenting the model as a detached technical result.

## 2. Data and Preprocessing

The application uses two main historical datasets. The district-level source is Kaggle `hau100416/vietnamese-air-quality-dataset`, locally processed into Hanoi-specific data covering 30 districts, 920,160 hourly rows, and the period from 2022-08-04 to 2026-02-01. This dataset drives the district maps, district ranking table, selected-district monthly trends, and pollutant breakdowns.

The city-level modeling source is Kaggle `phungdinhdat/aqi-in-hanoi-2022-2025`, containing 30,341 hourly rows from 2022-01-13 to 2025-06-30. Its fields include AQI, PM2.5, PM10, CO, NO2, O3, SO2, temperature, humidity, pressure, precipitation, wind, clouds, and UV index. This dataset supports the Overview fallback state, the History tab, and the forecasting models.

Spatial boundaries are loaded from `data/hanoi_districts.geojson` and name-matched to the 30 district names in the air-quality data. Processed data is stored as compact Parquet files to reduce app startup time. Forecast models are trained offline and cached as Joblib artifacts so that deployment does not retrain models during the live demo.

Air-quality time series can contain both true pollution episodes and sensor-like anomalies. The final dashboard uses an anomaly-aware cleaned series for production charts and forecasting. The preprocessing applies physical plausibility checks, rolling robust statistics, and isolated-spike handling. Importantly, unusual observations are not simply hidden: the History tab includes a "Show anomaly markers" control so users can inspect flagged spikes or unusual episodes directly.

## 3. Realtime Architecture and Deployment

The app is deployed on shinyapps.io under the app title `hanoi-aqi-pulse`. Because shinyapps.io processes may sleep or restart when nobody is connected, realtime collection is handled outside the Shiny session. A SLURM job on the department server runs `run_slurm_realtime_crawler.sh`, which calls `dashboard/scripts/collect_realtime_history.py` approximately every 10 minutes. The crawler records AQICN / WAQI station observations and uploads `realtime_history.csv` to the Hugging Face Dataset `MountainRiver/hanoi-aqi-realtime-history`.

The deployed app reads this CSV as its lightweight realtime history source. This design makes the dashboard more reliable for the final demo because data collection continues even when the app is not open. The current crawler stores timestamp, source, station name, AQI, PM2.5, PM10, latitude, and longitude. If AQICN is unavailable or incomplete, the app falls back to Open-Meteo or cleaned historical context. The forecast UI makes this source state explicit with production-style input chips, so users can distinguish live input from fallback context.

## 4. Visualization and Interaction Design

The final application is organized into four pages.

The Overview page provides the current AQI story. It includes a realtime AQI hero, weather context, a "Realtime AQI History - Last 24 Hours" chart, the model's 1-hour forecast extension, day/night AQI summaries, a 24h PM2.5 exposure card, a 3D / 2D Hanoi AQI map, and the Lexce mascot. The realtime chart separates observations from prediction using a yellow observed line and a cyan dashed forecast segment with a diamond marker. This makes the model output visible without confusing it with measured data.

The Districts page supports spatial comparison. Users can select districts manually or with shortcuts such as Select all, Top 5, Above avg, and PM2.5 hotspots. Year and month controls allow the map and ranking table to move beyond a fixed annual average. The district map can be shown in either 3D or 2D. The 3D version includes district labels and bright top boundary lines to make each district shape readable. Selection is linked across the map, ranking heatmap table, monthly trend, and pollutant breakdown.

The History page focuses on time. It includes a calendar heatmap, seasonal comparison by selectable month, air-quality category mix by year, and a monthly category matrix. The anomaly-marker toggle is important because it lets viewers inspect data-quality events while the main production views remain stable and readable.

The Forecast page presents predictive analytics. Users can choose AQI or PM2.5 and a 1h, 6h, or 24h horizon. The page shows a forecast summary card, risk gauge, Lexce forecast mood, Key Prediction Drivers radar chart, Model Learning Space PCA plot, backtest chart, and model-vs-baseline error comparison. The PCA plot is a projection of engineered regression features, not a neural embedding. It is included to show where the current forecast case sits relative to historical backtest cases and whether high-error regions are visible.

The chart inventory exceeds the requirement of at least five charts and three chart types. The final dashboard uses line/area charts, 2D maps, 3D spatial maps, calendar heatmaps, ranking heatmaps, donut charts, radar charts, gauge charts, PCA scatter plots, backtest charts, and narrative KPI cards. Accessibility improvements include keyboard focus states, high-contrast insight text, larger control hit areas, reduced-motion support, ARIA labels, and 2D alternatives for 3D maps.

## 5. Forecasting Method

The forecasting component is framed as short-term risk prediction rather than exact sensor simulation. Models are trained for two targets, AQI and PM2.5, at three horizons: 1h, 6h, and 24h. Input features include current pollutants, weather variables, time features, lag features, and rolling mean/max windows. The model family is scikit-learn `HistGradientBoostingRegressor`, selected through a chronological validation split to avoid future leakage. The comparison baseline is a persistence forecast, meaning the future value is assumed to stay equal to the current value.

Table 1 summarizes the cleaned-series model artifacts used in the final app.

| Target / horizon | Selected model | Model MAE | Baseline MAE | Improvement |
|---|---|---:|---:|---:|
| AQI 1h | HistGB-Absolute | 18.80 | 19.15 | 1.8% |
| AQI 6h | HistGB-Squared | 30.33 | 37.09 | 18.2% |
| AQI 24h | HistGB-Absolute | 35.37 | 44.43 | 20.4% |
| PM2.5 1h | HistGB-Absolute | 11.89 | 11.73 | -1.4% |
| PM2.5 6h | HistGB-Absolute | 20.82 | 25.64 | 18.8% |
| PM2.5 24h | HistGB-Absolute | 24.59 | 29.94 | 17.9% |

The results show that the model is most useful for longer horizons, where persistence becomes weaker. AQI improves over persistence at all three horizons, with stronger gains at 6h and 24h. PM2.5 has a small negative improvement at 1h, which is an honest limitation: for very short-term PM2.5, persistence is already a strong baseline. The dashboard therefore shows baseline error alongside model error rather than only displaying a single forecast number.

## 6. Findings and Discussion

The final dashboard supports several findings. First, Hanoi air quality has meaningful temporal structure. Day/night summaries and seasonal comparison charts show that the pattern is not just a sequence of independent daily readings. Second, district-level views reveal spatial differences that are hidden by a citywide AQI number. Linked district selection makes it possible to inspect which districts are driving high values in a given month or year.

Third, anomaly-aware design improves interpretability. Cleaning improves chart stability and model training, but anomaly markers preserve visibility of unusual events. This balances production readability with analytical honesty. Fourth, realtime history makes the Overview page operational: users can see recent live readings and an explicit 1h forecast continuation rather than only historical summaries. Finally, the forecast diagnostics help avoid black-box presentation. The radar chart, PCA feature-space view, backtest chart, and baseline comparison give users multiple ways to understand what the model is doing and where it may be less reliable.

## 7. Reflection, Limitations, and Future Work

The strongest design choice was to combine overview-first public communication with deeper analytical pages. The mascot and exposure card make risk understandable, while the maps, history charts, and forecast diagnostics preserve quantitative depth. Providing both 3D and 2D maps was also important: 3D improves spatial storytelling and makes landmarks/station columns memorable, while 2D remains simpler and more accessible.

There are several limitations. Realtime station coverage can be sparse or stale. The crawler currently stores AQI, PM2.5, PM10, coordinates, source, and timestamps, but not every weather or secondary pollutant feature used during model training. The forecast therefore uses live values where available and fallback context for missing features. This is transparent in the UI but should not be overstated as a fully realtime feature pipeline. Forecasting is also city-level rather than district-specific. The 3D maps are visual encodings for context and risk, not precise physical terrain or building-height models.

Future work would include storing richer realtime weather and pollutant features, adding uncertainty bands to forecasts, training district-specific models where data density allows, and conducting formal accessibility user testing. A longer-term version could also support alerts, user-selected locations, and uncertainty-aware exposure recommendations.

## Suggested Figures for LaTeX

- Figure 1: Overview page showing realtime AQI hero, realtime history, prediction extension, and Hanoi AQI map.
- Figure 2: Districts page showing 3D District AQI Map and linked ranking table.
- Figure 3: History page showing anomaly markers and category mix.
- Figure 4: Forecast page showing forecast card, radar drivers, and PCA learning space.
- Figure 5: Architecture diagram: historical data, realtime crawler, HF Dataset, cached models, Shiny deployment.

## References / Credits

- Kaggle dataset `hau100416/vietnamese-air-quality-dataset`.
- Kaggle dataset `phungdinhdat/aqi-in-hanoi-2022-2025`.
- AQICN / WAQI realtime station data.
- Open-Meteo fallback data.
- Python Shiny, Plotly, Pandas, scikit-learn, Joblib.
