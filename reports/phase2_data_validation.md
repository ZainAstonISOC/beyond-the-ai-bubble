# Phase 2 data validation

Series checked: 35. Hard failures (duplicates, non-finite values, publication before observation, coverage short of inventory): 0.

| Series | Source | n | First | Last | Lag rule | Gaps over limit | Max gap (days) | Jumps (robust z>10) | Start vs inventory |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| aaii_bull_bear | AAII Sentiment Survey | 2049 | 1987-07-24 | 2026-11-12 | same day (reported date) | 0 | 14 | 0  |  |
| baa10y | FRED | 10215 | 1986-01-02 | 2026-11-10 | next business day | 0 | 5 | 13 1986-06-04, 1986-06-06, 1987-04-15, 1987-05-11 | ok |
| bamlh0a0hym2 | FRED | 785 | 2023-11-13 | 2026-11-11 | next business day | 0 | 4 | 1 2025-04-03 | ok |
| cftc_es_net_pct_oi | CFTC Traders in Financial Futures | 1065 | 2006-06-13 | 2026-11-03 | +3 calendar days (Friday release of Tuesday data) | 0 | 8 | 0  | ok |
| cftc_es_oi | CFTC TFF | 1065 | 2006-06-13 | 2026-11-03 | +3 calendar days | 0 | 8 | 66 2006-06-20, 2006-09-19, 2006-12-19, 2007-03-13 |  |
| dfii10 | FRED | 5969 | 2003-01-02 | 2026-11-10 | next business day | 0 | 4 | 2 2009-03-18, 2020-03-20 | ok |
| dgs10 | FRED | 16200 | 1962-01-02 | 2026-11-10 | next business day | 0 | 5 | 46 2008-11-20, 2009-01-02, 2009-02-17, 2009-03-18 | ok |
| equity_pc | Cboe | 3253 | 2006-11-01 | 2019-10-04 | same day | 0 | 5 | 0  | ok |
| nfci | FRED | 2914 | 1971-01-08 | 2026-11-06 | +5 calendar days | 0 | 7 | 55 1971-08-06, 1971-08-13, 1971-08-20, 1974-01-18 | ok |
| px_gc_f | Yahoo Finance chart API | 6577 | 2000-08-30 | 2026-11-12 | same day | 0 | 5 | 3 2008-09-17, 2013-04-15, 2026-01-30 | ok |
| px_hyg | Yahoo Finance chart API | 4930 | 2007-04-11 | 2026-11-11 | same day | 0 | 5 | 34 2008-09-15, 2008-09-17, 2008-09-18, 2008-09-29 | ok |
| px_idx_gspc | Yahoo Finance chart API | 14339 | 1970-01-02 | 2026-11-12 | same day | 0 | 7 | 15 1987-10-19, 1987-10-21, 1987-10-26, 2008-09-29 | ok |
| px_idx_ndx | Yahoo Finance chart API | 10360 | 1985-10-01 | 2026-11-12 | same day | 0 | 7 | 7 1987-10-19, 1987-10-26, 2001-01-03, 2008-09-29 | ok |
| px_idx_sox | Yahoo Finance chart API | 8188 | 1994-05-04 | 2026-11-12 | same day | 0 | 7 | 0  | ok |
| px_idx_sp500ew | Yahoo Finance chart API | 4999 | 2006-12-08 | 2026-11-12 | same day | 0 | 5 | 9 2008-09-29, 2008-10-13, 2008-10-15, 2008-10-28 | ok |
| px_ief | Yahoo Finance chart API | 6112 | 2002-07-30 | 2026-11-11 | same day | 0 | 5 | 0  | ok |
| px_rsp | Yahoo Finance chart API | 5922 | 2003-05-01 | 2026-11-11 | same day | 0 | 5 | 9 2008-09-29, 2008-10-13, 2008-10-15, 2008-10-28 | ok |
| px_smh | Yahoo Finance chart API | 6650 | 2000-06-05 | 2026-11-11 | same day | 0 | 7 | 0  | ok |
| px_spy | Yahoo Finance chart API | 8505 | 1993-01-29 | 2026-11-11 | same day | 0 | 7 | 12 2008-09-29, 2008-10-13, 2008-10-15, 2008-10-28 | ok |
| px_tlt | Yahoo Finance chart API | 6112 | 2002-07-30 | 2026-11-11 | same day | 0 | 5 | 0  | ok |
| px_xlb | Yahoo Finance chart API | 7015 | 1998-12-22 | 2026-11-11 | same day | 0 | 7 | 4 2008-10-13, 2008-10-15, 2008-10-28, 2020-03-16 |  |
| px_xle | Yahoo Finance chart API | 7015 | 1998-12-22 | 2026-11-11 | same day | 0 | 7 | 8 2008-10-09, 2008-10-13, 2008-10-15, 2008-10-28 |  |
| px_xlf | Yahoo Finance chart API | 7015 | 1998-12-22 | 2026-11-11 | same day | 0 | 7 | 25 2008-07-16, 2008-09-19, 2008-09-29, 2008-10-07 |  |
| px_xli | Yahoo Finance chart API | 7015 | 1998-12-22 | 2026-11-11 | same day | 0 | 7 | 8 2001-09-17, 2008-10-13, 2008-10-15, 2008-10-28 |  |
| px_xlk | Yahoo Finance chart API | 7015 | 1998-12-22 | 2026-11-11 | same day | 0 | 7 | 4 2001-01-03, 2008-10-28, 2020-03-16, 2025-04-09 | ok |
| px_xlp | Yahoo Finance chart API | 7015 | 1998-12-22 | 2026-11-11 | same day | 0 | 7 | 3 2020-03-12, 2020-03-13, 2020-03-17 |  |
| px_xlu | Yahoo Finance chart API | 7015 | 1998-12-22 | 2026-11-11 | same day | 0 | 7 | 7 2008-10-13, 2008-10-28, 2008-11-21, 2020-03-12 |  |
| px_xlv | Yahoo Finance chart API | 7015 | 1998-12-22 | 2026-11-11 | same day | 0 | 7 | 5 2000-01-10, 2001-09-17, 2008-10-13, 2008-10-15 |  |
| px_xly | Yahoo Finance chart API | 7015 | 1998-12-22 | 2026-11-11 | same day | 0 | 7 | 3 2008-10-15, 2020-03-12, 2020-03-16 |  |
| skew | Cboe | 9268 | 1990-01-02 | 2026-11-11 | same day | 1 | 13 | 9 1990-06-25, 1990-07-18, 1990-07-20, 1990-08-02 | ok |
| t10y2y | FRED | 12609 | 1976-06-01 | 2026-11-12 | next business day | 0 | 5 | 24 1979-10-09, 1980-02-15, 1980-02-29, 1980-03-20 | ok |
| vix | Cboe | 9314 | 1990-01-02 | 2026-11-11 | same day | 0 | 7 | 3 2018-02-05, 2024-12-18, 2026-11-05 | ok |
| vix3m | Cboe | 4315 | 2009-09-18 | 2026-11-12 | same day | 0 | 5 | 3 2018-02-05, 2020-03-16, 2024-08-05 | ok |
| vix9d | Cboe | 3989 | 2011-01-04 | 2026-11-12 | same day | 0 | 5 | 1 2018-02-05 |  |
| vvix | Cboe | 5146 | 2006-03-06 | 2026-11-12 | same day | 6 | 21 | 9 2006-03-15, 2006-03-16, 2006-04-11, 2006-05-22 |  |
