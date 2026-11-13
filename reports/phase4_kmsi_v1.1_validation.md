# Phase 4: KMSI v1.1 validation

Config f3187d25946f. Published sample 2001-10-10 to 2026-11-12 (6314 days). AI momentum uses the ^SOX analogue (provisional).

| Check | Result | Criterion | Outcome |
| --- | --- | --- | --- |
| Convergent validity | 20-day KMSI vs NFCI r = -0.48 (n=1306); vs equity put/call r = -0.40 (n=3253); vs AAII bull-bear r = 0.46 (n=1305) | Expected sign on all three; abs(r) with NFCI >= 0.4 | Pass |
| Discriminant validity | R squared of KMSI on 21-day S&P 500 return and VIX percentile = 0.587 (n=6314) | R squared < 0.80 | Pass |
| Effective dimension | Effective number of signals = 4.07 of 8; first principal component explains 43% (complete cases 2011-09-16 to 2026-11-12) | Reported, no pass/fail. Below 2 = describe KMSI as mainly one factor |  |
| Ablation | Correlation with full KMSI when each is removed: momentum 0.991; breadth 0.986; volatility 0.979; options 0.995; credit 0.990; safe_haven 0.992; positioning 0.991; ai_momentum 0.987 | Flag any > 0.98 as redundant | Redundant: momentum, breadth, options, credit, safe_haven, positioning, ai_momentum |
| Weight sensitivity | Regime agreement with proposed weights: equal 93.1%; risk_heavy 84.5%; behaviour_heavy 81.0% | Agreement >= 80% for every scheme | Pass |
| Window sensitivity | Regime agreement with 1,260-day window: 504 71.9%; 2520 82.1%; expanding 78.3% | Agreement >= 80% for every window | Fail |
| Transform sensitivity | Correlation of percentile KMSI with robust z-score KMSI = 0.997 | r >= 0.9 | Pass |
| Episode readings | Dot-com peak (24 Mar 2000): nan; Lehman aftermath (10 Oct 2008): 13.1; Market low (20 Nov 2008): 12.0; COVID crash (16 Mar 2020): 5.4; COVID low (23 Mar 2020): 8.1; 2022 low (16 Jun 2022): 18.0; 2022 low (12 Oct 2022): 20.7; Tariff shock (8 Apr 2025): 18.4; 5 Nov 2026 sell-off: 34.7; Latest (12 Nov 2026): 50.5 | Reported as-is, never used for tuning |  |
| Look-ahead audit | 5 passed in 4.22s | Zero violations | Pass |
| Independent recalculation | PASS: 10 series, 6314 published days, worst difference 0.00e+00 | Match to 1e-9 | Pass |

Benchmarks: correlation with inverted VIX percentile 0.73; with S&P 500 drawdown from peak 0.24.

Component correlation matrix (complete cases):

|             |   momentum |   breadth |   volatility |   options |   credit |   safe_haven |   positioning |   ai_momentum |
|:------------|-----------:|----------:|-------------:|----------:|---------:|-------------:|--------------:|--------------:|
| momentum    |       1    |      0.42 |         0.5  |      0.49 |     0.58 |         0.73 |          0.35 |          0.38 |
| breadth     |       0.42 |      1    |         0.19 |      0.19 |     0.38 |         0.26 |          0.21 |          0.14 |
| volatility  |       0.5  |      0.19 |         1    |      0.59 |     0.54 |         0.41 |          0.13 |          0.24 |
| options     |       0.49 |      0.19 |         0.59 |      1    |     0.28 |         0.39 |         -0.03 |          0.25 |
| credit      |       0.58 |      0.38 |         0.54 |      0.28 |     1    |         0.46 |          0.43 |          0.26 |
| safe_haven  |       0.73 |      0.26 |         0.41 |      0.39 |     0.46 |         1    |          0.1  |          0.24 |
| positioning |       0.35 |      0.21 |         0.13 |     -0.03 |     0.43 |         0.1  |          1    |          0.04 |
| ai_momentum |       0.38 |      0.14 |         0.24 |      0.25 |     0.26 |         0.24 |          0.04 |          1    |
