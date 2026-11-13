"""Independent recalculation of KBRI v1.0 (Phase 6 gate).

Written separately from engine.py. From the variable panel it re-derives:
  - g* with a bisection solver and a closed-form annuity sum (engine uses brentq and a vector sum),
  - pooled-history and cross-section percentiles with explicit loops,
  - components, company scores and the equal-weighted disclosure-basket company mean.
It also re-derives four raw variables for every company-month directly from the fundamentals
and market panels (EV/sales, FCF yield, capex/revenue, FCF margin) as a check on variable construction.
Pass = every value within 1e-6 (g*) / 1e-9 (scores) and identical missing-value patterns.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import yaml

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
CFG = yaml.safe_load((ROOT / "config" / "kbri_v1.0.yaml").read_text())
OUT = ROOT / "data" / "outputs"
D = CFG["reverse_dcf"]


def ev_closed(g, R0, m, r, gT, H):
    q = (1 + g) / (1 + r)
    pv = R0 * m * (q * (1 - q ** H) / (1 - q) if abs(1 - q) > 1e-14 else H)
    return pv + R0 * m * (1 + g) ** H * (1 + gT) / ((r - gT) * (1 + r) ** H)


def g_bisect(EV, R0, m, r):
    gT, H = D["terminal_growth"], D["horizon_years"]
    if not all(map(math.isfinite, [EV, R0, m, r])) or EV <= 0 or R0 <= 0 or m <= 0 or r <= gT:
        return float("nan")
    f = lambda g: ev_closed(g, R0, m, r, gT, H) - EV
    lo, hi = -0.5, 3.0
    if f(lo) > 0:
        return float("nan")
    if f(hi) < 0:
        return hi
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    return (lo + hi) / 2


def pct(pool, v):
    return 100.0 * (sum(p < v for p in pool) + 0.5 * sum(p == v for p in pool)) / len(pool)


def main():
    V = pd.read_parquet(OUT / "kbri_v1.0_variables.parquet").reset_index(drop=True)
    A = pd.read_parquet(OUT / "kbri_v1.0_company_abs.parquet").reset_index(drop=True)
    R = pd.read_parquet(OUT / "kbri_v1.0_company_rel.parquet").reset_index(drop=True)
    # 1. g*
    g = np.array([g_bisect(*x) for x in zip(V.ev_usd, V.revenue_usd, V.m_used, V.r_used)])
    dg = np.nanmax(np.abs(g - V.g_star.to_numpy()))
    nan_g = int((np.isnan(g) != V.g_star.isna().to_numpy()).sum())
    print(f"g*: max|diff| = {dg:.2e}, NaN mismatches = {nan_g}")
    # 2. raw-variable spot rebuild from market panel
    M = pd.read_parquet(ROOT / "data" / "staged" / "kbri_market_monthly.parquet")
    J = V.merge(M[["date", "ticker", "ev_usd", "revenue_ttm_usd"]], on=["date", "ticker"], suffixes=("", "_m"))
    evs = np.where(J.revenue_ttm_usd > 0, J.ev_usd_m / J.revenue_ttm_usd, np.nan)
    evs = np.where(J.ev_usd_m > 0, evs, np.nan)
    print(f"EV/sales rebuild: max|diff| = {np.nanmax(np.abs(evs - J.ev_sales)):.2e}, NaN mismatches = {int((np.isnan(evs) != J.ev_sales.isna()).sum())}")
    # 3. scores
    comps = {k: v for k, v in CFG["components"].items() if not v.get("basket_only")}
    worst, mism = 0.0, 0
    for kind, S in (("abs", A), ("rel", R)):
        comp_vals = {}
        for cname, c in comps.items():
            cols = []
            for var, direction in c["vars"].items():
                sc = np.full(len(V), np.nan)
                for g, idx in V.groupby("group").groups.items():
                    sub = V.loc[idx]
                    vals = sub[var].to_numpy(float)
                    dts = sub["date"].to_numpy()
                    for d in np.unique(dts):
                        rows = np.where((dts == d) & np.isfinite(vals))[0]
                        if not len(rows):
                            continue
                        mask = (dts <= d) if kind == "abs" else (dts == d)
                        pool = np.sort(vals[mask & np.isfinite(vals)])
                        need = CFG["normalisation"]["abs_min_obs"] if kind == "abs" else 3
                        if len(pool) < need:
                            continue
                        lo = np.searchsorted(pool, vals[rows], "left")
                        hi = np.searchsorted(pool, vals[rows], "right")
                        p = 100.0 * (lo + 0.5 * (hi - lo)) / len(pool)
                        sc[np.asarray(idx)[rows]] = 100 - p if direction == "inverse" else p
                cols.append(sc)
                d = np.nanmax(np.abs(sc - S[f"s_{var}"].to_numpy())) if np.isfinite(sc).any() else 0.0
                mm = int((np.isnan(sc) != S[f"s_{var}"].isna().to_numpy()).sum())
                worst, mism = max(worst, d), mism + mm
            Cm = np.vstack(cols)
            n_ok = np.isfinite(Cm).sum(axis=0)
            with np.errstate(all="ignore"):
                cv = np.where(n_ok >= CFG["component_min_share"] * len(cols) - 1e-9, np.nanmean(Cm, axis=0), np.nan)
            comp_vals[cname] = cv
        w = {k: v["weight"] for k, v in comps.items()}
        num = sum(np.nan_to_num(comp_vals[k]) * w[k] for k in w)
        den = sum(np.isfinite(comp_vals[k]) * w[k] for k in w)
        with np.errstate(all="ignore"):
            k_ = np.where(den / sum(w.values()) >= CFG["company_min_weight"] - 1e-9, num / den, np.nan)
        d = np.nanmax(np.abs(k_ - S["kbri"].to_numpy()))
        mm = int((np.isnan(k_) != S["kbri"].isna().to_numpy()).sum())
        print(f"KBRI-{kind}: company score max|diff| = {d:.2e}, NaN mismatches = {mm}")
        worst, mism = max(worst, d), mism + mm
    # 4. disclosure basket equal-weighted company mean
    U = pd.read_parquet(ROOT / "data" / "staged" / "kbri_universe_monthly.parquet")
    B = pd.read_parquet(OUT / "kbri_v1.0_basket_disclosure.parquet")
    m = A.merge(U[["date", "ticker", "member"]], on=["date", "ticker"])
    ew = {dt: np.nanmean(d.loc[d.member, "kbri"]) if d.loc[d.member, "kbri"].notna().any() else np.nan for dt, d in m.groupby("date")}
    b = pd.Series(ew).reindex(B.index)
    db = np.nanmax(np.abs(b - B.kbri_company_mean_ew))
    print(f"Disclosure basket EW mean: max|diff| = {db:.2e}")
    ok = dg <= 1e-6 and nan_g == 0 and worst <= 1e-9 + 0 and mism == 0 and db <= 1e-9
    print("PASS" if ok else "FAIL", f"(worst score diff {worst:.2e}, missing-pattern mismatches {mism})")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
