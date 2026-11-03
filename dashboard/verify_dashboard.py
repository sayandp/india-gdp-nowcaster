"""Check every number in dashboard/gdp_nowcaster.xlsx against data/processed (backtest_*.csv and the other inputs).

Usage: python dashboard/verify_dashboard.py
"""
import os
import re
import warnings
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)  # openpyxl doesn't read conditional-format extensions
ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
wb = openpyxl.load_workbook(os.environ.get("DASHBOARD_XLSX", ROOT / "dashboard" / "gdp_nowcaster.xlsx"))
NAMES = {"1 Naive": "Naive", "2 AR(1)": "AR(1)", "3 Bridge: core 8": "Bridge · Core 8", "4 Bridge + AR: core 8": "Bridge + AR · Core 8",
         "5 Bridge: IIP": "Bridge · IIP", "6a Bridge + exports": "Bridge · Core 8 + Exports", "6b Bridge + GST": "Bridge · Core 8 + GST",
         "7a Bridge + e-way bills [look-ahead]": "Bridge · Core 8 + E-way bills [look-ahead]",
         "7b Bridge + diesel [look-ahead]": "Bridge · Core 8 + Diesel [look-ahead]", "8 Change: Δ core 8": "Change model"}
VAR = {"drop": "COVID dropped", "dummy": "COVID dummy"}
COVID = {str(p) for p in pd.period_range("2020Q2", "2022Q2", freq="Q")}
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))

def sheet_table(ws, name):
    t = ws.tables[name]
    rows = list(ws[t.ref])
    head = [c.value for c in rows[0]]
    return pd.DataFrame([[c.value for c in r] for r in rows[1:]], columns=head)

def close(a, b, tol=1e-6):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return bool(np.all((np.isnan(a) & np.isnan(b)) | (np.abs(a - b) <= tol)))

nc = pd.read_csv(P / "backtest_nowcasts.csv")
mx = pd.read_csv(P / "backtest_metrics_main_without_2022Q3.csv")
mm = pd.read_csv(P / "backtest_metrics_main.csv")
cv = pd.read_csv(P / "backtest_metrics_covid.csv")
gdp = pd.read_csv(P / "gdp.csv", parse_dates=["release_date"]).set_index("quarter")

# Backtest sheet: every nowcast
bt = sheet_table(wb["Backtest"], "Backtest")
src = nc.assign(model_name=nc.model.map(NAMES), variant_name=nc.variant.map(VAR))
key = ["quarter", "date", "model_name", "variant_name"]
m = bt.rename(columns={"nowcast_date": "date", "model": "model_name", "variant": "variant_name"}).merge(src, on=key, suffixes=("_x", ""), how="outer", indicator=True)
check("Backtest: same rows as backtest_nowcasts.csv", (m._merge == "both").all() and len(bt) == len(nc), f"{len(bt)} rows")
check("Backtest: nowcast", close(m.nowcast_x, m.nowcast))
check("Backtest: actual", close(m.actual_x.astype(float), m.actual))
check("Backtest: error = nowcast - actual", close(m.error, m.nowcast - m.actual))
check("Backtest: abs_error", close(m.abs_error, (m.nowcast - m.actual).abs()))
check("Backtest: is_covid", (m.is_covid == m.quarter.isin(COVID)).all())
nerr = src[src.model == "1 Naive"].assign(naive_abs=lambda d: (d.nowcast - d.actual).abs()).set_index(["variant", "date", "quarter"])["naive_abs"]
exp = (m.nowcast - m.actual).abs().values < nerr.reindex(pd.MultiIndex.from_frame(m[["variant", "date", "quarter"]])).values
nn = m.model != "1 Naive"
check("Backtest: beats_naive", (m.beats_naive[nn].astype(bool).values == exp[nn.values]).all() and m.beats_naive[~nn].isna().all())

# Metrics sheet
mt = sheet_table(wb["Metrics"], "Metrics")
samples = {"Non-COVID, excluding 2022Q3 (headline)": mx, "Non-COVID, including 2022Q3": mm, "COVID quarters": cv}
ok_all, n_cmp = True, 0
for s, d in samples.items():
    d = d.assign(model_name=d.model.map(NAMES), variant_name=d.variant.map(VAR))
    x = mt[mt["sample"] == s].merge(d, left_on=["variant", "nowcast_date", "model"], right_on=["variant_name", "date", "model_name"], suffixes=("", "_c"))
    ok_all &= len(x) == len(d) == (mt["sample"] == s).sum()
    for a, b in [("n", "n_c"), ("rmse", "rmse_c"), ("mae", "mae_c"), ("bias", "bias_c"), ("rel_rmse_vs_naive", "rel_rmse"), ("dm_p", "dm_p_c")]:
        ok_all &= close(x[a], x[b]); n_cmp += len(x)
check("Metrics: n, RMSE, MAE, bias, relative RMSE, DM p match the three metrics CSVs", ok_all, f"{n_cmp} values")

# Chart data
cd = wb["chart_data"]
col = lambda c, r0, r1: [cd.cell(r, c).value for r in range(r0, r1 + 1)]
head_q = [x for x in pd.period_range("2022Q4", "2025Q3", freq="Q").astype(str) if x not in COVID]
assert mx[(mx.variant == "dummy") & (mx.model == "1 Naive") & (mx.date == "D+0")].quarters.iloc[0] == "2022Q4-2025Q3"
bi = nc[(nc.model == "5 Bridge: IIP") & (nc.variant == "dummy") & nc.quarter.isin(head_q)]
c1q = sorted(set.intersection(*[set(bi[bi.date == d].quarter) for d in ["D+0", "D+32", "D+45"]]))
def rm(model, d):
    x = nc[(nc.model == model) & (nc.variant == "dummy") & (nc.date == d) & nc.quarter.isin(c1q)]
    return round(float(np.sqrt(((x.nowcast - x.actual) ** 2).mean())), 4)
check("Chart 1: Bridge · IIP RMSE on one quarter set at all dates", close(col(2, 2, 4), [rm("5 Bridge: IIP", d) for d in ["D+0", "D+32", "D+45"]]), f"n = {len(c1q)}")
check("Chart 1: naive on the same quarters, flat", close(col(3, 2, 4), [rm("1 Naive", d) for d in ["D+0", "D+32", "D+45"]]) and len(set(col(3, 2, 4))) == 1)
window = [str(p) for p in pd.period_range("2017Q2", "2025Q3", freq="Q")]
check("Chart 2: first prints", close(col(6, 2, 35), gdp.loc[window, "gdp_growth_first_print"]))
b = nc[(nc.model == "5 Bridge: IIP") & (nc.variant == "dummy") & (nc.date == "D+32")].set_index("quarter").nowcast.reindex(window)
check("Chart 2: best model nowcasts at D+32", close([np.nan if v is None else v for v in col(7, 2, 35)], b.round(4)))
nv = nc[(nc.model == "1 Naive") & (nc.variant == "dummy") & (nc.date == "D+32")].set_index("quarter").nowcast.reindex(window)
check("Chart 2: naive", close(col(8, 2, 35), nv))
check("Chart 2: COVID band covers 2020Q2 to 2022Q2 only", [q for q, v in zip(window, col(9, 2, 35)) if v] == sorted(COVID))
c3 = mx[(mx.date == "D+32") & (mx.model != "1 Naive")].sort_values("rel_rmse")
check("Chart 3: relative RMSE at D+32", close(col(13, 2, 1 + len(c3)), c3.rel_rmse.round(4)))
q = pd.read_csv(P / "indicators_quarterly.csv")
c8 = q[(q.indicator == "core8_overall_base2011") & (q.vintage == "latest")].set_index("quarter").yoy_pct  # chart 4 uses latest vintage
c8f = q[(q.indicator == "core8_overall_base2011") & (q.vintage == "first")].set_index("quarter").yoy_pct
gq = [str(p) for p in pd.period_range("2023Q1", "2025Q3", freq="Q")]
g = gdp.gdp_growth_first_print.reindex(gq)
check("Chart 4: GDP", close(col(17, 2, 12), g))
check("Chart 4: core 8 YoY, latest vintage, no blanks", close(col(18, 2, 12), c8.reindex(gq).round(4)) and None not in col(18, 2, 12))
check("Chart 4: gap", close(col(19, 2, 12), (g - c8.reindex(gq)).round(4)))

# Dashboard numbers
ws = wb["Dashboard"]
import zipfile
XLSX = os.environ.get("DASHBOARD_XLSX", ROOT / "dashboard" / "gdp_nowcaster.xlsx")
with zipfile.ZipFile(XLSX) as z:
    drawing = z.read("xl/drawings/drawing1.xml").decode("utf8")  # Dashboard is sheet 1
    sheet1 = z.read("xl/worksheets/sheet1.xml").decode("utf8")
    media = [n for n in z.namelist() if n.startswith("xl/media/")]
    dash_charts = [z.read(n).decode("utf8") for n in sorted(z.namelist()) if re.fullmatch(r"xl/charts/chart[1-4]\.xml", n)]
# KPI and chart-header text now lives in text boxes, so read paragraphs from the drawing as well as cells
box_text = ["".join(re.findall(r"<a:t>(.*?)</a:t>", p_)) for p_ in re.findall(r"<a:p>.*?</a:p>", drawing, flags=re.S)]
texts = {str(c.value) for row in ws.iter_rows() for c in row if c.value is not None} | {t.replace("&amp;", "&") for t in box_text if t}
best_rel = mx.rel_rmse.min()
dm_texts = {str(c.value) for row in wb["Data & method"].iter_rows() for c in row if c.value is not None}
best_n = int(mx[mx.rel_rmse == best_rel].n.iloc[0])
check("KPI: best relative RMSE 0.97", "0.97" in texts and round(best_rel, 2) == 0.97)
check("KPI 1 label names the 12 quarters", f"Best relative RMSE vs naive ({best_n} quarters)" in texts and best_n == 12)
check("KPI 1 subtext is 'Bridge · IIP, D+32'", "Bridge · IIP, D+32" in texts and mx[mx.rel_rmse == best_rel].model.iloc[0] == "5 Bridge: IIP")
check("Chart 1 subtitle states n", any(f"n = {len(c1q)}" in t for t in texts))
check("Chart 1 subtitle reconciles with KPI 1",
      f"On the {len(c1q)} quarters shared by all dates; on all {best_n} at D+32 it's {best_rel:.2f}" in texts and len(c1q) == 10)
c1x, c2x = dash_charts[0], dash_charts[1]
c1vals = col(2, 2, 4) + col(3, 2, 4)
check("Chart 1: y-axis 0.8 to 1.4, all values inside", '<c:min val="0.8"/>' in c1x and '<c:max val="1.4"/>' in c1x and 0.8 <= min(c1vals) and max(c1vals) <= 1.4)
check("Chart 2: COVID band grey #8E8E93 at 80% transparency, no peach",
      c2x.count('<a:srgbClr val="8E8E93"><a:alpha val="20000"/></a:srgbClr>') == 2 and "FFE0DE" not in c2x)
foot = [str(c.value) for row in ws.iter_rows() for c in row if c.value is not None and "13.5%" in str(c.value)]
check("Footnote: one cell, at most 2 short lines, points to Data & method",
      len(foot) == 1 and foot[0].count("\n") <= 1 and all(len(l_) <= 130 for l_ in foot[0].split("\n")) and "Data & method" in foot[0])
check("KPI: 12 test quarters", "12" in texts and int(mx[mx.rel_rmse == best_rel].n.iloc[0]) == 12)
nr = round(float(mx[(mx.variant == "drop") & (mx.date == "D+32") & (mx.model == "1 Naive")].rmse.iloc[0]), 2)
check("KPI: live naive 7.8% ± 1.05", "7.8%" in texts and gdp.loc["2026Q2", "gdp_growth_first_print"] == 7.8 and nr == 1.05 and any("± 1.05" in t for t in texts))
d = (gdp.loc[window, "release_date"] - pd.PeriodIndex(window, freq="Q").end_time.normalize()).dt.days
check("KPI: median 61 days (range 57 to 62)", "61" in texts and d.median() == 61 and any("range 57 to 62" in t for t in texts) and (d.min(), d.max()) == (57, 62))
check("Title: within 3% of naive", any("within 3%" in t for t in texts) and round(100 * (1 - best_rel)) == 3)
gl, gf = g - c8.reindex(gq), g - c8f.reindex(gq)
fl = (round(gl.loc["2023Q1":"2024Q2"].mean(), 1), round(gl.loc["2024Q3":"2025Q3"].mean(), 1))
ff = (round(gf.loc["2023Q1":"2024Q2"].mean(), 1), round(gf.loc["2024Q3":"2025Q3"].mean(), 1))
check(f"Data & method notes: latest-vintage gap {fl[0]} then {fl[1]}", any(f"{fl[0]} points in 2023Q1 to 2024Q2 and {fl[1]} in" in t for t in dm_texts))
check(f"Data & method notes: first-print gap {ff[0]} and {ff[1]}, as in the report", ff == (0.2, 3.9) and any(f"it is {ff[0]} and {ff[1]}" in t for t in dm_texts))
check("Dashboard: columns right of Q hidden", any(d.hidden and d.min == 18 and d.max == 16384 for d in ws.column_dimensions.values()) and not any(d.hidden and d.min <= 17 for d in ws.column_dimensions.values()))
check("Footer: 13.5% carried into 2022Q3", any("13.5%" in t for t in texts) and gdp.loc["2022Q2", "gdp_growth_first_print"] == 13.5)

# Glass style (Dashboard)
anchors = re.findall(r"<xdr:twoCellAnchor.*?</xdr:twoCellAnchor>", drawing, flags=re.S)
kinds = ["shape" if "<xdr:sp" in a_ else "chart" for a_ in anchors]
cards = [a_ for a_ in anchors if 'descr="glass card"' in a_]
check("Glass: background image attached to the Dashboard", "<picture " in sheet1 and len(media) >= 1)
check("Glass: no cell fills on the Dashboard", all(c.fill is None or c.fill.fill_type in (None, "none") for row in ws.iter_rows(min_row=1, max_row=50, max_col=17) for c in row))
check("Glass: 8 rounded cards, white at 40% transparency with a 40% white border",
      len(cards) == 8 and all('prst="roundRect"' in c_ and c_.count('<a:alpha val="60000"/>') == 2 for c_ in cards))
check("Glass: cards and text drawn behind the charts", kinds == ["shape"] * kinds.count("shape") + ["chart"] * 4)
check("Glass: dashboard chart and plot areas have no fill or border", len(dash_charts) >= 4 and all(x.count("<a:noFill/>") >= 4 for x in dash_charts[:4]))

# Live call sheet against the live file
lv = sheet_table(wb["Live call"], "LiveCall")
live = (ROOT / "reports" / "live_nowcast_2026Q3.md").read_text(encoding="utf8")
mb = re.search(r"\| 3 Bridge: core 8 \| ([\d.]+)% \| ([\d.]+)% to ([\d.]+)%", live)
mc = re.search(r"\*\*Model 8.*?:\*\* ([\d.]+)% \(range ([\d.]+)% to ([\d.]+)%", live)
expect = [(7.8, 7.8 - nr, 7.8 + nr), tuple(map(float, mb.groups())), tuple(map(float, mc.groups()))]
check("Live call: nowcasts and ranges", close(lv[["nowcast", "range_low", "range_high"]].values, expect))
check("Live call: only naive is primary", list(lv.is_primary) == [True, False, False])
check("Live call: made on 3 Nov 2026", all(pd.Timestamp(v) == pd.Timestamp("2026-11-03") for v in lv.made_on) and "Made on 03 Nov 2026" in live)
f = wb["Live call"]
check("Live call: actual and error are formulas", all(str(f.cell(r, 8).value).startswith("=") and str(f.cell(r, 7).value).startswith("=") for r in range(7, 10)))
check("Live call: error bars match ranges", close(col(23, 2, 4), [round(h - n, 4) for n, l, h in expect]) and close(col(24, 2, 4), [round(n - l, 4) for n, l, h in expect]))

out = pd.DataFrame(results, columns=["check", "ok", "detail"])
print(out.to_string(index=False))
print(f"\n{out.ok.sum()} of {len(out)} checks passed")
raise SystemExit(0 if out.ok.all() else 1)
