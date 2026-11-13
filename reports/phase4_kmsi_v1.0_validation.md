# Phase 4: KMSI v1.0 validation

Config 0dbfb07d8bd0. Published sample 1996-07-30 to 2026-11-12 (7617 days). AI momentum uses the ^SOX analogue (provisional).

| Check | Result | Criterion | Outcome |
| --- | --- | --- | --- |
| Convergent validity | 20-day KMSI vs NFCI r = -0.44 (n=1572); vs equity put/call r = -0.39 (n=3253); vs AAII bull-bear r = 0.32 (n=1570) | Expected sign on all three; abs(r) with NFCI >= 0.4 | Pass |
| Discriminant validity | R squared of KMSI on 21-day S&P 500 return and VIX percentile = 0.493 (n=7617) | R squared < 0.80 | Pass |
| Effective dimension | Effective number of signals = 4.33 of 8; first principal component explains 41% (complete cases 2008-06-17 to 2026-11-12) | Reported, no pass/fail. Below 2 = describe KMSI as mainly one factor |  |
| Ablation | Correlation with full KMSI when each is removed: momentum 0.990; breadth 0.986; volatility 0.974; options 0.991; credit 0.989; safe_haven 0.992; positioning 0.991; ai_momentum 0.987 | Flag any > 0.98 as redundant | Redundant: momentum, breadth, options, credit, safe_haven, positioning, ai_momentum |
| Weight sensitivity | Regime agreement with proposed weights: equal 91.9%; risk_heavy 81.9%; behaviour_heavy 76.2% | Agreement >= 80% for every scheme | Fail |
| Window sensitivity | Regime agreement with 1,260-day window: 504 75.4%; 2520 84.2%; expanding 81.7% | Agreement >= 80% for every window | Fail |
| Transform sensitivity | Correlation of percentile KMSI with robust z-score KMSI = 0.997 | r >= 0.9 | Pass |
| Episode readings | Dot-com peak (24 Mar 2000): 42.5; Lehman aftermath (10 Oct 2008): 21.8; Market low (20 Nov 2008): 18.4; COVID crash (16 Mar 2020): 10.2; COVID low (23 Mar 2020): 12.6; 2022 low (16 Jun 2022): 21.4; 2022 low (12 Oct 2022): 24.5; Tariff shock (8 Apr 2025): 21.4; 5 Nov 2026 sell-off: 35.8; Latest (12 Nov 2026): 49.1 | Reported as-is, never used for tuning |  |
| Look-ahead audit | 3 passed in 2.17s | Zero violations | Pass |
| Independent recalculation | PASS: 10 series, 7617 published days, worst difference 0.00e+00 | Match to 1e-9 | Pass |

Benchmarks: correlation with inverted VIX percentile 0.65; with S&P 500 drawdown from peak 0.20.

Component correlation matrix (complete cases):

|             |   momentum |   breadth |   volatility |   options |   credit |   safe_haven |   positioning |   ai_momentum |
|:------------|-----------:|----------:|-------------:|----------:|---------:|-------------:|--------------:|--------------:|
| momentum    |       1    |      0.57 |         0.51 |     -0.09 |     0.59 |         0.77 |          0.3  |          0.36 |
| breadth     |       0.57 |      1    |         0.26 |     -0.12 |     0.44 |         0.4  |          0.17 |          0.21 |
| volatility  |       0.51 |      0.26 |         1    |      0.01 |     0.58 |         0.42 |          0.05 |          0.19 |
| options     |      -0.09 |     -0.12 |         0.01 |      1    |    -0.12 |        -0.01 |         -0.12 |          0.07 |
| credit      |       0.59 |      0.44 |         0.58 |     -0.12 |     1    |         0.5  |          0.33 |          0.3  |
| safe_haven  |       0.77 |      0.4  |         0.42 |     -0.01 |     0.5  |         1    |          0.1  |          0.3  |
| positioning |       0.3  |      0.17 |         0.05 |     -0.12 |     0.33 |         0.1  |          1    |          0.06 |
| ai_momentum |       0.36 |      0.21 |         0.19 |      0.07 |     0.3  |         0.3  |          0.06 |          1    |
