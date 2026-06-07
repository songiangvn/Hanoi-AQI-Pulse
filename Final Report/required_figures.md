# Figures — Hanoi Air Quality Pulse Final Report

**Status: all figures supplied and wired into `final_report.tex`.** Everything lives in the
`Final Report/` folder. Compile from inside that folder.

The report has 5 figures. Four are dashboard screenshots (two stacked sub-images each, (a)/(b) with
sub-captions); the fifth is an inline TikZ architecture diagram (no image file).

| Fig | `\label` | Image files | What they show |
|---|---|---|---|
| 1 | `fig:overview`  | `fig_overview_1.jpg`, `fig_overview_2.jpg`   | (a) hero AQI + scale + skyline + advisory; (b) 24h realtime line w/ 1h forecast, peak cards, PM2.5 exposure, 3D map + mascot |
| 2 | `fig:districts` | `fig_districts_1.jpg`, `fig_districts_2.jpg` | (a) selector + presets + 3D choropleth + ranking heatmap-table; (b) linked monthly trend + pollutant breakdown |
| 3 | `fig:history`   | `fig_history_1.jpg`, `fig_history_2.jpg`     | (a) controls + quality note + calendar heatmap + seasonal overlay; (b) category-mix donut + month×year matrix |
| 4 | `fig:forecast`  | `fig_forecast_1.jpg`, `fig_forecast_2.jpg`   | (a) controls + forecast hero + source chip + Lexce + Key-Drivers radar; (b) model-vs-baseline bars + PCA learning space + backtest |
| 5 | `fig:arch`      | — (inline TikZ)                              | data → preprocess → train → app; SLURM crawler → Hugging Face → app |

## To compile
```
cd "Final Report"
pdflatex final_report.tex && pdflatex final_report.tex   # twice, for \pageref{LastPage}
```

## Adjusting figure size
Each sub-image is `\includegraphics[width=\linewidth]` inside a `subfigure` of width `0.86\textwidth`.
To shrink a whole figure, lower the `0.86\textwidth` on its `\begin{subfigure}{...}` lines (e.g. `0.72`).
Eight wide screenshots make the document run long — see the length note below.

## Note on length / 6-page limit
With two stacked screenshots per tab, the report will likely exceed the 6-page guideline. Options if it
must fit: (a) move the four screenshot figures into an **Appendix** after the References (keeps the
analytical body ~5–6 pages); (b) shrink the sub-figure widths to ~0.70; or (c) use one composite image
per tab instead of two. Confirm exact length by compiling.
