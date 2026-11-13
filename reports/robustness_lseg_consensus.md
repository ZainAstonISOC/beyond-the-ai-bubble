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
