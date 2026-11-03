"""Build dashboard/gdp_nowcaster.xlsx from existing files in data/processed and reports/. Changes no results.

Usage: python dashboard/build_dashboard.py
"""
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import xlsxwriter
from PIL import Image, ImageDraw, ImageFilter
from xlsxwriter.utility import xl_rowcol_to_cell

ROOT = Path(__file__).resolve().parents[1]
P, R = ROOT / "data" / "processed", ROOT / "reports"
OUT = Path(os.environ.get("DASHBOARD_XLSX", ROOT / "dashboard" / "gdp_nowcaster.xlsx"))

# Tokens: Apple system palette; Segoe UI Variable (SF Pro isn't installed), named instances for weights
BG, CARD, INK, SEC, HAIR = "#F5F5F7", "#FFFFFF", "#1D1D1F", "#6E6E73", "#E5E5EA"
BLUE, GRAY, RED, GREEN, ORANGE = "#007AFF", "#8E8E93", "#FF3B30", "#34C759", "#FF9500"
GREEN_TINT, RED_TINT = "#DDF6E3", "#FFE0DE"
SEC_GLASS = "#3A3A3C"  # darker secondary text for contrast on the glass background
BG_IMAGE = ROOT / "dashboard" / "assets" / "glass_bg.png"
DISPLAY, DISPLAY_SEMI = "Segoe UI Variable Display", "Segoe UI Variable Display Semib"
TEXT, TEXT_SEMI = "Segoe UI Variable Text", "Segoe UI Variable Text Semibold"

NAMES = {"1 Naive": "Naive", "2 AR(1)": "AR(1)", "3 Bridge: core 8": "Bridge · Core 8", "4 Bridge + AR: core 8": "Bridge + AR · Core 8",
         "5 Bridge: IIP": "Bridge · IIP", "6a Bridge + exports": "Bridge · Core 8 + Exports", "6b Bridge + GST": "Bridge · Core 8 + GST",
         "7a Bridge + e-way bills [look-ahead]": "Bridge · Core 8 + E-way bills [look-ahead]",
         "7b Bridge + diesel [look-ahead]": "Bridge · Core 8 + Diesel [look-ahead]", "8 Change: Δ core 8": "Change model"}
VARIANTS = {"drop": "COVID dropped", "dummy": "COVID dummy"}
DATES = ["D+0", "D+32", "D+45"]
WINDOW = [str(p) for p in pd.period_range("2017Q2", "2025Q3", freq="Q")]
COVID = {str(p) for p in pd.period_range("2020Q2", "2022Q2", freq="Q")}
MAIN_ORDER = ["Naive", "AR(1)", "Bridge · Core 8", "Bridge + AR · Core 8", "Bridge · IIP", "Change model"]

# ---------- data (read only) ----------
gdp = pd.read_csv(P / "gdp.csv", parse_dates=["release_date"]).set_index("quarter")
nc = pd.read_csv(P / "backtest_nowcasts.csv", parse_dates=["asof"])
mx = pd.read_csv(P / "backtest_metrics_main_without_2022Q3.csv")
mm = pd.read_csv(P / "backtest_metrics_main.csv")
cv = pd.read_csv(P / "backtest_metrics_covid.csv")
q = pd.read_csv(P / "indicators_quarterly.csv")
mo = pd.read_csv(P / "indicators_monthly.csv")
coverage = pd.read_csv(P / "indicators_coverage.csv")
live_md = (R / "live_nowcast_2026Q3.md").read_text(encoding="utf8")
for t in (nc, mx, mm, cv):
    t["model_name"] = t.model.map(NAMES)
    assert t.model_name.notna().all()

def metric(t, variant, date, name, col):
    r = t[(t.variant == variant) & (t.date == date) & (t.model_name == name)]
    assert len(r) == 1, (variant, date, name)
    return float(r[col].iloc[0])

# Best model (Phase 4 selection: lowest mean relative RMSE over dates, models 2-5, without 2022Q3)
sel = mx[mx.model.str[0].isin(list("2345"))].groupby(["model_name", "variant"]).rel_rmse.mean().sort_values()
BEST, BEST_VAR = sel.index[0]
best_rel = metric(mx, BEST_VAR, "D+32", BEST, "rel_rmse")
best_n = int(metric(mx, BEST_VAR, "D+32", BEST, "n"))
best_p = metric(mx, BEST_VAR, "D+32", BEST, "dm_p")
assert mx.rel_rmse.min() == best_rel  # also the lowest relative RMSE anywhere in the headline table
best_quarters = mx[(mx.variant == BEST_VAR) & (mx.date == "D+32") & (mx.model_name == BEST)].quarters.iloc[0]

days = (gdp.loc[WINDOW, "release_date"] - pd.PeriodIndex(WINDOW, freq="Q").end_time.normalize()).dt.days
GDP_DAY = int(days.median())

# Live call: the live file is the record; naive ± is the variant (a) D+32 naive RMSE, as declared in the README
m_bridge = re.search(r"\| 3 Bridge: core 8 \| ([\d.]+)% \| ([\d.]+)% to ([\d.]+)%", live_md)
m_change = re.search(r"\*\*Model 8.*?, added (\d\d \w{3} \d{4}):\*\* ([\d.]+)% \(range ([\d.]+)% to ([\d.]+)%", live_md)
made = pd.to_datetime(re.search(r"Made on (\d\d \w{3} \d{4})", live_md).group(1))
naive_pt = float(gdp.loc["2026Q2", "gdp_growth_first_print"])
naive_rmse = round(metric(mx, "drop", "D+32", "Naive", "rmse"), 2)
LIVE = pd.DataFrame([
    {"forecast": "Naive (2026Q2 first print)", "is_primary": True, "made_on": made, "nowcast": naive_pt, "low": naive_pt - naive_rmse, "high": naive_pt + naive_rmse},
    {"forecast": "Bridge · Core 8", "is_primary": False, "made_on": made, "nowcast": float(m_bridge.group(1)), "low": float(m_bridge.group(2)), "high": float(m_bridge.group(3))},
    {"forecast": "Change model", "is_primary": False, "made_on": pd.to_datetime(m_change.group(1)), "nowcast": float(m_change.group(2)), "low": float(m_change.group(3)), "high": float(m_change.group(4))},
])

# Core 8 vs GDP gap (2011-12 base). The 2024Q4 core 8 first print is blank, so this chart alone uses the latest vintage throughout
core8_yoy = lambda v: q[(q.indicator == "core8_overall_base2011") & (q.vintage == v)].set_index("quarter").yoy_pct
GAPQ = [str(p) for p in pd.period_range("2023Q1", "2025Q3", freq="Q")]
gap = pd.DataFrame({"gdp": gdp.gdp_growth_first_print.reindex(GAPQ), "core8": core8_yoy("latest").reindex(GAPQ)})
assert gap.notna().all().all()
gap["gap"] = gap.gdp - gap.core8
gap_early, gap_late = gap.gap.loc["2023Q1":"2024Q2"].mean(), gap.gap.loc["2024Q3":"2025Q3"].mean()
gap_first = gap.gdp - core8_yoy("first").reindex(GAPQ)  # as in the report
gapf_early, gapf_late = gap_first.loc["2023Q1":"2024Q2"].mean(), gap_first.loc["2024Q3":"2025Q3"].mean()

# ---------- workbook ----------
wb = xlsxwriter.Workbook(OUT, {"nan_inf_to_errors": False})
wb.set_properties({"title": "India GDP Nowcaster", "subject": "Real-time nowcast backtest for India's GDP first print"})
F = {}
def fmt(name, **kw):
    base = {"font_name": TEXT, "font_size": 11, "font_color": INK, "valign": "vcenter"}
    base.update(kw)
    F[name] = wb.add_format(base)
    return F[name]

fmt("bg", bg_color=BG)
fmt("card", bg_color=CARD)
fmt("title", font_name=DISPLAY_SEMI, font_size=28, bg_color=BG, valign="bottom")
fmt("subtitle", font_size=13, font_color=SEC, bg_color=BG, valign="top")
fmt("kpi", font_name=DISPLAY_SEMI, font_size=32, bg_color=CARD, indent=1, valign="bottom")
fmt("kpi_label", font_size=11, bg_color=CARD, indent=1, valign="top")
fmt("kpi_note", font_size=10, font_color=SEC, bg_color=CARD, indent=1, valign="top", text_wrap=True)
fmt("card_title", font_name=TEXT_SEMI, font_size=13, bg_color=CARD, indent=1, valign="bottom")
fmt("card_sub", font_size=10, font_color=SEC, bg_color=CARD, indent=1, valign="top")
fmt("footer", font_size=9, font_color=SEC, bg_color=BG, text_wrap=True, valign="top")
fmt("h1", font_name=DISPLAY_SEMI, font_size=20)
fmt("h2", font_name=TEXT_SEMI, font_size=13)
fmt("note", font_color=SEC, text_wrap=True, valign="top")
fmt("body", text_wrap=True, valign="top")
HEAD = dict(font_name=TEXT_SEMI, bold=False, bg_color=BG, bottom=1, bottom_color=HAIR, valign="vcenter")
fmt("head", **HEAD)
fmt("head_r", align="right", **HEAD)
CELL = dict(bottom=1, bottom_color=HAIR)
fmt("txt", **CELL)
fmt("num1", num_format="0.0", **CELL)
fmt("num2", num_format="0.00", **CELL)
fmt("int", num_format="0", **CELL)
fmt("pct1", num_format='0.0"%"', **CELL)
fmt("date", num_format="d mmm yyyy", align="left", **CELL)
fmt("bool", align="center", **CELL)
fmt("input", num_format='0.0"%"', bg_color="#FFFFFF", border=1, border_color=BLUE)
fmt("green_cf", bg_color=GREEN_TINT, font_color="#1E7A35")

def setup(ws, landscape=False):
    ws.hide_gridlines(2)
    ws.set_paper(9)
    if landscape:
        ws.set_landscape()
    ws.set_margins(0.4, 0.4, 0.5, 0.5)

def table(ws, r0, c0, df, spec, name, autofilter=True):
    """spec: list of (column, header, format key). Writes an Excel Table with the brief's header and hairline style."""
    rows = [[(None if (isinstance(v, float) and np.isnan(v)) else v) for v in rec] for rec in df[[s[0] for s in spec]].itertuples(index=False)]
    cols = [{"header": h, "format": F[f], "header_format": F["head_r" if f not in ("txt", "date", "bool") else "head"]} for _, h, f in spec]
    ws.add_table(r0, c0, r0 + max(len(rows), 1), c0 + len(spec) - 1,
                 {"data": rows, "columns": cols, "name": name, "style": None, "banded_rows": False, "autofilter": autofilter})
    return r0 + len(rows)

# Sheets in display order; chart_data last and hidden
ws, bt, me, lv, dm = (wb.add_worksheet(n) for n in ("Dashboard", "Backtest", "Metrics", "Live call", "Data & method"))
cd = wb.add_worksheet("chart_data")

# ---------- chart data (hidden sheet) ----------
def put(r, c, values, f=None):
    for i, v in enumerate(values):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            cd.write_blank(r + i, c, None)
        else:
            cd.write(r + i, c, v, f)
    return ["chart_data", r, c, r + len(values) - 1, c]

# Chart 1: RMSE by days before GDP
c1_lab = [f"{d} ({GDP_DAY - int(d[2:])} days)" for d in DATES]
# Same quarters at every date: headline non-COVID quarters (excluding 2022Q3) where the best model has a nowcast at all three dates
lo, hi = mx[(mx.variant == BEST_VAR) & (mx.model_name == "Naive") & (mx.date == "D+0")].quarters.iloc[0].split("-")
HEAD_Q = [x for x in WINDOW if lo <= x <= hi and x not in COVID and x != "2022Q3"]
bm = nc[(nc.model_name == BEST) & (nc.variant == BEST_VAR) & nc.quarter.isin(HEAD_Q)]
C1Q = sorted(set.intersection(*[set(bm[bm.date == d].quarter) for d in DATES]))
def rmse_on(name, d):
    x = nc[(nc.model_name == name) & (nc.variant == BEST_VAR) & (nc.date == d) & nc.quarter.isin(C1Q)]
    assert len(x) == len(C1Q)
    return round(float(np.sqrt(((x.nowcast - x.actual) ** 2).mean())), 4)
c1_model = [rmse_on(BEST, d) for d in DATES]
c1_naive = [rmse_on("Naive", d) for d in DATES]
cd.write_row(0, 0, ["chart 1", "model RMSE", "naive RMSE, same quarters"])
C1 = dict(cat=put(1, 0, c1_lab), model=put(1, 1, c1_model), naive=put(1, 2, c1_naive))

# Chart 2: nowcast vs first print over time (best model, D+32)
b = nc[(nc.model_name == BEST) & (nc.variant == BEST_VAR) & (nc.date == "D+32")].set_index("quarter").nowcast
nv = nc[(nc.model_name == "Naive") & (nc.variant == BEST_VAR) & (nc.date == "D+32")].set_index("quarter").nowcast
c2 = pd.DataFrame({"actual": gdp.gdp_growth_first_print.reindex(WINDOW), "model": b.reindex(WINDOW), "naive": nv.reindex(WINDOW)})
c2["covid"] = [25.0 if x in COVID else None for x in WINDOW]
c2["covid_low"] = [-30.0 if x in COVID else None for x in WINDOW]
cd.write_row(0, 4, ["chart 2 quarter", "first print", "model D+32", "naive", "covid band top", "covid band bottom"])
C2 = dict(cat=put(1, 4, WINDOW), actual=put(1, 5, list(c2.actual)), model=put(1, 6, [round(v, 4) if pd.notna(v) else None for v in c2.model]),
          naive=put(1, 7, list(c2.naive)), covid=put(1, 8, list(c2.covid)), covid_low=put(1, 9, list(c2.covid_low)))
c2_last_model = max(i for i, v in enumerate(c2.model) if pd.notna(v))

# Chart 3: relative RMSE at D+32 by model and variant, excluding 2022Q3
c3 = mx[(mx.date == "D+32") & (mx.model_name != "Naive")].copy()
c3["order"] = c3.model_name.map(MAIN_ORDER.index)
c3 = c3.sort_values("rel_rmse")
cd.write_row(0, 11, ["chart 3 model, variant", "rel RMSE"])
C3 = dict(cat=put(1, 11, [f"{m}, {VARIANTS[v]}" for m, v in zip(c3.model_name, c3.variant)]), rel=put(1, 12, [round(v, 4) for v in c3.rel_rmse]))

# Chart 4: GDP vs core 8 YoY and gap
cd.write_row(0, 15, ["chart 4 quarter", "GDP first print", "core 8 YoY", "gap"])
C4 = dict(cat=put(1, 15, GAPQ), gdp=put(1, 16, list(gap.gdp)), core8=put(1, 17, [round(v, 4) if pd.notna(v) else None for v in gap.core8]),
          gap=put(1, 18, [round(v, 4) if pd.notna(v) else None for v in gap.gap]))

# Live chart helpers
cd.write_row(0, 20, ["live forecast", "nowcast", "plus", "minus"])
L = dict(cat=put(1, 20, list(LIVE.forecast)), val=put(1, 21, list(LIVE.nowcast)),
         plus=put(1, 22, [round(h - n, 4) for h, n in zip(LIVE.high, LIVE.nowcast)]), minus=put(1, 23, [round(n - l, 4) for n, l in zip(LIVE.nowcast, LIVE.low)]))
cd.hide()

# ---------- chart helpers ----------
AXIS_FONT = {"name": TEXT, "size": 10, "color": SEC}
AXIS_GLASS = {**AXIS_FONT, "color": SEC_GLASS}
def style(chart, y_fmt="0.0", y_min=None, y_max=None, y_title=None, rotate=False, title=None, sec=SEC):
    axis_font = {**AXIS_FONT, "color": sec}
    if title:  # charts outside a card carry their own title
        chart.set_title({"name": title, "overlay": False, "layout": {"x": 0.02, "y": 0.03}, "name_font": {"name": TEXT_SEMI, "size": 13, "color": INK, "bold": False}})
    else:  # dashboard titles live in the card header cells
        chart.set_title({"none": True})
    chart.set_legend({"none": True})
    chart.set_chartarea({"border": {"none": True}, "fill": {"none": True}})
    chart.set_plotarea({"border": {"none": True}, "fill": {"none": True}, "layout": {"x": 0.13, "y": 0.06, "width": 0.67, "height": 0.72 if rotate else 0.8}})
    chart.set_x_axis({"line": {"none": True}, "major_tick_mark": "none", "minor_tick_mark": "none", "label_position": "low",
                      "num_font": {**axis_font, "rotation": -90} if rotate else axis_font, "major_gridlines": {"visible": False}})
    y = {"line": {"none": True}, "major_tick_mark": "none", "num_font": axis_font, "num_format": y_fmt,
         "major_gridlines": {"visible": True, "line": {"color": HAIR, "width": 0.5}}}
    if y_min is not None:
        y["min"] = y_min
    if y_max is not None:
        y["max"] = y_max
    if y_title:
        y["name"], y["name_font"] = y_title, {"name": TEXT, "size": 10, "color": sec, "bold": False}
    chart.set_y_axis(y)

def end_label(n, text, color, at=None, pos="right"):
    at = n - 1 if at is None else at
    return {"custom": [{"delete": True} if i != at else {"value": text, "font": {"name": TEXT_SEMI, "size": 10, "color": color}} for i in range(n)],
            "position": pos}

def line(chart, values, cats, color, label=None, at=None, width=2.0, dash=None, pos="right"):
    s = {"values": values, "categories": cats, "marker": {"type": "none"}, "line": {"color": color, "width": width}}
    if dash:
        s["line"]["dash_type"] = dash
    if label:
        s["data_labels"] = end_label(values[3] - values[1] + 1, label, color, at, pos)
    chart.add_series(s)

# ---------- Dashboard (glass style) ----------
def make_background(path):
    """Soft pastel mesh: large colour blobs on #EEF2F8, blurred smooth. Deterministic."""
    img = Image.new("RGB", (2400, 1400), "#EEF2F8")
    d = ImageDraw.Draw(img)
    for (cx, cy, r), colour in zip([(170, 140, 430), (920, 90, 400), (1080, 760, 440), (330, 860, 400)], ["#7AB8FF", "#C9A7FF", "#FFC7D9", "#A8F0E0"]):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colour)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.filter(ImageFilter.GaussianBlur(120)).save(path, optimize=True)

make_background(BG_IMAGE)
setup(ws, landscape=True)
ws.set_background(str(BG_IMAGE))  # shows on screen only; print and PDF fall back to white
GUT, COLW = 1.6, 11.5
LAYOUT = ["g"] + (["c"] * 3 + ["g"]) * 4  # A..Q: gutter, 4 x (3 card columns + gutter)
for i, kind in enumerate(LAYOUT):
    ws.set_column(i, i, GUT if kind == "g" else COLW)  # no cell fill, so the background shows through
ws.set_column(len(LAYOUT), 16383, None, None, {"hidden": True})  # nothing right of the dashboard area
ws.set_default_row(15, hide_unused_rows=True)
px_col = lambda w: int(w * 7 + 0.5) + 5
CARD_COLS = [(1, 3), (5, 7), (9, 11), (13, 15)]

heights = {0: 12, 1: 40, 2: 22, 3: 10, 4: 8, 5: 46, 6: 18, 7: 30, 8: 8, 9: 10}
CH_TOP1, CH_ROWS = 10, 17
CH_TOP2 = CH_TOP1 + CH_ROWS + 1
FOOT = CH_TOP2 + CH_ROWS + 1
heights[FOOT] = 28  # two-line footnote; the full notes are on Data & method
for top in (CH_TOP1, CH_TOP2):
    heights[top], heights[top + 1] = 26, 18
heights[CH_TOP1 + 1] = 32  # chart 1's subtitle runs to two lines
for r in range(0, FOOT + 3):
    ws.set_row(r, heights.get(r, 15))
row_px = lambda r0, r1: round(sum(heights.get(r, 15) for r in range(r0, r1 + 1)) * 4 / 3)
col_px = lambda c0, c1: sum(px_col(GUT if LAYOUT[c] == "g" else COLW) for c in range(c0, c1 + 1))

g_title = wb.add_format({"font_name": DISPLAY_SEMI, "font_size": 28, "font_color": INK, "valign": "bottom"})
g_sub = wb.add_format({"font_name": TEXT, "font_size": 13, "font_color": SEC_GLASS, "valign": "top"})
g_foot = wb.add_format({"font_name": TEXT, "font_size": 9, "font_color": SEC_GLASS, "valign": "top", "text_wrap": True})
ws.merge_range(1, 1, 1, 15, "Can monthly indicators beat a naive rule for India's GDP?", g_title)
ws.merge_range(2, 1, 2, 15, "Not in normal quarters: the best model comes within 3% of naive. Indicators help only in shocks like COVID.", g_sub)

GLASS_FILL = {"color": "#FFFFFF", "transparency": 40}
GLASS_LINE = {"color": "#FFFFFF", "transparency": 40, "width": 1}
def glass_card(r0, r1, c0, c1):
    """Frosted card: a translucent white shape (rounded after saving), drawn behind the charts."""
    ws.insert_textbox(r0, c0, "", {"width": col_px(c0, c1), "height": row_px(r0, r1), "fill": GLASS_FILL, "line": GLASS_LINE,
                                   "object_position": 3, "description": "glass card"})

def text_box(r, c0, c1, text, font, valign, rows=1):
    ws.insert_textbox(r, c0, text, {"width": col_px(c0, c1), "height": row_px(r, r + rows - 1), "fill": {"none": True}, "line": {"none": True},
                                    "font": font, "align": {"vertical": valign, "horizontal": "left"}, "object_position": 3})

kpis = [
    (f"{best_rel:.2f}", f"Best relative RMSE vs naive ({best_n} quarters)", f"{BEST}, D+32"),
    (f"{best_n}", "Non-COVID test quarters", f"{best_quarters.replace('-', ' to ')}, without 2022Q3, for the best model"),
    (f"{naive_pt:.1f}%", "Live call for 2026Q3, naive", f"± {naive_rmse:.2f} points. First print due 30 Nov 2026"),
    (f"{GDP_DAY}", "Median days to the GDP first print", f"After quarter-end, 2017Q2 to 2025Q3 (range {days.min()} to {days.max()})"),
]
CHART_CARDS = [(CH_TOP1, 1), (CH_TOP1, 9), (CH_TOP2, 1), (CH_TOP2, 9)]
for c0, c1 in CARD_COLS:
    glass_card(4, 8, c0, c1)
for top, c0 in CHART_CARDS:
    glass_card(top, top + CH_ROWS - 1, c0, c0 + 6)
for (c0, c1), (big, label, note) in zip(CARD_COLS, kpis):
    text_box(5, c0, c1, big, {"name": DISPLAY_SEMI, "size": 32, "color": INK}, "bottom")
    text_box(6, c0, c1, label, {"name": TEXT, "size": 11, "color": INK}, "top")
    text_box(7, c0, c1, note, {"name": TEXT, "size": 10, "color": SEC_GLASS}, "top")

chart_w = px_col(COLW) * 6 + px_col(GUT) - 16  # 6 card columns + 1 gutter, less 8px padding each side
chart_h = int((CH_ROWS - 2) * 20) - 8  # below the two header rows
def place(chart, top, c0, title, subtitle):
    text_box(top, c0, c0 + 6, title, {"name": TEXT_SEMI, "size": 13, "color": INK}, "bottom")
    text_box(top + 1, c0, c0 + 6, subtitle, {"name": TEXT, "size": 10, "color": SEC_GLASS}, "top")
    chart.set_size({"width": chart_w, "height": chart_h})
    ws.insert_chart(top + 2, c0, chart, {"x_offset": 8, "y_offset": 0, "object_position": 1})

# Chart 1
ch1 = wb.add_chart({"type": "line"})
line(ch1, C1["model"], C1["cat"], BLUE, BEST)
line(ch1, C1["naive"], C1["cat"], GRAY, "Naive")
style(ch1, "0.0", 0.8, 1.4, "RMSE, points", sec=SEC_GLASS)
assert all(m > n for m, n in zip(c1_model, c1_naive))  # the title below depends on this
assert 0.8 <= min(c1_model + c1_naive) and max(c1_model + c1_naive) <= 1.4  # the y-axis range
place(ch1, CH_TOP1, 1, f"{BEST} stays above naive at every nowcast date",
      f"RMSE on the same {len(C1Q)} non-COVID quarters at every date ({C1Q[0]} to {C1Q[-1]}), n = {len(C1Q)}\n"
      f"On the {len(C1Q)} quarters shared by all dates; on all {best_n} at D+32 it's {best_rel:.2f}")

# Chart 2: COVID quarters as a light grey band (full-height columns behind the lines), then first print, naive and the best model
ch2 = wb.add_chart({"type": "column"})
for key in ("covid", "covid_low"):
    ch2.add_series({"values": C2[key], "categories": C2["cat"], "gap": 0, "overlap": 100, "fill": {"color": GRAY, "transparency": 80}, "border": {"none": True}})
ln2 = wb.add_chart({"type": "line"})
iq = WINDOW.index
line(ln2, C2["actual"], C2["cat"], INK, "First print", iq("2021Q2"), pos="left")
line(ln2, C2["naive"], C2["cat"], GRAY, "Naive", iq("2021Q3"), pos="right")
line(ln2, C2["model"], C2["cat"], BLUE, BEST, c2_last_model, pos="below")
ch2.combine(ln2)
style(ch2, "0", -30, 25, "GDP growth, %", rotate=True, sec=SEC_GLASS)
ch2.set_x_axis({"line": {"none": True}, "major_tick_mark": "none", "label_position": "low", "num_font": {**AXIS_GLASS, "rotation": -90}, "interval_unit": 4})
ln2.show_blanks_as("gap")
place(ch2, CH_TOP1, 9, "Outside COVID, nowcasts hug last quarter's print", f"{BEST} at D+32, {VARIANTS[BEST_VAR]}. COVID quarters shaded")

# Chart 3: horizontal bars crossing at 1.0, so the axis is the naive reference: left beats naive, right loses
ch3 = wb.add_chart({"type": "bar"})
ch3.add_series({"values": C3["rel"], "categories": C3["cat"], "gap": 45, "border": {"none": True},
                "points": [{"fill": {"color": GREEN if v < 1 else GRAY}} for v in c3.rel_rmse],
                "data_labels": {"value": True, "num_format": "0.00", "position": "outside_end", "font": {"name": TEXT, "size": 9, "color": SEC_GLASS}}})
style(ch3, sec=SEC_GLASS)
ch3.set_x_axis({"min": 0.8, "max": 2.0, "crossing": 1, "label_position": "high", "major_unit": 0.2, "num_format": "0.0", "line": {"none": True}, "major_tick_mark": "none",
                "num_font": AXIS_GLASS, "major_gridlines": {"visible": False}, "name": "RMSE relative to naive (1.0 = naive)",
                "name_font": {"name": TEXT, "size": 10, "color": SEC_GLASS, "bold": False}})
ch3.set_y_axis({"reverse": True, "label_position": "low", "line": {"color": INK, "width": 1}, "major_tick_mark": "none",
                "num_font": {**AXIS_GLASS, "size": 9}, "major_gridlines": {"visible": False}})
ch3.set_plotarea({"border": {"none": True}, "fill": {"none": True}, "layout": {"x": 0.42, "y": 0.1, "width": 0.5, "height": 0.72}})
place(ch3, CH_TOP2, 1, f"Only {BEST} edges below naive, by {100 * (1 - best_rel):.0f}%, at D+32", "Non-COVID quarters, excluding 2022Q3. Bars start at naive (1.0)")

# Chart 4
ch4 = wb.add_chart({"type": "column"})
ch4.add_series({"values": C4["gap"], "categories": C4["cat"], "gap": 70, "border": {"none": True}, "fill": {"color": BLUE},
                "data_labels": end_label(len(GAPQ), "Gap", BLUE, GAPQ.index("2025Q2"), "outside_end")})
ln4 = wb.add_chart({"type": "line"})
line(ln4, C4["gdp"], C4["cat"], INK, "GDP")
line(ln4, C4["core8"], C4["cat"], GRAY, "Core 8", GAPQ.index("2023Q3"), pos="above")
ch4.combine(ln4)
style(ch4, "0", -4, 12, "YoY growth, %", rotate=True, sec=SEC_GLASS)
place(ch4, CH_TOP2, 9, "The GDP–core 8 gap widened from mid-2024", "Bars: GDP minus core 8 YoY. Core 8 is the latest vintage here (see note)")

ws.merge_range(FOOT, 1, FOOT, 15, "Non-COVID quarters exclude 2022Q3, when naive carried forward a 13.5% base-effect print. COVID is 2020Q2 to 2022Q2.\n"
               "The gap chart uses latest-vintage core 8 because the 2024Q4 first print is blank. Full notes are on the Data & method sheet.", g_foot)
DASH_NOTES = [
    "Non-COVID test quarters exclude 2022Q3, where naive carried forward a 13.5% base-effect print. COVID quarters are 2020Q2 to 2022Q2.",
    f"Gap chart: the 2024Q4 core 8 first print is blank, so this chart alone uses latest-vintage core 8 throughout: the gap averages {gap_early:.1f} points in 2023Q1 to 2024Q2 and {gap_late:.1f} in 2024Q3 to 2025Q3.",
    f"On first prints, as in the report, it is {gapf_early:.1f} and {gapf_late:.1f} (2024Q4 missing). The widening gap is a hypothesis, not tested.",
    "The dashboard is built by dashboard/build_dashboard.py from data/processed.",
]
ws.print_area(0, 0, FOOT + 1, 16)
ws.fit_to_pages(1, 1)
ws.center_horizontally()
ws.set_zoom(90)
ws.activate()

# ---------- Backtest ----------
setup(bt)
naive_err = nc[nc.model_name == "Naive"].assign(nerr=lambda d: (d.nowcast - d.actual).abs()).set_index(["variant", "date", "quarter"]).nerr
t = nc.copy()
t["variant_name"] = t.variant.map(VARIANTS)
t["base"] = np.where(t.quarter.isin(WINDOW), "2011-12", "2022-23")
t["error"] = t.nowcast - t.actual
t["abs_error"] = t.error.abs()
t["is_covid"] = t.quarter.isin(COVID)
ne = naive_err.reindex(pd.MultiIndex.from_frame(t[["variant", "date", "quarter"]])).values
t["beats_naive"] = np.where(t.model_name == "Naive", None, t.abs_error.values < ne)
t["asof_d"] = list(t["asof"].dt.to_pydatetime())
t = t.sort_values(["quarter", "date", "variant", "model"]).reset_index(drop=True)
bt.write(0, 0, "Every real-time nowcast", F["h1"])
bt.write(1, 0, "Error is nowcast minus first print. Beats naive compares absolute errors on the same quarter, date and variant. 2022-23 base rows are an illustration only.", F["note"])
spec = [("quarter", "quarter", "txt"), ("date", "nowcast_date", "txt"), ("asof_d", "as_of", "date"), ("model_name", "model", "txt"), ("variant_name", "variant", "txt"),
        ("base", "gdp_base", "txt"), ("nowcast", "nowcast", "pct1"), ("actual", "actual", "pct1"), ("error", "error", "num2"), ("abs_error", "abs_error", "num2"),
        ("is_covid", "is_covid", "bool"), ("beats_naive", "beats_naive", "bool")]
last = table(bt, 3, 0, t, spec, "Backtest")
for i, w in enumerate([10, 13, 13, 40, 16, 11, 11, 10, 10, 11, 10, 13]):
    bt.set_column(i, i, w)
bt.set_row(0, 30)
bt.conditional_format(4, 8, last, 8, {"type": "data_bar", "bar_color": "#A8E6B7", "bar_negative_color": "#FFB3AD", "bar_solid": True,
                                     "bar_no_border": True, "bar_negative_border_color_same": True, "bar_axis_position": "middle", "bar_axis_color": GRAY})
bt.conditional_format(4, 11, last, 11, {"type": "cell", "criteria": "==", "value": "TRUE", "format": F["green_cf"]})
bt.freeze_panes(4, 0)

# ---------- Metrics ----------
setup(me)
parts = [(mx, "Non-COVID, excluding 2022Q3 (headline)"), (mm, "Non-COVID, including 2022Q3"), (cv, "COVID quarters")]
mt = pd.concat([d.assign(sample=s) for d, s in parts], ignore_index=True)
mt["variant_name"] = mt.variant.map(VARIANTS)
mt["order"] = mt.model_name.map(MAIN_ORDER.index)
mt["date"] = pd.Categorical(mt.date, DATES)
mt = mt.sort_values(["sample", "variant", "date", "order"], key=lambda s: s.map({p[1]: i for i, p in enumerate(parts)}) if s.name == "sample" else s).reset_index(drop=True)
me.write(0, 0, "Backtest metrics by model, variant and nowcast date", F["h1"])
me.write(1, 0, "Relative RMSE compares each model with naive on the same quarters. Below 1 means the model beat naive. The lowest non-COVID Diebold-Mariano p (0.10, Change model with the COVID dummy at D+0) favours naive. The test isn't reliable at these sample sizes.", F["note"])
spec = [("sample", "sample", "txt"), ("variant_name", "variant", "txt"), ("date", "nowcast_date", "txt"), ("model_name", "model", "txt"), ("quarters", "quarters", "txt"),
        ("n", "n", "int"), ("rmse", "rmse", "num2"), ("mae", "mae", "num2"), ("bias", "bias", "num2"), ("rel_rmse", "rel_rmse_vs_naive", "num2"), ("dm_p", "dm_p", "num2")]
mt["date"] = mt.date.astype(str)
last = table(me, 3, 0, mt, spec, "Metrics")
for i, w in enumerate([38, 16, 13, 24, 15, 6, 9, 9, 9, 18, 9]):
    me.set_column(i, i, w)
me.set_row(0, 30)
me.set_row(1, 32)
me.conditional_format(4, 9, last, 9, {"type": "3_color_scale", "min_type": "num", "min_value": 0.4, "min_color": "#BDECC9",
                                     "mid_type": "num", "mid_value": 1, "mid_color": "#FFFFFF", "max_type": "num", "max_value": 2, "max_color": "#FFC4BF"})
me.freeze_panes(4, 0)

# ---------- Live call ----------
setup(lv, landscape=True)
lv.write(0, 0, "Live call: India real GDP growth, 2026Q3", F["h1"])
lv.write(1, 0, "Pre-registered before the first print. Naive is the primary forecast. Change model ≈ naive, so the informative comparison on 30 Nov is naive against Bridge · Core 8.", F["note"])
lv.write(3, 0, "2026Q3 first print, type it here on 30 Nov:", F["h2"])
lv.write_blank(3, 3, None, F["input"])
INPUT = "$D$4"
spec = [("forecast", "forecast", "txt"), ("is_primary", "is_primary", "bool"), ("made_on", "made_on", "date"), ("nowcast", "nowcast", "pct1"), ("low", "range_low", "pct1"), ("high", "range_high", "pct1")]
LIVE["made_on"] = list(LIVE["made_on"].dt.to_pydatetime())
rows = [list(r) for r in LIVE[[s[0] for s in spec]].itertuples(index=False)]
cols = [{"header": h, "format": F[f], "header_format": F["head" if f in ("txt", "date", "bool") else "head_r"]} for _, h, f in spec]
cols += [{"header": "actual", "formula": f'=IF({INPUT}="","",{INPUT})', "format": F["pct1"], "header_format": F["head_r"]},
         {"header": "error", "formula": '=IF([@actual]="","",[@nowcast]-[@actual])', "format": F["num2"], "header_format": F["head_r"]},
         {"header": "abs_error", "formula": '=IF([@actual]="","",ABS([@error]))', "format": F["num2"], "header_format": F["head_r"]},
         {"header": "within_range", "formula": '=IF([@actual]="","",AND([@actual]>=[@[range_low]],[@actual]<=[@[range_high]]))', "format": F["bool"], "header_format": F["head"]}]
lv.add_table(5, 0, 5 + len(rows), len(cols) - 1, {"data": rows, "columns": cols, "name": "LiveCall", "style": None, "banded_rows": False, "autofilter": False})
for i, w in enumerate([30, 11, 13, 10, 11, 11, 10, 9, 10, 13]):
    lv.set_column(i, i, w)
lv.set_row(0, 30)
lv.write(10, 0, "Ranges are ±1 backtest RMSE at D+32 (non-COVID, excluding 2022Q3). Every model was fitted on the 2011-12 base and applied to 2022-23 base data, so the ranges understate the uncertainty. Source: reports/live_nowcast_2026Q3.md.", F["note"])
cd.write(0, 25, "actual line")
for i in range(3):
    cd.write_formula(1 + i, 25, f"=IF('Live call'!{INPUT}=\"\",NA(),'Live call'!{INPUT})")
lc = wb.add_chart({"type": "column"})
lc.add_series({"values": L["val"], "categories": L["cat"], "gap": 120, "border": {"none": True},
               "points": [{"fill": {"color": GRAY if p else BLUE}} for p in LIVE.is_primary],
               "y_error_bars": {"type": "custom", "plus_values": "=" + "chart_data!$W$2:$W$4", "minus_values": "=chart_data!$X$2:$X$4",
                                "end_style": 1, "line": {"color": SEC, "width": 1.25}},
               "data_labels": {"value": True, "num_format": '0.0"%"', "position": "inside_base", "font": {"name": TEXT_SEMI, "size": 11, "color": "#FFFFFF"}}})
al = wb.add_chart({"type": "line"})
al.add_series({"values": ["chart_data", 1, 25, 3, 25], "categories": L["cat"], "marker": {"type": "none"}, "line": {"color": INK, "width": 2}})
lc.combine(al)
style(lc, "0", 0, 10, "GDP growth, %", title="Three calls for 2026Q3, with naive as the primary forecast")
lc.set_plotarea({"border": {"none": True}, "fill": {"none": True}, "layout": {"x": 0.1, "y": 0.18, "width": 0.85, "height": 0.68}})
lc.set_size({"width": 640, "height": 340})
lv.insert_chart(12, 0, lc, {"x_offset": 4, "y_offset": 8})

# ---------- Data & method ----------
setup(dm)
dm.write(0, 0, "Data and method", F["h1"])
dm.set_row(0, 30)
r = 2
dm.write(r, 0, "Method", F["h2"]); r += 1
for line_txt in [
    "Target: India's quarterly real GDP growth, first print, 2017Q2 to 2025Q3 (34 quarters, 2011-12 base).",
    "Nowcast dates: D+0, D+32 and D+45 days after quarter-end, about 61, 29 and 16 days before the median GDP release.",
    "As-of rule: a monthly value is used only if released on or before the nowcast date; a GDP print only if released before it.",
    "Expanding-window backtest, refitted every quarter, starting once 8 training quarters exist. COVID (2020Q2 to 2022Q2) is either dropped from training or kept with a dummy.",
    "Change model was pre-registered as the only extra model before its results were seen.",
]:
    dm.merge_range(r, 0, r, 7, line_txt, F["body"]); dm.set_row(r, 30); r += 1
r += 1
dm.write(r, 0, "Dashboard notes", F["h2"]); r += 1
for line_txt in DASH_NOTES:
    dm.merge_range(r, 0, r, 7, line_txt, F["body"]); dm.set_row(r, 30); r += 1
r += 1
dm.write(r, 0, "Indicator coverage", F["h2"]); r += 1
cov = coverage.copy()
spec = [("indicator", "indicator", "txt"), ("first_month", "first_month", "txt"), ("last_month", "last_month", "txt"), ("missing_months", "missing_months", "int"),
        ("first_print_months", "first_print_months", "int"), ("first_print_available", "first_print_available", "txt"), ("median_lag_days", "median_lag_days", "int")]
end = table(dm, r, 0, cov, spec, "Coverage")
r = end + 2
dm.write(r, 0, "Limitations", F["h2"]); r += 1
for line_txt in [
    "Small samples: headline comparisons rest on 6 to 12 test quarters, add-on tests on 5 to 13 outside COVID, COVID results on 1 to 8, the 2022-23 base check on 3.",
    "Proxy release dates: core 8 and AAI dates are PDF creation dates. GST first prints from Apr 2024 are undated and unused. CEA, e-way bills, diesel and petrol have no release dates; the [look-ahead] tests assume core 8's timing.",
    "Three GDP quarters (2016Q4, 2019Q3, 2021Q3) have an unverified release day; removing them moves relative RMSEs by up to 0.53, and no model in the COVID-dropped variant gets below naive.",
    "Base-year break: GDP and core 8 moved to the 2022-23 base, which adds iron ore to core 8. The live call applies old-base coefficients to new-base data.",
    "No second-source check for the exports, air and GST parsing.",
    "The Diebold-Mariano test isn't reliable at this sample size. Its p-values are indicative only.",
    "The bootstrap in the exploration's like-for-like check ignores autocorrelation, so its intervals are too narrow.",
]:
    dm.merge_range(r, 0, r, 7, line_txt, F["body"]); dm.set_row(r, 32); r += 1
r += 1
dm.write(r, 0, "Sources", F["h2"]); r += 1
urls = pd.concat([gdp.source_url.dropna(), mo.loc[mo.value.notna(), "source_url"].dropna()])
host = urls.map(lambda u: urlparse(u).netloc.replace("www.", "") if u.startswith("http") else "other")
src = host.value_counts().rename_axis("host").reset_index(name="values")
src["note"] = src.host.map({"web.archive.org": "Wayback Machine captures (RBI Bulletin tables, PPAC snapshots)"}).fillna("")
end = table(dm, r, 0, src, [("host", "source host", "txt"), ("values", "values sourced", "int"), ("note", "note", "txt")], "Sources", autofilter=False)
r = end + 2
dm.merge_range(r, 0, r, 7, "Every value in data/processed links to the file it came from (source_url). Notebooks 01 to 04 rebuild everything; see README.md.", F["note"])
for i, w in enumerate([34, 13, 13, 15, 18, 20, 16, 40]):
    dm.set_column(i, i, w)

wb.close()

def finish_glass(path, radius_px=12):
    """xlsxwriter writes charts before shapes and has no rounded rectangle. Move shapes behind the charts and round the glass cards."""
    import zipfile
    with zipfile.ZipFile(path) as z:
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    out = []
    for info, data in items:
        if info.filename.startswith("xl/drawings/drawing") and b"<xdr:sp" in data:
            xml = data.decode("utf8")
            anchors = re.findall(r"<xdr:twoCellAnchor.*?</xdr:twoCellAnchor>", xml, flags=re.S)
            head, tail = xml.split(anchors[0], 1)[0], xml.rsplit(anchors[-1], 1)[1]
            def round_card(a):
                if 'descr="glass card"' not in a:
                    return a
                # xlsxwriter drops transparency on shapes, so write the alpha into the fill and the line
                fill_alpha, line_alpha = 100000 - GLASS_FILL["transparency"] * 1000, 100000 - GLASS_LINE["transparency"] * 1000
                a = a.replace('<a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:ln',
                              f'<a:solidFill><a:srgbClr val="FFFFFF"><a:alpha val="{fill_alpha}"/></a:srgbClr></a:solidFill><a:ln', 1)
                a = re.sub(r'(<a:ln w="\d+" cmpd="sng"><a:solidFill>)<a:srgbClr val="FFFFFF"/>', rf'\1<a:srgbClr val="FFFFFF"><a:alpha val="{line_alpha}"/></a:srgbClr>', a)
                assert a.count("<a:alpha ") == 2, "glass card XML changed shape"
                cx, cy = map(int, re.search(r'<a:ext cx="(\d+)" cy="(\d+)"', a).groups())
                adj = int(radius_px * 9525 / min(cx, cy) * 100000)
                return re.sub(r'<a:prstGeom prst="rect">\s*<a:avLst\s*/>\s*</a:prstGeom>',
                              f'<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val {adj}"/></a:avLst></a:prstGeom>', a)
            shapes = [round_card(a) for a in anchors if "<xdr:sp>" in a or "<xdr:sp " in a]
            others = [a for a in anchors if not ("<xdr:sp>" in a or "<xdr:sp " in a)]
            data = (head + "".join(shapes + others) + tail).encode("utf8")
        out.append((info, data))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for info, data in out:
            z.writestr(info, data)

finish_glass(OUT)
print("Wrote", OUT)
print("Best:", BEST, VARIANTS[BEST_VAR], round(best_rel, 4), "n", best_n, "| GDP day", GDP_DAY, "| gap", round(gap_early, 2), round(gap_late, 2))
