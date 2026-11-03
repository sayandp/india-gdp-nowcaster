# Excel dashboard

`gdp_nowcaster.xlsx` summarises the India GDP Nowcaster results from `data/processed`. It changes no results.

| Sheet | Contents |
|---|---|
| Dashboard | KPI tiles and four charts, in a frosted-glass style |
| Backtest | Every real-time nowcast, with error and whether it beat naive |
| Metrics | n, RMSE, MAE, bias, RMSE relative to naive and Diebold-Mariano p, by model, variant and nowcast date |
| Live call | The 2026Q3 forecasts. Type the first print into cell D4 on 30 Nov, and the error columns fill in |
| Data & method | Indicator coverage, limitations and sources |

## Rebuild and check

```bash
python dashboard/build_dashboard.py    # writes gdp_nowcaster.xlsx and assets/glass_bg.png
python dashboard/verify_dashboard.py   # checks every number against data/processed
```

Set `DASHBOARD_XLSX` to write or check a copy somewhere else, for example while the workbook is open in Excel.

## Screen vs print

**The Dashboard's gradient background shows on screen only.** Excel sheet backgrounds don't print and aren't included in PDF export, so the printed or PDF version falls back to white. The cards stay translucent white, so on white they read as plain white panels.

**Other Excel quirks:**
- The frosted cards are shapes with transparency, behind the charts.
- xlsxwriter can't set transparency or rounded corners on shapes. The build script adds both to the saved file's drawing XML.
- Excel's own drawing order puts the cards behind the charts.
