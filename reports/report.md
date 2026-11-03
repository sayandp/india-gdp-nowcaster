# Nowcasting India's GDP first print with monthly indicators

*India GDP Nowcaster, analysis write-up, 3 Nov 2026*

## Question

Can monthly indicators, such as the core 8 industries index and IIP, predict India's quarterly real GDP growth before MoSPI's first estimate? If so, how early? The bar is a naive rule: repeat the previous quarter's first print.

## Data and how it was built

- **Target:** the first-print YoY growth of quarterly real GDP, read from each MoSPI press note (or its PIB copy), 2017Q2 to 2025Q3, 34 quarters, all on the 2011-12 base. Later quarters are on the 2022-23 base and are kept separate.
- **Indicators:** monthly first prints with release dates.
  - Core 8 (OEA press releases) and IIP (MoSPI press notes), both on the 2011-12 base.
  - Merchandise exports and GST (PIB releases).
  - AAI domestic air passengers and CEA electricity, tested in exploration only.
  - E-way bills and diesel, which are latest vintage and undated, so they are labelled `[look-ahead]`.
- **Breaks:** series breaks and base changes are kept as separate series, never spliced. Every value links to the file it came from.
- **Quarterly YoY:** computed from the months available, against the same months a year earlier, first print against first print.

## Method

- **Nowcast dates:** D+0, D+32 and D+45 days after quarter-end, about 61, 29 and 16 days before the median GDP release (day 61). They were chosen from the release calendar, so core 8 is complete by D+32 and IIP by D+45.
- **As-of rule:** a monthly value counts only if its release date is on or before the nowcast date. A GDP print counts only if released before it.
- **Models:** OLS with an intercept, refitted every quarter on an expanding window, starting once 8 training quarters exist.
  - Naive, AR(1), core 8 bridge, core 8 bridge + AR, and IIP bridge.
  - Add-on tests: the bridge plus exports, or plus GST.
  - `[look-ahead]` sensitivity: the bridge plus e-way bills, or plus diesel.
- **Model 8:** a change model (change in GDP print on change in core 8 YoY), added afterwards as the single pre-registered extra model.
- **COVID handling:** 2020Q2 to 2022Q2 are handled two ways: (a) dropped from training, or (b) kept with a dummy. Headline metrics use non-COVID test quarters, with models and dates compared on the same quarters.

## Results

**Relative RMSE against naive, non-COVID test quarters, excluding 2022Q3 (below 1 means better than naive)**

| Model | (a) D+0 | (a) D+32 | (a) D+45 | (b) D+0 | (b) D+32 | (b) D+45 |
|---|---|---|---|---|---|---|
| Naive, RMSE in points | 1.05 | 1.05 | 1.05 | 1.14 | 1.14 | 1.14 |
| AR(1) | 1.13 | 1.13 | 1.13 | 1.12 | 1.12 | 1.12 |
| Bridge: core 8 | 1.30 | 1.20 | 1.20 | 1.64 | 1.81 | 1.81 |
| Bridge + AR: core 8 | 1.52 | 1.75 | 1.75 | 1.63 | 1.80 | 1.80 |
| Bridge: IIP | 1.14 | 1.15 | 1.34 | 1.04 | 0.97 | 1.09 |
| Model 8: change in core 8 | 1.17 | 1.17 | 1.17 | 1.71 | 1.61 | 1.61 |

**Test quarters:** variant (a) has 11 (2023Q1 to 2025Q3) and variant (b) has 12 (2022Q4 to 2025Q3). The IIP bridge has 10 or 6 at the later dates in (a) and 10 at D+45 in (b). Model 8 has 9 or 10 in (a) and 11 or 12 in (b). Each relative RMSE uses naive on the same quarters.

**Model 8 was pre-registered as the only extra model before its results were seen.**

- **Nothing beats naive outside COVID.** The only value below 1, the IIP bridge at 0.97 (D+32, b), has a Diebold-Mariano p of 0.87.
- **No p-value is below 0.10.** The lowest outside COVID, 0.10 (0.105, model 8 with the COVID dummy at D+0), favours naive, not the model. The test isn't reliable on 9 to 12 quarters anyway.
- **More months help a little.** The core 8 bridge in (a) goes from 1.30 at D+0 to 1.20 at D+32, once month 3 arrives. It still loses to naive.
- **With 2022Q3 included,** variant (b) appears to win: AR(1) 0.61, the IIP bridge 0.47 to 0.51 at D+0 and D+32, model 8 0.75 to 0.82. All of this comes from one quarter. Naive carried forward 2022Q2's base-effect 13.5% against an actual 6.3%.
- **The core 8 bridge is biased low,** by 0.85 to 1.01 points in (a). On the three 2022-23 base quarters (an illustration, n = 3), it missed by about 2 points each time, against an RMSE of 0.23 for naive.

**COVID quarters.** This is where indicators help. At D+32 in variant (b), across 8 COVID test quarters, the core 8 bridge has RMSE 4.29 against naive's 10.67 (relative 0.40). Model 8 has 0.42 on 7 quarters. Models with an AR term do worse than naive (2.01 and 2.05), because they extrapolate the last swing.

**Hypothesis, not tested: GDP has decoupled from core 8 since mid-2024.** From 2023Q1 to 2024Q2, GDP growth exceeded core 8 growth by 0.2 points on average. From 2024Q3 to 2025Q3, the gap was 3.9 points (4 quarters, with 2024Q4 missing a first print). In the three 2022-23 base quarters it was about 4 points. If growth has become less industry-led, a bridge fitted on earlier quarters will under-predict, which matches the bias above. Testing this needs more quarters and services-side indicators.

**Live call, 2026Q3, made 3 Nov 2026:**

- **Primary:** naive, 7.8% ± 1.05.
- **Core 8 bridge:** 7.0%.
- **Model 8:** 7.7%, almost the same as naive, so 30 Nov is a test of naive against the bridge.

## Limitations

- **Small samples:** headline comparisons rest on 6 to 12 test quarters, add-on and look-ahead tests on 5 to 13 outside COVID (2 to 4 inside it), COVID on 1 to 8 (mostly 7 or 8), and the new-base check on 3. The exploration correlations rest on 3 to 29 quarters.
- **Proxy release dates:**
  - Core 8 and AAI dates are PDF creation dates, not announced release days.
  - GST first prints from Apr 2024 have no date, so they are unused.
  - CEA, e-way bills, diesel and petrol have no release dates. The `[look-ahead]` tests assume core 8's timing.
- **Unverified GDP quarters:** 2016Q4, 2019Q3 and 2021Q3 have an unverified release day, and only the last two are in the window. Removing them moves relative RMSEs by up to 0.53, but no model in variant (a) gets below naive.
- **Base-year break:** GDP and core 8 moved to the 2022-23 base, which adds iron ore to core 8. The live call applies old-base coefficients to new-base data, and only 3 new-base quarters exist to check this.
- **Unchecked parsing:** exports, air and GST values come from a single source each, so parsing errors can't be fully ruled out.
- **Diebold-Mariano test:** it isn't reliable at this sample size. Its p-values are indicative only.
- **Bootstrap intervals:** the bootstrap in the exploration's like-for-like check resamples quarters independently and ignores autocorrelation, so its intervals are too narrow.

## What I'd do next

- **Score the live call** on 30 Nov 2026, and keep scoring each quarter before its print.
- **Rebuild on the 2022-23 base** as new-base first prints accumulate, rather than bridging bases.
- **Test the decoupling hypothesis** with services-side indicators that have real release dates, and model the GDP–core 8 gap directly.
- **Collect release dates** for CEA and PPAC data, so those series can leave `[look-ahead]`.
- **Score forecast intervals** as well as point errors. A shock detector is judged by how it does in large moves.
