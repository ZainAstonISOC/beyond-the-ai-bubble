"""KMSI v1.0 calculation engine (pandas implementation).

Pipeline
  1. Point-in-time alignment: on trading day t each series takes its latest
     observation with published <= t; values older than the staleness rule
     are treated as missing.
  2. Sub-indicators built from aligned values only.
  3. Rolling empirical percentile (window 1,260 trading days incl. t, min 504
     valid observations, ties at half weight); fear series inverted.
  4. Component = mean of available sub-indicator scores.
  5. KMSI = weight-normalised mean of available components, published only if
     available weight >= 0.75.

Provisional element: the AI-momentum component uses the PHLX Semiconductor
index (^SOX) relative to the S&P 500 as the analogue for the whole history
until the KBRI universe is fixed in Phase 5, after which the AI basket
replaces it from 2023 onwards.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from numpy.lib.stride_tricks import sliding_window_view
from pandas.tseries.offsets import BDay
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[2]
STAGED = ROOT / "data" / "staged"
OUT = ROOT / "data" / "outputs"
CFG_PATH = ROOT / "config" / "kmsi_v1.0.yaml"
CALENDAR_START = "1986-01-02"


def load_cfg() -> tuple[dict, str]:
    raw = CFG_PATH.read_bytes()
    return yaml.safe_load(raw), hashlib.sha256(raw).hexdigest()[:12]


def staged(sid: str) -> pd.DataFrame:
    return pd.read_parquet(STAGED / f"{sid}.parquet")


# ------------------------------------------------------------------ step 1
def calendar(cutoff: str | None = None) -> pd.DatetimeIndex:
    cal = staged("px_idx_gspc").index
    cal = cal[cal >= CALENDAR_START]
    if cutoff:
        cal = cal[cal <= cutoff]
    return cal


def align(sid: str, cal: pd.DatetimeIndex, max_age_bdays: int | None = 3,
          max_carry_days: int | None = None) -> pd.Series:
    """Latest value with published <= t; NaN if stale."""
    df = staged(sid).dropna(subset=["value"]).reset_index()
    df["date"] = df["date"].astype("datetime64[ns]")
    df["t"] = df["published"].astype("datetime64[ns]")
    df = df.sort_values(["t", "date"])
    left = pd.DataFrame({"t": pd.DatetimeIndex(cal).astype("datetime64[ns]")})
    m = pd.merge_asof(left, df[["t", "date", "published", "value"]], on="t", direction="backward")
    m.index = cal
    ok = m["value"].notna()
    if max_carry_days is not None:
        # weekly series: usable for max_carry_days after its release (published) date
        carry = (m["t"] - m["published"].astype("datetime64[ns]")).dt.days
        ok &= carry.le(max_carry_days).fillna(False)
    elif max_age_bdays is not None:
        d = m["date"].where(ok, m["t"]).values.astype("datetime64[D]")
        age = np.busday_count(d, m["t"].values.astype("datetime64[D]"))
        ok &= pd.Series(age, index=cal) <= max_age_bdays
    return m["value"].where(ok)


# ------------------------------------------------------------------ step 2
def sub_indicators(cal: pd.DatetimeIndex, cfg: dict) -> pd.DataFrame:
    p = cfg["parameters"]
    L, R, V = p["sma_long"], p["ret_window"], p["rv_window"]
    stale = cfg["coverage"]["stale_business_days"]
    a = lambda sid: align(sid, cal, max_age_bdays=stale)

    spx = a("px_idx_gspc")
    out = pd.DataFrame(index=cal)
    out["spx_vs_sma200"] = spx / spx.rolling(L, min_periods=L).mean() - 1
    out["spx_ret63"] = spx / spx.shift(R) - 1

    above = []
    for tkr in p["sectors"]:
        s = a(f"px_{tkr.lower()}")
        above.append((s > s.rolling(L, min_periods=L).mean()).where(s.rolling(L, min_periods=L).mean().notna()))
    ab = pd.concat(above, axis=1)
    out["sector_share_above_sma200"] = ab.mean(axis=1).where(ab.notna().all(axis=1))

    ew = a("px_idx_sp500ew")
    out["ew_vs_cw_ret63"] = (ew / ew.shift(R) - 1) - out["spx_ret63"]

    out["vix"] = a("vix")
    lr = np.log(spx).diff()
    out["spx_rv21"] = lr.rolling(V, min_periods=V).std() * np.sqrt(252)

    out["skew"] = a("skew")
    out["vix_vix3m"] = out["vix"] / a("vix3m")

    baa = a("baa10y")
    out["baa10y"] = baa
    out["baa10y_chg63"] = baa - baa.shift(R)

    # safe haven: equity total return minus haven return over 63 days
    spy = a("px_spy")
    eq_r = spy.pct_change(fill_method=None)
    eq_r = eq_r.where(spy.notna(), spx.pct_change(fill_method=None))    # pre-1993: S&P 500 price return
    ief, gold = a("px_ief"), a("px_gc_f")
    y = a("dgs10")
    synth = (y.shift(1) / 100 / 252) - p["synthetic_bond_duration"] * (y - y.shift(1)) / 100
    mix = 0.5 * ief.pct_change(fill_method=None) + 0.5 * gold.pct_change(fill_method=None)
    haven_r = mix.where(cal >= staged("px_ief").index.min(), synth)
    cum = lambda r: np.exp(np.log1p(r).rolling(R, min_periods=R).sum()) - 1
    out["equity_vs_haven_ret63"] = cum(eq_r) - cum(haven_r)

    out["cftc_es_net_pct_oi"] = align("cftc_es_net_pct_oi", cal, max_carry_days=cfg["coverage"]["weekly_carry_calendar_days"])

    sox = a("px_idx_sox")
    out["ai_rel_ret63"] = (sox / sox.shift(R) - 1) - out["spx_ret63"]
    out["ai_share_above_sma200"] = np.nan   # filled once the AI basket is fixed (Phase 5)
    return out


# ------------------------------------------------------------------ step 3
def rolling_percentile(x: pd.Series, window: int, min_obs: int) -> pd.Series:
    v = x.to_numpy(dtype=float)
    n = len(v)
    pad = np.concatenate([np.full(window - 1, np.nan), v])
    W = sliding_window_view(pad, window)                    # row t = values t-window+1 .. t
    cur = v[:, None]
    valid = ~np.isnan(W)
    cnt = valid.sum(axis=1)
    less = (W < cur).sum(axis=1)
    eq = (W == cur).sum(axis=1)
    pct = 100.0 * (less + 0.5 * eq) / np.where(cnt > 0, cnt, 1)
    pct[(cnt < min_obs) | np.isnan(v)] = np.nan
    return pd.Series(pct, index=x.index)


def rolling_robust_z(x: pd.Series, window: int, min_obs: int) -> pd.Series:
    v = x.to_numpy(dtype=float)
    pad = np.concatenate([np.full(window - 1, np.nan), v])
    W = sliding_window_view(pad, window)
    with np.errstate(all="ignore"), __import__("warnings").catch_warnings():
        __import__("warnings").simplefilter("ignore", RuntimeWarning)
        m = np.nanmedian(W, axis=1)
        madv = np.nanmedian(np.abs(W - m[:, None]), axis=1)
    cnt = (~np.isnan(W)).sum(axis=1)
    z = (v - m) / (1.4826 * np.where(madv > 0, madv, np.nan))
    z[(cnt < min_obs) | np.isnan(v)] = np.nan
    return pd.Series(100 * norm.cdf(z), index=x.index)


# ------------------------------------------------------------------ steps 4-5
def aggregate(sub_scores: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    comps = pd.DataFrame(index=sub_scores.index)
    w = {}
    for name, c in cfg["components"].items():
        ids = [s["id"] for s in c["subs"]]
        comps[name] = sub_scores[ids].mean(axis=1, skipna=True)
        w[name] = c["weight"]
    wv = pd.Series(w)
    avail = comps.notna()
    wsum = avail.mul(wv, axis=1).sum(axis=1)
    kmsi = comps.fillna(0).mul(wv, axis=1).sum(axis=1) / wsum.where(wsum > 0)
    kmsi = kmsi.where(wsum >= cfg["coverage"]["min_weight"] - 1e-12)
    return comps, kmsi, wsum


def score(raw: pd.DataFrame, cfg: dict, transform: str = "percentile") -> pd.DataFrame:
    n = cfg["normalisation"]
    scores = pd.DataFrame(index=raw.index)
    for c in cfg["components"].values():
        for s in c["subs"]:
            f = rolling_percentile if transform == "percentile" else rolling_robust_z
            p = f(raw[s["id"]], n["window_days"], n["min_obs"])
            scores[s["id"]] = 100 - p if s["direction"] == "fear" else p
    return scores


def regime(x: float, cfg: dict) -> str | None:
    if np.isnan(x):
        return None
    r = int(round(x))
    for lo, hi, lab in cfg["regimes"]:
        if lo <= r <= hi:
            return lab
    return None


def run(cutoff: str | None = None, cfg: dict | None = None, write: bool = True) -> dict:
    base_cfg, h = load_cfg()
    cfg = cfg or base_cfg
    cal = calendar(cutoff)
    raw = sub_indicators(cal, cfg)
    sub = score(raw, cfg)
    comps, kmsi, wsum = aggregate(sub, cfg)
    sub_z = score(raw, cfg, "robust_z")
    _, kmsi_z, _ = aggregate(sub_z, cfg)
    res = pd.DataFrame({"kmsi": kmsi, "weight_coverage": wsum})
    res = res.join(comps.add_prefix("c_"))
    for k in (5, 20, 60):
        res[f"kmsi_avg{k}"] = kmsi.rolling(k, min_periods=k).mean()
        res[f"kmsi_chg{k}"] = kmsi - kmsi.shift(k)
    res["kmsi_hist_pct"] = kmsi.expanding().rank(pct=True) * 100
    res["regime"] = [regime(x, cfg) for x in kmsi]
    res["kmsi_robust_z"] = kmsi_z
    res["missing_components"] = comps.isna().apply(lambda r: ",".join(r.index[r]), axis=1)
    res["model_version"] = cfg["version"]
    res["config_sha"] = h
    out = {"raw": raw, "sub": sub, "components": comps, "result": res}
    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        res.to_parquet(OUT / "kmsi_v1.0_daily.parquet")
        res.drop(columns=[]).to_csv(OUT / "kmsi_v1.0_daily.csv", float_format="%.6f")
        raw.to_parquet(OUT / "kmsi_v1.0_raw_subindicators.parquet")
        sub.to_parquet(OUT / "kmsi_v1.0_sub_scores.parquet")
        last = res["kmsi"].last_valid_index()
        meta = {
            "model_version": cfg["version"], "config_sha": h,
            "calculation_utc": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
            "data_cutoff": str(last.date()) if last is not None else None,
            "first_published": str(res["kmsi"].first_valid_index().date()),
            "universe": "AI momentum uses ^SOX analogue (provisional until Phase 5)",
            "transform": cfg["normalisation"],
            "weights": {k: v["weight"] for k, v in cfg["components"].items()},
            "source_manifest": "data/raw/manifest.json",
        }
        (OUT / "kmsi_v1.0_release.json").write_text(json.dumps(meta, indent=1))
    return out


if __name__ == "__main__":
    o = run()
    r = o["result"]
    print(r[["kmsi", "weight_coverage", "regime"]].dropna().tail(10))
    print("first published:", r["kmsi"].first_valid_index())
