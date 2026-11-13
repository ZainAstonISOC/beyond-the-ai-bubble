# OSF registration update, 13 November 2026

Registration: https://osf.io/fkude (Secondary Data Preregistration, registered 13 November 2026)

## Justification for update

This update records how the registered analysis was carried out. Every change below was fixed before the test it affects was run. The hypothesis tests (H1 to H5) were run once, on 13 November 2026, and all results are reported, including the two hypotheses that count against the framework (H1 and H4).

## Deviations and implementation choices

1. **KMSI v1.1 drops Cboe SKEW.** SKEW failed its registered convergent check (r = -0.20 daily, -0.34 on 20-day averages against the equity put/call ratio, 2006 to 2019). Version 1.1 uses the VIX/VIX3M ratio alone in the options component, as the pre-registered fallback required. Version 1.0 is kept as a robustness series.
2. **Secondary value-chain basket.** Under the registered AI-disclosure rule, Nvidia was the only member from 2017 to 2023 and the basket first had five members in December 2024, because Microsoft, Alphabet, Amazon, Meta and Oracle don't name AI as a principal revenue-growth driver in their 10-Ks. The registered disclosure basket stays the primary basket. A secondary basket of every pool firm meeting the size and filing-history rules (18 members in January 2010, 125 in October 2026) is used for tests that need long history (H1, H3, H4). Decided before any KBRI score existed.
3. **Rule-based candidate pool.** The hand-picked candidate list in the plan was replaced by a rule: NYSE/Nasdaq SEC filers in SIC codes 3674, 3559, 3825, 3827 (semiconductors and equipment), 3570-3579, 3661, 3663, 3669, 3672 (hardware and networking) and 7370-7374 (software), plus data-centre REITs and Amazon, worth at least $10bn ($2bn for specialist infrastructure) at any month-end since 2010. 163 firms. Decided before any hypothesis test, to remove hindsight from firm selection.
4. **H1 bootstrap.** Moving-block bootstrap with four-quarter blocks, resampling quarter growth and the episode label together, 10,000 draws, centred one-sided p-value. The plan specified a block bootstrap without a block length.
5. **H2 permutation test.** 1,000 within-month permutations of group labels. The plan gave no count.
6. **H4 sample and label gap.** Monthly design from January 2012, when the value-chain KBRI and the BSADF minimum window are both available. Training uses only months whose 126-day outcome window closed at least 183 days before the forecast month.
7. **Outcome fundamentals.** H1 and H3 outcomes use the latest filed (restated) value for each period, because they are outcomes. Every predictor stays point in time.

Also: Y4 factor loadings are estimated on the 252 trading days ending the day before each peak; H5 is judged on scenario magnitudes and has no inferential test. An exploratory analysis of H4 (univariate AUC by period) was run after the registered tests and is labelled as unregistered.

## Code and commit references

The public repository is https://github.com/ZainAstonISOC/beyond-the-ai-bubble. Before it was made public, its history was rewritten to remove licensed vendor data (Cboe index histories and the Moody's and ICE BofA series distributed through FRED). File contents, messages and dates are otherwise unchanged. The commit cited in this registration maps as follows (full table in COMMIT_MAP.md):

| Purpose | Original commit | Public commit |
| --- | --- | --- |
| Code at registration | 9c69ca9 | 5cb5a87 |
| Hypothesis tests run | 90e3695 | d2478ba |

The registered specification PDF is unchanged (SHA-256 25d9682ac2eb0cab6f911614c76f229bdd15e21943c464b1d5e47f44ecb39d67).

## Results summary

H1 counts against (revenue growth 2.6 points slower after fear episodes, p = 0.001, Holm 0.008). H2 doesn't count against (KBRI-rel IQR 13.1, below the 15-point threshold, but group effect significant, p < 0.001). H3 doesn't count against (revenue grew after all six 20% drawdowns; AI-specific residual largest only once). H4 counts against (AUC 0.37 for the framework model against 0.50 price-only and 0.53 with BSADF; Clark-West p = 0.93). H5 doesn't count against. Full report: reports/phase8_hypothesis_tests.md.
