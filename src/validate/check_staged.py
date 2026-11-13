"""Phase 2 gate: validate staged series and write reports/phase2_data_validation.md.

Checks per series: observation count, first/last date, duplicates, non-finite
values, publication date never before observation date, largest calendar gap,
and suspicious jumps (robust z of daily change > 10 for prices/levels).
Coverage is compared with the start dates verified in the Data inventory.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
STAGED = ROOT / "data" / "staged"
REPORT = ROOT / "reports" / "phase2_data_validation.md"

# Start dates from the spec's Data inventory (first observation verified 13 Nov 2026)
EXPECTED_START = {
    "vix": "1990-01-02", "skew": "1990-01-02", "vix3m": "2009-09-18", "equity_pc": "2006-11-01",
    "baa10y": "1986-01-02", "bamlh0a0hym2": "2023-11-13", "dgs10": "1962-01-02", "dfii10": "2003-01-02",
    "t10y2y": "1976-06-01", "nfci": "1971-01-08", "px_idx_gspc": "1985-01-01", "px_idx_ndx": "1985-10-01",
    "px_idx_sox": "1994-05-01", "px_rsp": "2003-05-01", "px_spy": "1993-01-01", "px_xlk": "1998-12-01",
    "px_smh": "2000-06-01", "px_tlt": "2002-07-01", "px_ief": "2002-07-01", "px_gc_f": "2000-08-01",
    "px_hyg": "2007-04-01", "px_idx_sp500ew": "2006-12-01", "cftc_es_net_pct_oi": "2006-06-13",
}
WEEKLY = {"nfci", "cftc_es_net_pct_oi", "cftc_es_oi", "aaii_bull_bear"}
ALLOW_GAP_DAYS = {"daily": 6, "weekly": 15}   # calendar days; >6 on daily = missing week (except known closures)
KNOWN_CLOSURES = [("2001-09-10", "2001-09-17")]  # 9/11 market closure


def check(sid: str) -> dict:
    df = pd.read_parquet(STAGED / f"{sid}.parquet")
    meta = json.loads((STAGED / f"{sid}.meta.json").read_text())
    v = df["value"]
    gaps = df.index.to_series().diff().dt.days
    kind = "weekly" if sid in WEEKLY else "daily"
    big = gaps[gaps > ALLOW_GAP_DAYS[kind]]
    for a, b in KNOWN_CLOSURES:
        big = big[~((big.index > pd.Timestamp(a)) & (big.index <= pd.Timestamp(b)))]
    dv = np.log(v.where(v > 0)).diff() if (v > 0).all() else v.diff()
    med, mad = dv.median(), (dv - dv.median()).abs().median()
    rz = (dv - med) / (1.4826 * mad) if mad > 0 else dv * 0
    jumps = rz[rz.abs() > 10]
    exp = EXPECTED_START.get(sid)
    start_ok = None if exp is None else df.index.min() <= pd.Timestamp(exp) + pd.Timedelta(days=45)
    return {
        "series": sid, "source": meta.get("source", ""), "n": len(df),
        "first": df.index.min().date(), "last": df.index.max().date(),
        "dups": int(df.index.duplicated().sum()), "nonfinite": int((~np.isfinite(v)).sum()),
        "pub_before_obs": int((df["published"] < df.index).sum()),
        "gaps_over_limit": len(big), "max_gap_days": int(gaps.max()) if len(gaps) > 1 else 0,
        "largest_gap_end": big.idxmax().date() if len(big) else "",
        "jumps_rz10": len(jumps), "jump_dates": ", ".join(str(d.date()) for d in jumps.index[:4]),
        "expected_start": exp or "", "start_ok": start_ok, "lag": meta.get("lag", ""),
    }


def main() -> None:
    ids = sorted(p.stem for p in STAGED.glob("*.parquet"))
    rows = [check(s) for s in ids]
    t = pd.DataFrame(rows)
    hard_fail = t[(t.dups > 0) | (t.nonfinite > 0) | (t.pub_before_obs > 0) | (t.start_ok == False)]  # noqa: E712
    lines = ["# Phase 2 data validation", "",
             f"Series checked: {len(t)}. Hard failures (duplicates, non-finite values, publication before observation, "
             f"coverage short of inventory): {len(hard_fail)}.", "",
             "| Series | Source | n | First | Last | Lag rule | Gaps over limit | Max gap (days) | Jumps (robust z>10) | Start vs inventory |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        so = "" if r["start_ok"] is None else ("ok" if r["start_ok"] else "SHORT")
        lines.append(f"| {r['series']} | {r['source']} | {r['n']} | {r['first']} | {r['last']} | {r['lag']} | "
                     f"{r['gaps_over_limit']} | {r['max_gap_days']} | {r['jumps_rz10']} {r['jump_dates']} | {so} |")
    REPORT.write_text("\n".join(lines) + "\n")
    print(t[["series", "n", "first", "last", "dups", "pub_before_obs", "gaps_over_limit", "max_gap_days",
             "largest_gap_end", "jumps_rz10", "jump_dates", "start_ok"]].to_string(index=False))
    print("\nHARD FAILURES:", len(hard_fail), list(hard_fail.series))


if __name__ == "__main__":
    main()
