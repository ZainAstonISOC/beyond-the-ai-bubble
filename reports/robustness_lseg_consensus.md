# Robustness: price-implied growth against analyst consensus (exploratory)

Not registered. Run on 13 November 2026, after the registered tests. Code: `src/robustness/lseg_consensus.py`. Summary: `data/outputs/robustness_lseg_consensus_summary.json`.

## Data

LSEG I/B/E/S monthly consensus, January 2010 to October 2026, pulled through the LSEG Data Library in Workspace CodeBook for all 163 pool firms: mean revenue estimate for FY1 and FY2 (with the number of estimates) and mean long-term growth. Licensed data, used under Howden Research's LSEG Workspace access for research; the vendor values stay in `data/licensed/` (git-ignored) and only aggregate statistics are published.

Consensus forward growth is FY2 over FY1 minus one, which needs no currency conversion. Sample: value-chain basket firm-months with both g* and consensus, 11,642 firm-months across 158 firms (99.9% of eligible firm-months). Ratios beyond plus or minus 200% are dropped.

## Results

1. **Level.** Over the whole sample the median g* (7.3%) sits below consensus one-year-forward revenue growth (10.8%) and consensus long-term growth (14.4%). Prices implied less ten-year growth than analysts expected for the next year in 68% of firm-months.
2. **The crossover.** The basket median g* was below consensus forward growth in every month from 2010 to 2022. It drew level in June 2023, rose above it in September 2023, and was above it in every month of 2024, 11 of 12 months in 2025 and 6 of 10 months in 2026 to October (January to March 2026 below). For most of the time since mid-2023, share prices in the AI value chain have implied ten years of revenue growth faster than analysts expect for the coming year.
3. **Forecasting realised growth.** Consensus is the better forecast of realised next-twelve-month revenue growth: median absolute error 6.1 points against 10.1 for g*, and a mean monthly rank correlation of 0.65 against 0.54.
4. **Returns.** The gap between g* and consensus forward growth predicts lower 12-month returns across firms: mean monthly rank IC -0.061 (Newey-West t = -2.17 with 11 lags, p = 0.03). The sign is the same in 2012 to 2018 (-0.087, t = -1.84) and 2019 to 2025 (-0.047, t = -1.21). g* alone has no predictive power (IC 0.027, t = 0.59). Consensus growth alone predicts higher returns (IC 0.093, t = 1.65), driven by 2012 to 2018. Quintiles of the gap aren't monotonic: highest-gap minus lowest-gap is -4.1 points a year.

## Reading

Two findings matter for the paper. The 2023 crossover is new: it dates the point at which prices began to assume more sustained growth than analysts were forecasting even for the next year. And the price-analyst gap keeps the same sign across both periods, unlike the KBRI basket score in H4. That makes it a candidate for a future registered test. These results are exploratory and the 2019 to 2025 estimate alone isn't significant.

## Extended checks on the gap

Code: `src/robustness/lseg_gap_extended.py`; output: `data/outputs/robustness_lseg_gap_extended.json`. Exploratory, run after the registered tests. Price returns from month-end closes; regressors are within-month standardised ranks; returns winsorised 1/99 within month.

**Fama-MacBeth, 12-month returns (Newey-West, 11 lags; coefficient per one standard deviation of rank):**

- Gap alone: -1.6 points a year (t = -1.40).
- Gap with size, 12-1 momentum, beta and EV/Sales: -3.2 points (t = -2.64), 178 months, about 56 firms a month.
- Gap with the same controls and analysts' long-term growth: -2.4 points (t = -2.71); long-term growth itself +0.9 (t = 0.51).
- Split into its legs with controls: g* -3.8 points (t = -2.37), consensus growth +5.9 points (t = 2.72). With both the gap and consensus growth in the regression, neither is significant (t = -1.33 and 1.82): the two are collinear by construction.

**Fama-MacBeth, 1-month returns (non-overlapping, 3 lags):** gap with controls -0.24 points a month (t = -2.21); gap alone -0.11 (t = -1.07).

**Quintile portfolios, monthly rebalancing, equal weight:** lowest-gap minus highest-gap 0.36% a month (t = 1.08; 4.4% a year; Sharpe 0.28), not significant; 0.41% in 2010-2018 and 0.30% in 2019-2026. Returns by quintile aren't monotonic.

**Time series, inside the H4 design:** adding the basket-median gap to the price-only model raises out-of-sample AUC from 0.502 to 0.513 (bootstrap p for no gain 0.50). Univariate AUC of the gap is 0.617 in 2012-2018 and 0.524 in 2019-2026: the same side of 0.5 in both, unlike KBRI (0.692 then 0.289), but weak in the test period. BSADF is 0.606 and 0.622.

**95% block-bootstrap intervals for the registered H4 AUCs (6-month blocks, 5,000 draws):** price-only 0.502 [0.336, 0.642]; +KMSI 0.434 [0.261, 0.579]; +KMSI+KBRI 0.366 [0.223, 0.496]; price+BSADF 0.531 [0.348, 0.694].

Reading: the gap's cross-sectional link to returns survives standard controls and analysts' long-term growth forecasts, but it's modest, and a simple portfolio sort doesn't deliver a significant spread in a cross-section of about 58 firms. It doesn't help time drawdowns. Its value is that it keeps its sign, at both levels, through the regime change that broke KBRI.

## Debt maturities (KBRI financing component)

KBRI v1.0 proxies debt due within 24 months by current debt over cash, because SEC XBRL rarely tags maturities. LSEG Fundamentals gives short-term debt and current portion of long-term debt, plus long-term debt maturing in year two, for 2,676 firm-years (code: `src/robustness/lseg_debt.py`; summary: `data/outputs/robustness_lseg_debt_summary.json`). Using that sum over cash in place of the proxy, usable 90 days after fiscal year end:

- The two measures rank firms similarly (rank correlation 0.55) and LSEG covers 89% of firm-months against 99.8% for the proxy.
- Company KBRI correlates 0.993 with v1.0, and 95.6% of firm-months stay in the same 20-point band. The financing component correlates 0.93.
- The value-chain basket correlates 0.996 with v1.0 from 2012, when every registered test starts, with a mean difference of about 0.2 points. The 2010 and 2011 values move more (up to 9 points), because LSEG maturity history is thin before fiscal 2010.

The proxy doesn't drive any result in the paper.

## Delisted firms

An LSEG screen for inactive US technology equities returned only 35 recent delistings, so it can't rebuild the historical universe. The survivorship check in the paper (dropping the 35 firms that left the value-chain basket; correlation 0.99) stands, and a full delisted-firm universe remains future work.

## Customer concentration

LSEG Workspace has no standard data item for largest-customer share. The variable stays missing, as in v1.0.
