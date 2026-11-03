"""Check the README insight images: every number in reports/readme/numbers.csv, recomputed from data/processed by a separate
route where one exists (relative RMSE from the raw nowcasts, not the metrics column), plus image paths, image sizes and the
numbers quoted in the README's Key insights section.

Usage: python tools/check_readme.py
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
R = ROOT / "reports" / "readme"
results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))

nc = pd.read_csv(P / "backtest_nowcasts.csv")
gdp = pd.read_csv(P / "gdp.csv", parse_dates=["release_date"]).set_index("quarter")
monthly = pd.read_csv(P / "indicators_monthly.csv", parse_dates=["release_date"])
quarterly = pd.read_csv(P / "indicators_quarterly.csv")
avail = pd.read_csv(P / "eda_nowcast_availability.csv")
nums = pd.read_csv(R / "numbers.csv", dtype={"shown": str})

WINDOW = [str(p) for p in pd.period_range("2017Q2", "2025Q3", freq="Q")]
COVID = {str(p) for p in pd.period_range("2020Q2", "2022Q2", freq="Q")}
rmse = lambda e: float(np.sqrt((e ** 2).mean()))

def common(variant):
    """The backtest's test quarters: those where models 1 to 4 all have a nowcast at all three dates."""
    x = nc[(nc.variant == variant) & nc.model.str[0].isin(list("1234")) & nc.quarter.isin(WINDOW)]
    full = x.groupby("quarter").apply(lambda d: len(d[["model", "date"]].drop_duplicates()) == 12)
    return set(full[full].index)
HEAD = {v: {q for q in common(v) if q not in COVID and q != "2022Q3"} for v in ("drop", "dummy")}
COVID_TEST = common("dummy") & COVID

def rel_rmse(model, variant, date="D+32"):
    """Model RMSE over naive RMSE on the model's own non-COVID test quarters, from the raw nowcasts."""
    m = nc[(nc.model == model) & (nc.variant == variant) & (nc.date == date) & nc.quarter.isin(HEAD[variant])].set_index("quarter")
    n = nc[(nc.model == "1 Naive") & (nc.variant == variant) & (nc.date == date)].set_index("quarter").loc[m.index]
    return rmse(m.nowcast - m.actual) / rmse(n.nowcast - n.actual), len(m)

def covid_rmse(model, date):
    x = nc[(nc.model == model) & (nc.variant == "dummy") & (nc.date == date) & nc.quarter.isin(COVID_TEST)]
    return rmse(x.nowcast - x.actual), sorted(x.quarter)

qend = lambda qs: pd.PeriodIndex(qs, freq="Q").end_time.normalize()
def release_days(ind, pos):
    x = monthly[(monthly.indicator == ind) & (monthly.vintage == "first") & monthly.value.notna() & monthly.release_date.notna()]
    per = pd.PeriodIndex(x.ref_month, freq="M")
    q = per.asfreq("Q").astype(str)
    keep = np.asarray(q.isin(WINDOW)) & np.asarray((per.month - 1) % 3 + 1 == pos)
    return (x.release_date[keep].values - qend(q[keep]).values).astype("timedelta64[D]").astype(int)
gdays = (gdp.loc[WINDOW, "release_date"] - qend(WINDOW)).dt.days

GAPQ = [str(p) for p in pd.period_range("2023Q1", "2025Q3", freq="Q")]
core8 = lambda v: quarterly[(quarterly.indicator == "core8_overall_base2011") & (quarterly.vintage == v)].set_index("quarter").yoy_pct.reindex(GAPQ)
gap_l = gdp.gdp_growth_first_print.reindex(GAPQ) - core8("latest")
gap_f = gdp.gdp_growth_first_print.reindex(GAPQ) - core8("first")

PAIRS = [(m, v) for m in ["2 AR(1)", "3 Bridge: core 8", "4 Bridge + AR: core 8", "5 Bridge: IIP", "8 Change: Δ core 8"] for v in ("drop", "dummy")]
ns = [rel_rmse(m, v)[1] for m, v in PAIRS]
head_q = sorted(HEAD["drop"] | HEAD["dummy"])
cq = covid_rmse("1 Naive", "D+32")[1]
bi = nc[(nc.model == "5 Bridge: IIP") & (nc.variant == "dummy") & (nc.date == "D+32") & nc.quarter.isin(WINDOW)].sort_values("quarter")
nv3 = nc[(nc.model == "1 Naive") & (nc.variant == "dummy") & (nc.date == "D+32") & (nc.quarter == "2022Q3")].nowcast.iloc[0]
c8m3 = np.median(release_days("core8_overall_base2011", 3))

EXPECT = {
    ("01_headline.png", "first_quarter"): head_q[0], ("01_headline.png", "last_quarter"): head_q[-1],
    ("01_headline.png", "n_min"): min(ns), ("01_headline.png", "n_max"): max(ns),
    **{("01_headline.png", f"rel_rmse|{m}|{v}"): rel_rmse(m, v)[0] for m, v in PAIRS},
    ("02_covid.png", "first_quarter"): cq[0], ("02_covid.png", "last_quarter"): cq[-1], ("02_covid.png", "n"): len(cq),
    **{("02_covid.png", f"rmse_naive|{d}"): covid_rmse("1 Naive", d)[0] for d in ("D+0", "D+32", "D+45")},
    **{("02_covid.png", f"rmse_bridge|{d}"): covid_rmse("3 Bridge: core 8", d)[0] for d in ("D+0", "D+32", "D+45")},
    **{("02_covid.png", f"cut_pct|{d}"): 100 * (1 - covid_rmse("3 Bridge: core 8", d)[0] / covid_rmse("1 Naive", d)[0]) for d in ("D+0", "D+32", "D+45")},
    ("03_timeline.png", "n_quarters"): len(gdp.loc[WINDOW].gdp_growth_first_print.dropna()),
    ("03_timeline.png", "best_first_quarter"): bi.quarter.iloc[0], ("03_timeline.png", "best_n"): len(bi),
    ("03_timeline.png", "naive_2022Q3"): nv3, ("03_timeline.png", "actual_2022Q3"): gdp.loc["2022Q3", "gdp_growth_first_print"],
    ("04_info_calendar.png", "gdp_n"): len(gdays),
    ("04_info_calendar.png", "core8_d32_on_time_pct"): 100 * avail[(avail.series == "Core 8") & (avail.date == "D+32")].on_time_share.iloc[0],
    **{("04_info_calendar.png", f"median_day|{lab}|M{m}"): np.median(release_days(ind, m))
       for lab, ind in (("Core 8", "core8_overall_base2011"), ("IIP", "iip_general_base2011")) for m in (1, 2, 3)},
    ("04_info_calendar.png", "gdp_median_day"): gdays.median(), ("04_info_calendar.png", "gdp_min_day"): gdays.min(),
    ("04_info_calendar.png", "gdp_max_day"): gdays.max(), ("04_info_calendar.png", "core8_m3_lead_days"): gdays.median() - c8m3,
    ("05_gap.png", "n"): len(GAPQ),
    ("05_gap.png", "early_mean"): gap_l.loc["2023Q1":"2024Q2"].mean(), ("05_gap.png", "late_mean"): gap_l.loc["2024Q3":"2025Q3"].mean(),
    ("05_gap.png", "first_early_mean"): gap_f.loc["2023Q1":"2024Q2"].mean(), ("05_gap.png", "first_late_mean"): gap_f.loc["2024Q3":"2025Q3"].mean(),
    **{("05_gap.png", f"gap|{q}"): gap_l.loc[q] for q in ("2023Q1", "2025Q2", "2025Q3")},
}

def shown_as(expected, shown):
    if isinstance(expected, str):
        return expected
    dp = len(shown.split(".")[1]) if "." in shown else 0
    return f"{expected:.{dp}f}"

bad = [(r.image, r.key, r.shown, shown_as(EXPECT[(r.image, r.key)], r.shown)) for r in nums.itertuples()
       if (r.image, r.key) in EXPECT and shown_as(EXPECT[(r.image, r.key)], r.shown) != r.shown]
check("numbers.csv: every number recomputed from data/processed", not bad, f"{len(nums)} numbers" + (f"; mismatches {bad}" if bad else ""))
keys = set(zip(nums.image, nums.key))
check("numbers.csv: one recomputation per number, none missing or extra", keys == set(EXPECT) and len(keys) == len(nums),
      f"missing {sorted(set(EXPECT) - keys)} extra {sorted(keys - set(EXPECT))}" if keys != set(EXPECT) else "")

IMAGES = ["01_headline.png", "02_covid.png", "03_timeline.png", "04_info_calendar.png", "05_gap.png"]
for f in IMAGES:
    im = Image.open(R / f)
    check(f"{f}: 1600 x 900 at 200 dpi", im.size == (1600, 900) and round(im.info["dpi"][0]) == 200, f"{im.size}")

readme = (ROOT / "README.md").read_text(encoding="utf8")
paths = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", readme)
check("README: every image path resolves", all((ROOT / p).is_file() for p in paths), f"{len(paths)} images")
alts = re.findall(r"!\[([^\]]*)\]\(reports/readme/", readme)
check("README: the 5 insight images appear in order a to e, each with alt text",
      [p.split("/")[-1] for p in paths if p.startswith("reports/readme/")] == IMAGES and all(len(a) > 40 for a in alts))
check("README: dashboard screenshot placeholder", "<!-- dashboard screenshot: add reports/readme/00_dashboard.png -->" in readme)

section = readme.split("## Key insights", 1)[1].split("\n## ", 1)[0]
text = re.sub(r"<!--.*?-->|\(reports/readme/[^)]+\)", "", section)
text = re.sub(r"\b\d{4}Q[1-4]\b|D\+\d+|\bQ[1-4]\b|mid-2024", "", text)  # quarter labels and nowcast-date names
quoted = re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?", text)
allowed = set(nums.shown)
missing = sorted(set(q for q in quoted if q not in allowed))
check("README Key insights: every number appears in numbers.csv", not missing, f"{len(quoted)} numbers" + (f"; not found {missing}" if missing else ""))
labels = set(re.findall(r"\b\d{4}Q[1-4]\b", section))
known_q = set(nums.shown) | {"2022Q3", "2017Q2", "2025Q3", "2024Q2", "2024Q3", "2023Q1", "2024Q4", "2025Q2"}
check("README Key insights: quarter labels are ones the images use", labels <= known_q, str(sorted(labels - known_q)))

out = pd.DataFrame(results, columns=["check", "ok", "detail"])
print(out.to_string(index=False))
print(f"\n{out.ok.sum()} of {len(out)} checks passed")
raise SystemExit(0 if out.ok.all() else 1)
