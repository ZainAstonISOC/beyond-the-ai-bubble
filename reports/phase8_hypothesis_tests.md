# Phase 8: pre-registered hypothesis tests

Registration: osf.io/fkude (13 Nov 2026). Code: `src/tests_stats/hypotheses.py` (registered tests), `src/tests_stats/h4_diagnostics.py` (exploratory). Outputs: `data/outputs/phase8_*.{json,parquet}`. Random seed 20261113.

Every registered test was run once and is reported below whatever it showed. Tests that need long history use the value-chain basket (a logged deviation). KMSI v1.1 throughout.

## Summary

| Hypothesis | Registered "counts against" rule | Result | Verdict |
|---|---|---|---|
| H1 fear without fundamental deterioration | falls in ≥2/3 of episodes, or significantly negative difference at 5% | Revenue never fell after a fear episode, but grew 2.6 pp slower over the next two quarters than in other quarters (p = 0.001; Holm 0.008). Capex 6.8 pp slower (p = 0.004; Holm 0.025). | **Counts against** |
| H2 heterogeneous risk | mean IQR of KBRI-rel < 15 **and** eta² not significant | IQR 13.1 (below threshold); eta² 0.129, permutation p < 0.001 | Does not count against (one leg failed) |
| H3 drawdowns are not fundamental collapses | revenue and RPO negative in most episodes **and** residual explains most of the fall | Revenue growth positive after all 6 troughs; AI-specific residual > 50% of the fall in 1 of 6 | Does not count against |
| H4 framework adds out-of-sample information | AUC gain < 0.03 and Clark-West p > 0.10 | AUC 0.37 (framework) vs 0.50 (price only) vs 0.53 (GSADF); Clark-West p = 0.93 | **Counts against**, against both benchmarks |
| H5 climate-finance exposure is material on both sides | either side immaterial | +149 to +404 TWh US load by 2028; $51.8bn idle PP&E at a 40% utilisation cut; Scope 2 accounting gap 81–100% | Does not count against |

Two of five hypotheses count against the framework under the rules we fixed in advance. H4 is the more serious one: as specified, KMSI and KBRI made drawdown forecasts worse out of sample, not better.

## Outcomes

Y1 and Y2 are built for the value-chain basket at 63, 126 and 252 trading days (`phase8_outcomes_value_chain.parquet`).

Y3 (realised next-four-quarter revenue growth minus g*): the median member-month gap is +6.3 pp and the basket median is negative in only 8.5% of months. Read literally, the market priced in less growth than members went on to deliver. The comparison sets one year of realised growth against a 10-year implied rate, so it shouldn't be read as a valuation verdict on its own. The paper should say so.

Y4 is the market/duration/credit/residual decomposition reported under H3.

## H1

Fear episodes (KMSI v1.1 below 25 for ten consecutive days, starts at least 90 days apart, from mid-2010): 17 Aug 2011, 1 Sep 2015, 21 Jan 2016, 1 Nov 2018, 18 Mar 2020, 7 Mar 2022, 27 Jun 2022, 21 Oct 2022, 17 Apr 2025. That's nine episodes in nine distinct quarters.

| Item (basket aggregate, 2-quarter-forward growth) | Share of episodes falling | Episode minus other quarters | One-sided p | Holm |
|---|---|---|---|---|
| Revenue (TTM) | 0/9 | −2.6 pp | 0.001 | 0.008 |
| Operating cash flow (TTM) | 3/9 | −2.6 pp | 0.078 | 0.392 |
| Capex (TTM) | 2/9 | −6.8 pp | 0.004 | 0.025 |

The level claim holds: aggregate revenue kept growing after every fear episode. The relative claim fails: fear quarters were followed by measurably slower growth in revenue and capex. Fear in this sample wasn't detached from fundamentals; it came with a deceleration. Under the registered rule (either leg is enough) H1 counts against.

## H2

KBRI-rel's cross-sectional interquartile range averages 13.1 points over 193 months (KBRI-abs: 13.5). That's below the 15-point threshold. Group membership (semis/equipment, hardware/networking, software, specialists) explains 12.9% of within-month variance on average, and none of 1,000 label permutations matched it (p < 0.001). The rule needs both legs to fail, so H2 doesn't count against. The dispersion threshold was missed, though, and the paper should report it as a partial result: risk differs by group much more clearly than it differs across firms in general.

## H3 and Y4

Six drawdowns of 20% or more in the value-chain basket since 2010. Factor loadings come from the 252 trading days ending the day before each peak.

| Peak | Trough | Fall | Market | Duration | Credit | AI-specific residual | Residual share | Revenue growth, 2Q after trough | RPO growth, 2Q after trough |
|---|---|---|---|---|---|---|---|---|---|
| 2011-02-18 | 2011-08-19 | −24.1% | −17.5% | −1.0% | +0.5% | −9.3% | 36% | +8.2% | n/a |
| 2015-05-28 | 2016-02-11 | −20.3% | −15.9% | 0.0% | +1.0% | −11.4% | 54% | +2.2% | n/a |
| 2018-08-29 | 2018-12-24 | −24.5% | −25.3% | +0.2% | +0.6% | −5.9% | 22% | +2.9% | +9.1% |
| 2020-02-19 | 2020-03-20 | −31.8% | −48.6% | +0.1% | +2.6% | +11.1% | −32% | +6.3% | +8.8% |
| 2021-11-16 | 2022-10-14 | −44.2% | −32.8% | +5.7% | −3.8% | −21.2% | 41% | +1.2% | +8.0% |
| 2025-02-18 | 2025-04-08 | −28.7% | −28.9% | 0.0% | +0.3% | −3.4% | 10% | +7.9% | +93.6% |

Factor contributions are sums of daily simple returns, so they don't add exactly to the peak-to-trough fall. Revenue grew after every trough. The AI-specific residual was the largest single part only in 2015–16. Market beta did most of the work everywhere else, and in March 2020 the basket did better than its beta implied. H3 doesn't count against.

The 2025 RPO figure (+93.6%) is an aggregate across members and is probably dominated by one or two very large backlog reporters. It needs a firm-level check before it goes in the paper.

## H4

Monthly design from January 2012. Training uses months whose 126-day label window closed at least 183 days before the forecast month (74 months at the first test date). Expanding-window test: January 2019 to the last month with a complete label, 94 months. Event (Y1 drawdown of 15% or more within 126 days) rate: 16% in training, 41% in test.

| Model | Predictors | AUC | Brier | Y2 out-of-sample R² vs historical mean |
|---|---|---|---|---|
| a | 63-day return, drawdown from peak, VIX percentile | 0.502 | 0.308 | −0.41 |
| b | a + KMSI | 0.434 | 0.334 | −0.53 |
| c | b + KBRI | 0.366 | 0.360 | −0.72 |
| d | a + BSADF | 0.531 | 0.307 | −0.41 |

| Test | Value | p |
|---|---|---|
| AUC gain c − a | −0.135 | 0.998 (block bootstrap, H0 gain ≤ 0) |
| AUC gain c − d | −0.164 | 0.999 |
| Clark-West, a nested in c | | 0.931 |
| Clark-West, a nested in b | | 0.889 |
| Diebold-Mariano, c vs d (squared Y2 errors) | | 0.943 |

H4 counts against the framework under both the price-only and the bubble-test comparison. No model beat the historical mean on excess returns. The framework model was the worst of the four.

Exploratory diagnostics (not registered; `phase8_h4_diagnostics.json`) show why. Here are univariate AUCs for the drawdown event:

| Predictor | 2012–2018 | 2019–2026 |
|---|---|---|
| KMSI (low = fear) | 0.14 | 0.45 |
| KBRI basket | 0.69 | 0.29 |
| BSADF | 0.61 | 0.62 |
| VIX percentile | 0.83 | 0.54 |

KBRI's relationship with drawdown risk reversed sign between the two periods. Before 2019, high KBRI came before drawdowns. After 2019, high KBRI came during a long run-up in which drawdowns were frequent but recovered, so a high reading marked strength rather than fragility. KMSI's strong pre-2019 signal (fear clusters before further falls) mostly disappeared. BSADF was the only predictor whose association held steady across both periods. A model fitted on the first regime and scored on the second was always going to do badly, and it did.

This is the finding the paper has to lead with on H4: a composite bubble index calibrated on 2010s data didn't forecast drawdowns in the 2019–2026 AI cycle, and a single explosive-root statistic held up better.

## H5

Opportunity side: incremental US data-centre load by 2028 of +149 TWh (LBNL low), +276.5 TWh (midpoint) and +404 TWh (high) over 2023. Risk side: at a 40% utilisation cut, $51.8bn of net PP&E would sit idle across CRWV, NBIS, APLD, EQIX and DLR, and CoreWeave's interest cover drops to 0.58. Scope 2 accounting gap (share of location-based emissions removed by market-based accounting): Amazon 82% (2023) to 83% (2025), Microsoft 89% (FY2020) to 97% (FY2024), Alphabet 81% (2025), Meta 100% (2024), 87% across the four. Both sides are material, so H5 doesn't count against. It's scenario evidence, not a statistical test.

## Multiple testing

Holm adjustment across the eight registered p-values. These survive at 5%: H2 eta² (< 0.001), H1 revenue (0.008), H1 capex (0.025). These don't: H1 cash flow (0.39) and all four H4 tests (1.00).

## Implementation choices and deviations (for the change log and the OSF update)

- H1 bootstrap: a moving-block bootstrap (blocks of four quarters) resampling quarter growth and the episode label together, 10,000 draws, centred one-sided p-value. The plan said "block bootstrap" without a block length.
- H2 permutation: 1,000 within-month label permutations.
- H4 sample starts January 2012, when the value-chain KBRI and the BSADF minimum window are both available. The label gap is 183 calendar days.
- H1/H3 fundamentals are outcomes, so they use the latest-filed (restated) value for each period, not point-in-time values. Predictors stay point-in-time.
- Y4 loadings come from 252 trading days ending the day before each peak; contributions are sums of daily simple returns.
- H5 has no inferential test; the rule is applied to scenario magnitudes.

The basket fundamentals behind H1 and H3 depend on XBRL coverage. Firm counts per quarter and item are in `phase8_basket_fundamentals_vc.parquet`.

## Disclosure basket (2024 onward, descriptive)

The registered disclosure basket's daily series starts 3 April 2017 (NVDA alone until 2024). Since January 2024 its maximum drawdown is −46.1%, with the trough on 4 April 2025. The basket has had at least five members only since December 2024, which is too short for the H1, H3 or H4 designs. It gets reported descriptively in the paper.
