# Beyond the AI Bubble: KMSI, KBRI and KCEI

Code, data and reports for the Howden Research working paper *Beyond the AI Bubble: Measuring Sentiment, Speculative Risk and Climate-Finance Exposure in the AI Cycle*.

The project builds three indices from public data and tests them against hypotheses registered on the Open Science Framework before any test was run ([osf.io/fkude](https://osf.io/fkude)).

- **KMSI**, the Khan Market Sentiment Index: daily fear and greed from eight market signals, published from October 2001.
- **KBRI**, the Khan Bubble Risk Index: monthly bubble-risk scores for 163 US-listed firms in the AI value chain from 2010, built from point-in-time SEC filings and the revenue growth each share price implies (reverse DCF).
- **KCEI**, the Khan Climate and Energy Impact framework: US data-centre load scenarios, stress tests for specialist data-centre owners, and the gap between location-based and market-based Scope 2 emissions.

## Results in brief

Two of the five registered hypotheses count against the framework. The headline result is negative: out of sample (2019 to 2026), adding KMSI and KBRI to a price-only model made drawdown forecasts worse (AUC 0.37 against 0.50), and a Phillips-Shi-Yu BSADF statistic did better than both (0.53). Every 20% drawdown in the AI value chain since 2010 was mostly market beta, and revenue kept growing after each one. Full results are in `reports/phase8_hypothesis_tests.md`.

## Layout

| Path | Contents |
| --- | --- |
| `config/` | Frozen specifications (`kmsi_v1.0.yaml`, `kmsi_v1.1.yaml`, `kbri_v1.0.yaml`), the 163-firm candidate pool and sourced KCEI inputs |
| `src/ingest/` | Downloads every source and records URL, time and SHA-256 in `data/raw/manifest.json` |
| `src/validate/` | Data checks, including the quarter-sum reconciliation of XBRL fundamentals |
| `src/kmsi/`, `src/kbri/`, `src/kcei/` | Index engines, each with an independent NumPy recalculation |
| `src/dotcom/` | Dot-com comparison (CAPE, Damodaran EV/Sales vintages 1999 to 2026) |
| `src/tests_stats/` | Validation suites and the pre-registered hypothesis tests |
| `tests/` | Look-ahead audit |
| `data/outputs/` | Published index series and test outputs |
| `reports/` | Phase reports, reading-pass table and validation results |

## Rebuilding

Python 3.11 or later with pandas, numpy, scipy, statsmodels, scikit-learn, pyarrow and pyyaml.

```
python3 -m src.ingest.run_ingest          # market and macro inputs
python3 -m src.validate.check_staged      # data checks
python3 -m src.kmsi.engine                # KMSI (KMSI_VERSION=1.0 for the robustness series)
python3 -m src.kmsi.recalc_numpy          # independent recalculation
python3 -m src.ingest.edgar               # SEC filings for the candidate pool
python3 -m src.kbri.fundamentals          # point-in-time fundamentals panel (about an hour)
python3 -m src.kbri.market
python3 -m src.kbri.universe
python3 -m src.kbri.engine                # KBRI
python3 -m src.kbri.recalc_numpy
python3 -m src.kcei.kcei                  # KCEI
python3 -m src.tests_stats.hypotheses     # pre-registered tests H1 to H5
python3 -m pytest tests/                  # look-ahead audit
```

## Data not redistributed

Some inputs are licensed and aren't included: Yahoo Finance prices, the AAII survey, Cboe index histories (VIX, VIX3M, VIX9D, VVIX, SKEW, equity put/call) and the Moody's and ICE BofA spread series distributed through FRED. The ingestion code downloads them, and the manifest records the hash of each copy used, so you can check that your download matches ours. SEC EDGAR, Treasury and Federal Reserve series, CFTC data, Damodaran's and Shiller's public datasets are included.

The history was rewritten before publication to remove those files. `COMMIT_MAP.md` maps the commit hashes cited in the OSF registration to their public equivalents.

## Citation

See `CITATION.cff`. Code is MIT licensed (`LICENSE`); derived data and outputs are CC BY 4.0 (`DATA_LICENSE.md`).

Research and educational use only. Not investment advice.
