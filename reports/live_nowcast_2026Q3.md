# Live nowcast: India real GDP growth, 2026Q3 (Jul to Sep 2026)

Made on 03 Nov 2026, by notebooks/04_models.ipynb. It is not edited after 30 Nov 2026, when the first print is due.

## Nowcast

**5.8% to 8.3% YoY** (3 Bridge: core 8, (a) COVID dropped from training, centre 7.0%).

**In the backtest, no model beat the naive rule outside COVID.** The naive rule's 7.8% is as defensible a central guess as the model's. The core 8 bridges also nowcast too low in all three 2022-23 base quarters so far (see the notebook).

| Model | Centre | Range (±1 RMSE) | Backtest RMSE vs naive |
|---|---|---|---|
| 1 Naive | 7.8% | 6.8% to 8.8% | 1.00 |
| 2 AR(1) | 7.6% | 6.4% to 8.8% | 1.13 |
| 3 Bridge: core 8 | 7.0% | 5.8% to 8.3% | 1.20 |
| 4 Bridge + AR: core 8 | 7.5% | 5.7% to 9.3% | 1.75 |

The range is ±1 RMSE from the non-COVID real-time backtest at D+32, excluding 2022Q3 (2011-12 base). **It ignores the base mismatch below, so it understates the uncertainty.**

## Base mismatch

The models were fitted on 2011-12 base GDP first prints and 2011-12 base core 8, to 2025Q3. GDP is now published on the 2022-23 base (from 2025Q4), and core 8 has moved to the 2022-23 base, which adds iron ore as a ninth sector. The old-base coefficients are applied to new-base core 8 YoY as though the two were comparable. Only 3 new-base quarters exist to check this, which is too few to measure it.

## Data used

| Input | Value | Source | Public by |
|---|---|---|---|
| Core 8 YoY, Jul to Sep 2026 vs Jul to Sep 2025 (2022-23 base) | 6.27% | https://eaindustry.nic.in/eight_core_infra/Core_Industries_2022_23_20261021.xlsx | 21 Oct 2026 (date in file name) |
| Same, using the Jul and Aug 2026 first prints from the monthly press releases | 6.03% | eaindustry.nic.in press releases | 21 Sep 2026 |
| Previous quarter's GDP first print, 2026Q2 (2022-23 base) | 7.8% | https://www.mospi.gov.in/uploads/latestReleases/latest_release_1788172583113_d65a77cf-240e-4491-82ee-59f78618fa41_Press_Note_on_GDP_Estimates_for_Q1_2026-27.pdf | 31 Aug 2026 |

The Jul to Sep 2025 values in the YoY are from the 2022-23 back series in the same file. They were never published as first prints, unlike the training data.

## Backtest context

At D+32, outside COVID and excluding 2022Q3, 3 Bridge: core 8 had RMSE 1.26 points, against 1.05 for the naive rule (relative RMSE 1.20, Diebold-Mariano p = 0.58, n = 11 test quarters). With so few quarters, the test can't tell the two apart. See notebooks/04_models.ipynb.

**Model 8 (change model, Phase 4b), added 03 Nov 2026:** 7.7% (range 6.6% to 8.8%, ±1 RMSE 1.09, (a) COVID dropped from training, D+32, excluding 2022Q3; relative RMSE 1.17 vs naive, DM p = 0.30, n = 9). It adds the predicted change to the 2026Q2 first print of 7.8%. The predicted change comes from the move in 2022-23 base core 8 YoY from 3.94% in 2026Q2 to 6.27% in 2026Q3, both from the 21 Oct 2026 file. The same base mismatch applies.
