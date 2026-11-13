"""Phase 2 ingestion: fetch and stage every KMSI input and validation series."""
from __future__ import annotations

import sys
import traceback

from . import sources as S

YAHOO = ["^GSPC", "^NDX", "^SOX", "^SP500EW", "SPY", "RSP", "IEF", "TLT", "GC=F", "HYG", "SMH",
         "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
YAHOO_PRICE_ONLY = {"^GSPC", "^NDX", "^SOX", "^SP500EW", "GC=F"}  # indices / futures: no adjclose
FRED_DAILY = ["BAA10Y", "BAMLH0A0HYM2", "DGS10", "DFII10", "T10Y2Y"]


def main() -> int:
    jobs = []
    jobs += [(f"cboe {s}", lambda s=s: S.cboe_index(s)) for s in S.CBOE]
    jobs += [("cboe equity p/c", S.cboe_equity_pc)]
    jobs += [(f"fred {s}", lambda s=s: S.fred(s)) for s in FRED_DAILY]
    jobs += [("fred NFCI", lambda: S.fred("NFCI", weekly_lag_days=5))]
    jobs += [(f"yahoo {t}", lambda t=t: S.yahoo(t, "close" if t in YAHOO_PRICE_ONLY else "adjclose")) for t in YAHOO]
    jobs += [("cftc E-mini", S.cftc_es), ("aaii", S.aaii)]
    failed = []
    for name, fn in jobs:
        try:
            df = fn()
            print(f"OK   {name:22s} n={len(df):6d}  {df.index.min().date()} -> {df.index.max().date()}")
        except Exception:
            failed.append(name)
            print(f"FAIL {name}\n{traceback.format_exc(limit=2)}")
    print(f"\n{len(jobs) - len(failed)}/{len(jobs)} sources staged")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
