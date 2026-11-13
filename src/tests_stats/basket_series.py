"""Daily equal-weighted basket return series (membership from the previous month-end; price returns)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.kmsi import engine as E


def basket_returns(col: str = "member_value_chain", start: str = "2010-01-01") -> pd.DataFrame:
    U = pd.read_parquet(E.ROOT / "data" / "staged" / "kbri_universe_monthly.parquet")
    U = U[U[col]]
    months = np.array(sorted(U["date"].unique()), dtype="datetime64[ns]")
    mem = {m: sorted(U.loc[U["date"].values.astype("datetime64[ns]") == m, "ticker"]) for m in months}
    cal = E.calendar()
    cal = cal[cal >= start]
    tick = sorted(U["ticker"].unique())
    px = pd.DataFrame({t: E.align(f"px_{t.lower()}", cal) for t in tick})
    ret = px.pct_change(fill_method=None)
    idx = np.searchsorted(months, cal.values.astype("datetime64[ns]"), side="left") - 1
    r = np.full(len(cal), np.nan)
    n = np.zeros(len(cal), int)
    for i, t in enumerate(cal):
        if idx[i] < 0:
            continue
        ms = mem[months[idx[i]]]
        v = ret.loc[t, ms].to_numpy(float)
        v = v[np.isfinite(v)]
        if len(v):
            r[i], n[i] = v.mean(), len(v)
    out = pd.DataFrame({"ret": r, "n": n}, index=cal)
    out = out[out["n"] > 0]
    out["index"] = (1 + out["ret"]).cumprod()
    return out
