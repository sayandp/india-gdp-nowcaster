"""Build the README insight images (reports/readme/*.png) and numbers.csv from data/processed. Changes no results.

Usage: python tools/readme_images.py
Every number drawn on an image is logged to reports/readme/numbers.csv; tools/check_readme.py recomputes each one.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
OUT = ROOT / "reports" / "readme"
OUT.mkdir(parents=True, exist_ok=True)

INK, SEC, HAIR = "#1D1D1F", "#6E6E73", "#E5E5EA"
BLUE, GRAY, GREEN, COVID_BAND = "#007AFF", "#8E8E93", "#34C759", "#EBEBEF"
# Matplotlib can't pick weights inside the variable font, so semibold text uses Segoe UI
plt.rcParams.update({"font.family": ["Segoe UI Variable", "Segoe UI"], "font.size": 9, "text.color": INK,
                     "axes.edgecolor": HAIR, "axes.labelcolor": SEC, "xtick.color": SEC, "ytick.color": SEC,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y",
                     "grid.color": HAIR, "grid.linewidth": 0.6, "axes.axisbelow": True, "xtick.major.size": 0, "ytick.major.size": 0,
                     "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white"})
SEMI = {"family": "Segoe UI", "weight": 600}
W, H, DPI = 8, 4.5, 200  # 1600 x 900 px at 2x (200 dpi)

WINDOW = [str(p) for p in pd.period_range("2017Q2", "2025Q3", freq="Q")]
COVID = {str(p) for p in pd.period_range("2020Q2", "2022Q2", freq="Q")}
NAMES = {"2 AR(1)": "AR(1)", "3 Bridge: core 8": "Bridge: core 8", "4 Bridge + AR: core 8": "Bridge + AR: core 8",
         "5 Bridge: IIP": "Bridge: IIP", "8 Change: Δ core 8": "Model 8: change in core 8"}
VARIANT = {"drop": "COVID dropped", "dummy": "COVID dummy"}

mx = pd.read_csv(P / "backtest_metrics_main_without_2022Q3.csv")
cv = pd.read_csv(P / "backtest_metrics_covid.csv")
nc = pd.read_csv(P / "backtest_nowcasts.csv")
gdp = pd.read_csv(P / "gdp.csv", parse_dates=["release_date"]).set_index("quarter")
monthly = pd.read_csv(P / "indicators_monthly.csv", parse_dates=["release_date"])
quarterly = pd.read_csv(P / "indicators_quarterly.csv")
avail = pd.read_csv(P / "eda_nowcast_availability.csv")

NUMBERS = []
def num(image, key, value, fmt, source, rule):
    """Log a number shown on an image and return it as displayed."""
    shown = format(value, fmt)
    NUMBERS.append({"image": image, "key": key, "shown": shown, "value": value, "source": source, "rule": rule})
    return shown

def frame(title, subtitle, foot=None, axes=(0.08, 0.13, 0.88, 0.67)):
    fig = plt.figure(figsize=(W, H), dpi=DPI)
    fig.text(0.04, 0.935, title, fontsize=15, color=INK, va="baseline", **SEMI)
    fig.text(0.04, 0.875, subtitle, fontsize=9.5, color=SEC, va="baseline")
    if foot:
        fig.text(0.04, 0.03, foot, fontsize=8, color=SEC, va="baseline", linespacing=1.4)
    return fig, fig.add_axes(axes)

minus = lambda s: s.replace("-", "−")  # typographic minus on the image; numbers.csv keeps the plain form

def save(fig, name):
    fig.savefig(OUT / name, dpi=DPI)
    plt.close(fig)

# a. Headline: relative RMSE by model at D+32, non-COVID, without 2022Q3
IMG = "01_headline.png"
a = mx[(mx.date == "D+32") & (mx.model != "1 Naive")].copy()
a["label"] = a.model.map(NAMES) + " (" + a.variant.map(VARIANT) + ")"
a = a.sort_values("rel_rmse", ascending=False).reset_index(drop=True)
lo, hi = int(a.n.min()), int(a.n.max())
span = mx[(mx.date == "D+32") & (mx.model == "1 Naive")].quarters
first_q, last_q = min(s.split("-")[0] for s in span), max(s.split("-")[1] for s in span)
sub = (f"RMSE relative to naive at D+32, non-COVID test quarters {num(IMG, 'first_quarter', first_q, '', 'backtest_metrics_main_without_2022Q3.csv', 'D+32 naive, earliest quarter')} "
       f"to {num(IMG, 'last_quarter', last_q, '', 'backtest_metrics_main_without_2022Q3.csv', 'D+32 naive, latest quarter')} without 2022Q3; "
       f"n = {num(IMG, 'n_min', lo, 'd', 'backtest_metrics_main_without_2022Q3.csv', 'D+32 non-naive, min n')} "
       f"to {num(IMG, 'n_max', hi, 'd', 'backtest_metrics_main_without_2022Q3.csv', 'D+32 non-naive, max n')} quarters per bar")
fig, ax = frame("Nothing beats repeating last quarter outside COVID", sub, axes=(0.33, 0.1, 0.62, 0.72))
y = np.arange(len(a))
ax.barh(y, a.rel_rmse, height=0.62, color=[GREEN if v < 1 else BLUE for v in a.rel_rmse])
for i, r in a.iterrows():
    shown = num(IMG, f"rel_rmse|{r.model}|{r.variant}", r.rel_rmse, ".2f", "backtest_metrics_main_without_2022Q3.csv", f"D+32 {r.variant} {r.model} rel_rmse")
    ax.text(max(r.rel_rmse, 1) + 0.02, i, shown, va="center", fontsize=9, color=INK)  # clear of the reference line
ax.plot([1, 1], [-0.5, len(a) - 0.5], color=INK, lw=1.2, zorder=3)
ax.text(1, len(a) - 0.4, "Naive = 1.0", ha="center", va="bottom", fontsize=9, color=INK, **SEMI)
ax.set_yticks(y, a.label, fontsize=9, color=INK)
ax.set_ylim(-0.6, len(a) + 0.1)
ax.set_xlim(0, 2.0)
ax.grid(False)
ax.spines["left"].set_visible(False); ax.spines["bottom"].set_visible(False)
ax.set_xticks([])
save(fig, IMG)

# b. COVID: RMSE in COVID test quarters, core 8 bridge vs naive, by nowcast date
IMG = "02_covid.png"
assert set(cv.variant) == {"dummy"}
bc = cv[cv.model.isin(["1 Naive", "3 Bridge: core 8"])]
assert bc.quarters.nunique() == 1 and bc.n.nunique() == 1  # same quarters for both models at every date
b = bc.pivot(index="date", columns="model", values="rmse").loc[["D+0", "D+32", "D+45"]]
cq = bc.quarters.iloc[0]
sub = (f"RMSE in COVID test quarters, {num(IMG, 'first_quarter', cq.split('-')[0], '', 'backtest_metrics_covid.csv', 'naive and core 8 bridge, quarters start')} to "
       f"{num(IMG, 'last_quarter', cq.split('-')[1], '', 'backtest_metrics_covid.csv', 'naive and core 8 bridge, quarters end')}, COVID dummy variant; "
       f"n = {num(IMG, 'n', int(bc.n.iloc[0]), 'd', 'backtest_metrics_covid.csv', 'naive and core 8 bridge, n')} quarters at each date")
fig, ax = frame("Indicators earn their keep only in shocks", sub, axes=(0.08, 0.12, 0.88, 0.66))
x = np.arange(3); w = 0.34
ax.bar(x - w / 2 - 0.01, b["1 Naive"], w, color=GRAY)
ax.bar(x + w / 2 + 0.01, b["3 Bridge: core 8"], w, color=BLUE)
for i, d in enumerate(b.index):
    nv = num(IMG, f"rmse_naive|{d}", b.loc[d, "1 Naive"], ".2f", "backtest_metrics_covid.csv", f"{d} 1 Naive rmse")
    bv = num(IMG, f"rmse_bridge|{d}", b.loc[d, "3 Bridge: core 8"], ".2f", "backtest_metrics_covid.csv", f"{d} 3 Bridge: core 8 rmse")
    cut = num(IMG, f"cut_pct|{d}", 100 * (1 - b.loc[d, "3 Bridge: core 8"] / b.loc[d, "1 Naive"]), ".0f", "backtest_metrics_covid.csv", f"{d} 100*(1 - bridge rmse / naive rmse)")
    ax.text(i - w / 2 - 0.01, b.loc[d, "1 Naive"] + 0.2, nv, ha="center", va="bottom", fontsize=9, color=INK)
    ax.text(i + w / 2 + 0.01, b.loc[d, "3 Bridge: core 8"] + 0.2, f"{bv}\n−{cut}%", ha="center", va="bottom", fontsize=9, color=INK, linespacing=1.3)
ax.text(-w / 2 - 0.01, b.iloc[0, 0] / 2, "Naive", ha="center", va="center", fontsize=9, color="white", **SEMI)
ax.text(w / 2 + 0.01, b.iloc[0, 1] / 2, "Bridge:\ncore 8", ha="center", va="center", fontsize=9, color="white", linespacing=1.2, **SEMI)
ax.set_xticks(x, [f"{d} days" if False else d for d in b.index], fontsize=10, color=INK)
ax.set_ylabel("RMSE, percentage points")
ax.set_ylim(0, 12.5)
ax.spines["left"].set_visible(False)
save(fig, IMG)

# c. Timeline: nowcast vs first print, best model and naive at D+32, COVID shaded
IMG = "03_timeline.png"
best = mx[mx.rel_rmse == mx.rel_rmse.min()].iloc[0]
assert (best.model, best.variant, best.date) == ("5 Bridge: IIP", "dummy", "D+32")
sel = lambda m: nc[(nc.model == m) & (nc.variant == "dummy") & (nc.date == "D+32")].set_index("quarter").nowcast.reindex(WINDOW)
bm, nv, fp = sel("5 Bridge: IIP"), sel("1 Naive"), gdp.gdp_growth_first_print.reindex(WINDOW)
bq = bm.dropna().index
sub = (f"D+32 nowcasts, COVID dummy variant, against the GDP first print, {WINDOW[0]} to {WINDOW[-1]} "
       f"(n = {num(IMG, 'n_quarters', len(WINDOW), 'd', 'gdp.csv', 'quarters 2017Q2 to 2025Q3')}); "
       f"Bridge: IIP from {num(IMG, 'best_first_quarter', bq[0], '', 'backtest_nowcasts.csv', '5 Bridge: IIP dummy D+32, first quarter')} "
       f"(n = {num(IMG, 'best_n', len(bq), 'd', 'backtest_nowcasts.csv', '5 Bridge: IIP dummy D+32 nowcasts in window')})")
fig, ax = frame("Outside COVID, nowcasts hug last quarter's print", sub, axes=(0.07, 0.13, 0.78, 0.67))
xi = np.arange(len(WINDOW))
cidx = [i for i, q in enumerate(WINDOW) if q in COVID]
ax.axvspan(cidx[0] - 0.5, cidx[-1] + 0.5, color=COVID_BAND, lw=0, zorder=0)
ax.text((cidx[0] + cidx[-1]) / 2, 24, "COVID", ha="center", va="top", fontsize=9, color=SEC)
ax.plot(xi, fp, color=INK, lw=2, zorder=3)
ax.plot(xi, nv, color=GRAY, lw=2, zorder=2)
ax.plot(xi, bm, color=BLUE, lw=2, zorder=4)
ends = {"First print": (fp.iloc[-1], INK), "Naive": (nv.iloc[-1], GRAY), "Bridge: IIP": (bm.iloc[-1], BLUE)}
order = sorted(ends, key=lambda k: -ends[k][0])
for j, k in enumerate(order):  # spread the end labels so they don't collide
    ax.text(len(WINDOW) - 0.2, ends[order[0]][0] + 3 - 3 * j, k, va="center", fontsize=9, color=ends[k][1], **SEMI)
i3 = WINDOW.index("2022Q3")
n3 = num(IMG, "naive_2022Q3", nv.loc["2022Q3"], ".1f", "backtest_nowcasts.csv", "1 Naive dummy D+32 2022Q3 nowcast")
a3 = num(IMG, "actual_2022Q3", fp.loc["2022Q3"], ".1f", "gdp.csv", "2022Q3 first print")
ax.annotate(f"2022Q3: naive {n3}%,\nfirst print {a3}%", xy=(i3, nv.loc["2022Q3"]), xytext=(i3 + 2.2, 17), fontsize=8.5, color=SEC,
            arrowprops=dict(arrowstyle="-", color=SEC, lw=0.7), linespacing=1.3)
ax.set_xticks(xi[::4], [WINDOW[i] for i in xi[::4]], fontsize=9)
ax.set_xlim(-0.6, len(WINDOW) - 0.4)
ax.set_ylim(-30, 25)
ax.set_ylabel("Real GDP growth, % year on year")
ax.spines["left"].set_visible(False)
save(fig, IMG)

# d. Information calendar: when each month of the core indicators lands vs the GDP first print
IMG = "04_info_calendar.png"
CORE = {"Core 8": "core8_overall_base2011", "IIP": "iip_general_base2011"}
qend = lambda qs: pd.PeriodIndex(qs, freq="Q").end_time.normalize()
gdays = (gdp.loc[WINDOW, "release_date"] - qend(WINDOW)).dt.days
cal = {}
for label, ind in CORE.items():
    x = monthly[(monthly.indicator == ind) & (monthly.vintage == "first") & monthly.value.notna()].copy()
    per = pd.PeriodIndex(x.ref_month, freq="M")
    x["quarter"], x["pos"] = per.asfreq("Q").astype(str), (per.month - 1) % 3 + 1
    x = x[x.quarter.isin(WINDOW) & x.release_date.notna()]
    x["day"] = (x.release_date - qend(x.quarter)).dt.days
    cal[label] = x
share = avail[(avail.series == "Core 8") & (avail.date == "D+32")].on_time_share.iloc[0]
fig, ax = frame("Core 8 is almost complete a month before GDP",
                f"Days after quarter-end when each month's first print is released, {WINDOW[0]} to {WINDOW[-1]} "
                f"(n = {num(IMG, 'gdp_n', len(gdays), 'd', 'gdp.csv', 'GDP quarters 2017Q2 to 2025Q3')} GDP quarters)",
                foot="Dot = median, bar = 10th to 90th percentile. M1 to M3 are the quarter's three months. All three core 8 months were out by "
                     f"D+32 in {num(IMG, 'core8_d32_on_time_pct', 100 * share, '.0f', 'eda_nowcast_availability.csv', 'Core 8 D+32 on_time_share x 100')}% of quarters.",
                axes=(0.17, 0.17, 0.79, 0.63))
ax.grid(False)
rows = {"GDP first print": 0, "Core 8": 1, "IIP": 2}
for label, x in cal.items():
    r = rows[label]
    for m in (1, 2, 3):
        d = x[x.pos == m].day
        med = d.median()
        ax.plot([d.quantile(0.1), d.quantile(0.9)], [r, r], color=BLUE, alpha=0.35, lw=6, solid_capstyle="round")
        ax.scatter(med, r, s=60, color=BLUE, zorder=3, edgecolor="white", linewidth=1)
        ax.text(med, r - 0.22, f"M{m}", ha="center", va="bottom", fontsize=8.5, color=INK)
        ax.text(med, r + 0.2, "day " + minus(num(IMG,f"median_day|{label}|M{m}", med, ".0f", "indicators_monthly.csv", f"{CORE[label]} first, month {m}, median release day after quarter-end, 2017Q2-2025Q3")),
                ha="center", va="top", fontsize=8, color=SEC)
gmed = gdays.median()
ax.plot([gdays.min(), gdays.max()], [0, 0], color=INK, alpha=0.25, lw=6, solid_capstyle="round")
ax.scatter(gmed, 0, s=60, color=INK, zorder=3, edgecolor="white", linewidth=1)
gs = num(IMG, "gdp_median_day", gmed, ".0f", "gdp.csv", "median release day after quarter-end, 2017Q2-2025Q3")
gmin = num(IMG, "gdp_min_day", gdays.min(), "d", "gdp.csv", "min release day after quarter-end, 2017Q2-2025Q3")
gmax = num(IMG, "gdp_max_day", gdays.max(), "d", "gdp.csv", "max release day after quarter-end, 2017Q2-2025Q3")
ax.text(gmed, 0.2, f"day {gs} (range {gmin} to {gmax})", ha="center", va="top", fontsize=8, color=SEC)
ax.plot([gmed, gmed], [0.5, 2.6], color=INK, lw=0.8, ls=(0, (3, 3)), zorder=1)  # starts below the GDP label
c8m3 = cal["Core 8"][cal["Core 8"].pos == 3].day.median()
gap = num(IMG, "core8_m3_lead_days", gmed - c8m3, ".0f", "indicators_monthly.csv + gdp.csv", "GDP median day minus core 8 month 3 median day")
ax.annotate("", xy=(gmed - 1, 1), xytext=(c8m3 + 3, 1), arrowprops=dict(arrowstyle="<->", color=INK, lw=1, shrinkA=0, shrinkB=0))
ax.text((c8m3 + gmed) / 2 + 1, 0.93, f"{gap} days", ha="center", va="bottom", fontsize=9, color=INK, **SEMI)
ax.set_yticks(list(rows.values()), list(rows), fontsize=10, color=INK)
ax.set_ylim(2.6, -0.55)
ax.set_xlim(-75, 75)
ax.set_xlabel("Days after quarter-end")
ax.spines["left"].set_visible(False)
ax.axvline(0, color=HAIR, lw=0.8, zorder=0)
save(fig, IMG)

# e. GDP minus core 8 YoY, latest-vintage core 8 (the 2024Q4 first print is blank)
IMG = "05_gap.png"
GAPQ = [str(p) for p in pd.period_range("2023Q1", "2025Q3", freq="Q")]
c8 = lambda v: quarterly[(quarterly.indicator == "core8_overall_base2011") & (quarterly.vintage == v)].set_index("quarter").yoy_pct.reindex(GAPQ)
g = gdp.gdp_growth_first_print.reindex(GAPQ) - c8("latest")
assert g.notna().all() and c8("first").isna().sum() == 1
gf = gdp.gdp_growth_first_print.reindex(GAPQ) - c8("first")
early, late = g.loc["2023Q1":"2024Q2"], g.loc["2024Q3":"2025Q3"]
foot = (f"Core 8 is the latest vintage throughout, because its 2024Q4 first print is blank.\nOn first prints the averages are "
        f"{num(IMG, 'first_early_mean', gf.loc['2023Q1':'2024Q2'].mean(), '.1f', 'gdp.csv + indicators_quarterly.csv', 'first-print core 8, mean gap 2023Q1-2024Q2')} and "
        f"{num(IMG, 'first_late_mean', gf.loc['2024Q3':'2025Q3'].mean(), '.1f', 'gdp.csv + indicators_quarterly.csv', 'first-print core 8, mean gap 2024Q3-2025Q3 (2024Q4 missing)')} "
        f"(2024Q4 missing). A hypothesis, not tested.")
fig, ax = frame("The GDP–core 8 gap widened from mid-2024",
                f"GDP first-print growth minus core 8 YoY growth, percentage points, {GAPQ[0]} to {GAPQ[-1]} (n = {num(IMG, 'n', len(GAPQ), 'd', 'gdp.csv', 'quarters 2023Q1 to 2025Q3')})",
                foot=foot, axes=(0.08, 0.2, 0.88, 0.6))
xi = np.arange(len(GAPQ))
ax.bar(xi, g, width=0.62, color=BLUE)
for seg, lab in ((early, "early_mean"), (late, "late_mean")):
    i0, i1 = GAPQ.index(seg.index[0]), GAPQ.index(seg.index[-1])
    m = seg.mean()
    ax.plot([i0 - 0.4, i1 + 0.4], [m, m], color=INK, lw=1.2, ls=(0, (4, 2)), zorder=3)
    shown = num(IMG, lab, m, ".1f", "gdp.csv + indicators_quarterly.csv", f"latest-vintage core 8, mean gap {seg.index[0]}-{seg.index[-1]}")
    ax.text((i0 + i1) / 2 - (0 if lab == "early_mean" else 0.6), max(m, 0) + 0.35, f"average {shown} points", ha="center", va="bottom", fontsize=9, color=INK, **SEMI)
for i, q in enumerate(GAPQ):
    if q in ("2023Q1", "2025Q3") or g.loc[q] == g.max():
        shown = num(IMG, f"gap|{q}", g.loc[q], ".1f", "gdp.csv + indicators_quarterly.csv", f"{q} first-print GDP minus latest core 8 YoY")
        ax.text(i, g.loc[q] + (0.15 if g.loc[q] >= 0 else -0.15), minus(shown), ha="center", va="bottom" if g.loc[q] >= 0 else "top", fontsize=8.5, color=SEC)
ax.axhline(0, color=INK, lw=0.8)
ax.set_xticks(xi, GAPQ, fontsize=9)
ax.set_ylim(min(-1, g.min() - 1), 7.5)
ax.set_ylabel("Percentage points")
ax.spines["left"].set_visible(False)
save(fig, IMG)

pd.DataFrame(NUMBERS).to_csv(OUT / "numbers.csv", index=False)
print(f"Wrote 5 images and {len(NUMBERS)} numbers to {OUT}")
