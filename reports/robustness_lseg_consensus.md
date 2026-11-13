# Robustness: price-implied growth against analyst consensus (exploratory)

Not registered. Run on 13 November 2026, after the registered tests. Code: `src/robustness/lseg_consensus.py`. Summary: `data/outputs/robustness_lseg_consensus_summary.json`.

## Data

LSEG I/B/E/S monthly consensus, January 2010 to October 2026, pulled through the LSEG Data Library in Workspace CodeBook for all 163 pool firms: mean revenue estimate for FY1 and FY2 (with the number of estimates) and mean long-term growth. Licensed data, used under Howden Research's LSEG Workspace access for research; the vendor values stay in `data/licensed/` (git-ignored) and only aggregate statistics are published.

Consensus forward growth is FY2 over FY1 minus one, which needs no currency conversion. Sample: value-chain basket firm-months with both g* and consensus, 11,642 firm-months across 158 firms (99.9% of eligible firm-months). Ratios beyond plus or minus 200% are dropped.

## Results

1. **Level.** Over the whole sample the median g* (7.3%) sits below consensus one-year-forward revenue growth (10.8%) and consensus long-term growth (14.4%). Prices implied less ten-year growth than analysts expected for the next year in 68% of firm-months.
2. **The crossover.** The basket median g* was below consensus forward growth in every month from 2010 to 2022. It first rose above it in June 2023 and stayed above it in every month of 2024, 92% of months in 2025 and 60% of months in 2026 to October. Since mid-2023, share prices in the AI value chain have implied ten years of revenue growth faster than analysts expect for the coming year.
3. **Forecasting realised growth.** Consensus is the better forecast of realised next-twelve-month revenue growth: median absolute error 6.1 points against 10.1 for g*, and a mean monthly rank correlation of 0.65 against 0.54.
4. **Returns.** The gap between g* and consensus forward growth predicts lower 12-month returns across firms: mean monthly rank IC -0.061 (Newey-West t = -2.17 with 11 lags, p = 0.03). The sign is the same in 2012 to 2018 (-0.087, t = -1.84) and 2019 to 2025 (-0.047, t = -1.21). g* alone has no predictive power (IC 0.027, t = 0.59). Consensus growth alone predicts higher returns (IC 0.093, t = 1.65), driven by 2012 to 2018. Quintiles of the gap aren't monotonic: highest-gap minus lowest-gap is -4.1 points a year.

## Reading

Two findings matter for the paper. The 2023 crossover is new: it dates the point at which prices began to assume more sustained growth than analysts were forecasting even for the next year. And the price-analyst gap keeps the same sign across both periods, unlike the KBRI basket score in H4. That makes it a candidate for a future registered test. These results are exploratory and the 2019 to 2025 estimate alone isn't significant.

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
