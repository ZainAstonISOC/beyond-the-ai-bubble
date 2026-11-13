# Commit map

Before this repository was made public, the history was rewritten to remove licensed vendor data files (Cboe index histories and the Moody's and ICE BofA spread series distributed through FRED). The code still downloads them, and data/raw/manifest.json keeps the SHA-256 of every copy used. Nothing else changed: file contents, commit messages and dates are the same.

The OSF pre-registration (osf.io/fkude) and earlier drafts cite the original commit hashes. This table maps each one to its public equivalent.

| Date | Original commit | Public commit | Message |
| --- | --- | --- | --- |
| 2026-11-13 | 9b47528 | 5f2823e | Phase 2: ingestion and validation for KMSI inputs (34 series) |
| 2026-11-13 | deac810 | 3143cbb | Phase 3: KMSI v1.0 engine, independent NumPy recalculation (exact match), look-ahead tests |
| 2026-11-13 | b57ce02 | fcd9743 | Phase 4: KMSI validation; v1.1 drops SKEW per pre-registered fallback; v1.0 retained |
| 2026-11-13 | 0993d5c | d4c4a95 | Fix: synthetic bond covers IEF first trading day (removed Aug-Sep 2002 coverage gap); validation rerun |
| 2026-11-13 | 2d93247 | c4879fa | Add citation metadata (CITATION.cff), MIT code licence, CC BY 4.0 data licence |
| 2026-11-13 | 4865877 | 5b9cdd1 | CITATION.cff: drop repository URL until the public repo exists |
| 2026-11-13 | 9c69ca9 | 5cb5a87 | Phase 5: EDGAR ingestion with predecessor chains and archive fallback; point-in-time fundamentals panel (single-tag TTM, quarter plausibility, reconciliation); market panel; AI-disclosure evidence scan |
| 2026-11-13 | 87ad844 | 9d6464c | CITATION.cff: add OSF pre-registration (osf.io/fkude) |
| 2026-11-13 | 2436275 | 0b6b736 | Phase 5: reading pass for AI-disclosure condition (proposed entry filings with quoted passages) |
| 2026-11-13 | be7f20f | 049a5c7 | Universe: two baskets (registered disclosure basket primary; AI value-chain basket secondary, logged deviation); predecessor filings count toward history; confirmed reading-pass table |
| 2026-11-13 | b9787aa | fd077fa | Phase 6: KBRI v1.0 engine (reverse DCF, pooled-history and cross-section scoring, two baskets, size-neutral concentration); independent recalculation (exact); validation suite |
| 2026-11-13 | bc539f1 | 30d9f74 | Rule-based candidate pool (163 companies, SIC rule + size screen with plausibility bounds); full-pool fundamentals, market, universe, reading pass; KBRI rerun, recalculation (exact) and validation |
| 2026-11-13 | 0ad5e6f | daca854 | KMSI v1.1: AI-momentum uses the KBRI disclosure basket from its first month with >=5 members (SOX analogue before); recalculation updated; look-ahead tests extended to KBRI panels and basket membership |
| 2026-11-13 | 849c641 | 20c7c53 | KCEI v1.0 (sourced inputs, Scope 2 accounting gap, US load scenarios, operator stress); dot-com analogue (CAPE/ECY, NDX/SOX stretch, Damodaran EV/Sales 1999-2026); market panel: alternative debt tags, no silent zero debt |
| 2026-11-13 | 49e7039 | 823a6ce | KBRI rerun after debt fix (recalculation exact; validation unchanged); KCEI outputs |
| 2026-11-13 | 90e3695 | d2478ba | Phase 8: pre-registered hypothesis tests H1-H5 (outcomes Y1-Y4, block bootstrap, permutation, expanding-window H4 with Clark-West, Diebold-Mariano and BSADF benchmark, Holm); exploratory H4 diagnostics; report |
