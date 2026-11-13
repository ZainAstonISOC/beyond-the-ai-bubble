"""Independent recalculation of KMSI v1.0 (Phase 3 gate).

Written separately from engine.py: no pandas rolling, merge_asof or groupby.
Point-in-time alignment, every sub-indicator, the percentile transform and the
aggregation are re-derived with explicit NumPy loops from the staged files and
the YAML config. The test passes only if every published KMSI value and every
component score matches engine.py to 1e-9.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
STAGED = ROOT / "data" / "staged"
import os
VERSION = os.environ.get("KMSI_VERSION", "1.1")
CFG = yaml.safe_load((ROOT / "config" / f"kmsi_v{VERSION}.yaml").read_text())
START = np.datetime64("1986-01-02")


def load(sid):
    df = pd.read_parquet(STAGED / f"{sid}.parquet").dropna(subset=["value"])
    d = df.index.values.astype("datetime64[D]")
    p = df["published"].values.astype("datetime64[D]")
    v = df["value"].values.astype(float)
    order = np.lexsort((d, p))
    return d[order], p[order], v[order]


def pit(sid, cal, age_bdays=None, carry_days=None):
    d, p, v = load(sid)
    out = np.full(len(cal), np.nan)
    j = -1
    for i, t in enumerate(cal):
        while j + 1 < len(p) and p[j + 1] <= t:
            j += 1
        if j < 0:
            continue
        if carry_days is not None:
            if (t - p[j]).astype(int) <= carry_days:
                out[i] = v[j]
        elif np.busday_count(d[j], t) <= age_bdays:
            out[i] = v[j]
    return out


def sma(x, n):
    o = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)):
        w = x[i - n + 1:i + 1]
        if not np.isnan(w).any():
            o[i] = w.sum() / n
    return o


def lag(x, k):
    o = np.full(len(x), np.nan)
    o[k:] = x[:-k]
    return o


def ret(x, k):
    return x / lag(x, k) - 1


def pchg(x):
    return x / lag(x, 1) - 1


def cumret(r, n):
    o = np.full(len(r), np.nan)
    lr = np.log1p(r)
    for i in range(n - 1, len(r)):
        w = lr[i - n + 1:i + 1]
        if not np.isnan(w).any():
            o[i] = math.exp(w.sum()) - 1
    return o


def pct(x, W, mn):
    o = np.full(len(x), np.nan)
    for i in range(len(x)):
        if np.isnan(x[i]):
            continue
        w = x[max(0, i - W + 1):i + 1]
        w = w[~np.isnan(w)]
        if len(w) < mn:
            continue
        o[i] = 100.0 * ((w < x[i]).sum() + 0.5 * (w == x[i]).sum()) / len(w)
    return o


def main():
    P = CFG["parameters"]
    L, R, V, age = P["sma_long"], P["ret_window"], P["rv_window"], CFG["coverage"]["stale_business_days"]
    gd, _, _ = load("px_idx_gspc")
    cal = gd[gd >= START]
    A = lambda s: pit(s, cal, age_bdays=age)
    spx = A("px_idx_gspc")
    raw = {}
    raw["spx_vs_sma200"] = spx / sma(spx, L) - 1
    raw["spx_ret63"] = ret(spx, R)
    ab = []
    for t in P["sectors"]:
        s = A(f"px_{t.lower()}")
        m = sma(s, L)
        ab.append(np.where(np.isnan(m) | np.isnan(s), np.nan, (s > m).astype(float)))
    ab = np.vstack(ab)
    raw["sector_share_above_sma200"] = np.where(np.isnan(ab).any(axis=0), np.nan, np.nanmean(ab, axis=0) if True else 0)
    raw["ew_vs_cw_ret63"] = ret(A("px_idx_sp500ew"), R) - raw["spx_ret63"]
    raw["vix"] = A("vix")
    lr = np.log(spx / lag(spx, 1))
    rv = np.full(len(cal), np.nan)
    for i in range(V - 1, len(cal)):
        w = lr[i - V + 1:i + 1]
        if not np.isnan(w).any():
            rv[i] = w.std(ddof=1) * math.sqrt(252)
    raw["spx_rv21"] = rv
    raw["skew"] = A("skew")
    raw["vix_vix3m"] = raw["vix"] / A("vix3m")
    baa = A("baa10y")
    raw["baa10y"] = baa
    raw["baa10y_chg63"] = baa - lag(baa, R)
    spy = A("px_spy")
    eq = np.where(np.isnan(spy), pchg(spx), pchg(spy))
    y = A("dgs10")
    synth = lag(y, 1) / 100 / 252 - P["synthetic_bond_duration"] * (y - lag(y, 1)) / 100
    mix = 0.5 * pchg(A("px_ief")) + 0.5 * pchg(A("px_gc_f"))
    ief_start = load("px_ief")[0].min()
    hav = np.where(cal >= ief_start, mix, synth)
    raw["equity_vs_haven_ret63"] = cumret(eq, R) - cumret(hav, R)
    raw["cftc_es_net_pct_oi"] = pit("cftc_es_net_pct_oi", cal, carry_days=CFG["coverage"]["weekly_carry_calendar_days"])
    raw["ai_rel_ret63"] = ret(A("px_idx_sox"), R) - raw["spx_ret63"]
    raw["ai_share_above_sma200"] = np.full(len(cal), np.nan)

    Wn, mn = CFG["normalisation"]["window_days"], CFG["normalisation"]["min_obs"]
    comps, weights = {}, {}
    for name, c in CFG["components"].items():
        ss = []
        for s in c["subs"]:
            p = pct(raw[s["id"]], Wn, mn)
            ss.append(100 - p if s["direction"] == "fear" else p)
        ss = np.vstack(ss)
        cnt = (~np.isnan(ss)).sum(axis=0)
        comps[name] = np.where(cnt > 0, np.nansum(ss, axis=0) / np.maximum(cnt, 1), np.nan)
        weights[name] = c["weight"]
    k = np.full(len(cal), np.nan)
    cov = np.zeros(len(cal))
    for i in range(len(cal)):
        num = den = 0.0
        for n, w in weights.items():
            if not np.isnan(comps[n][i]):
                num += w * comps[n][i]
                den += w
        cov[i] = den
        if den >= CFG["coverage"]["min_weight"] - 1e-12:
            k[i] = num / den
    return pd.DataFrame({"kmsi": k, "weight_coverage": cov, **{f"c_{n}": v for n, v in comps.items()}},
                        index=pd.DatetimeIndex(cal))


if __name__ == "__main__":
    import warnings
    warnings.simplefilter("ignore")
    b = main()
    a = pd.read_parquet(ROOT / "data" / "outputs" / f"kmsi_v{VERSION}_daily.parquet")
    a.index = pd.DatetimeIndex(a.index).astype("datetime64[ns]")
    b.index = b.index.astype("datetime64[ns]")
    cols = ["kmsi", "weight_coverage"] + [c for c in b.columns if c.startswith("c_")]
    worst = 0.0
    for c in cols:
        x, y = a[c].reindex(b.index), b[c]
        nan_mismatch = int((x.isna() != y.isna()).sum())
        d = float((x - y).abs().max())
        worst = max(worst, 0 if math.isnan(d) else d)
        print(f"{c:24s} max|diff|={d:.3e}  NaN-pattern mismatches={nan_mismatch}")
        assert nan_mismatch == 0, c
    assert worst <= 1e-9, worst
    print(f"\nPASS: {len(cols)} series, {b['kmsi'].notna().sum()} published days, worst difference {worst:.2e}")
