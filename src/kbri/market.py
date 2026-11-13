"""Month-end market panel for KBRI: prices, market cap, enterprise value, USD conversion.

Market cap = split-adjusted close(M) x cover-page shares(D) x cumulative split factor after D,
where D is the share-count date. Yahoo closes are adjusted for every split after M, so this
puts price and share count in the same units. ADRs use the ADR ratio. Fundamentals are taken
from the latest filing usable at M (filing date + 1 business day <= M). Foreign filers'
fundamentals are converted to USD at the period-end exchange rate.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay

from src.kbri.fundamentals import CFG, ROOT

STAGED = ROOT / "data" / "staged"
RAW = ROOT / "data" / "raw"


def splits(ticker: str) -> pd.Series:
    j = json.loads((RAW / "yahoo" / f"{ticker}.json").read_text())["chart"]["result"][0]
    ev = j.get("events", {}).get("splits", {})
    if not ev:
        return pd.Series(dtype=float)
    s = pd.Series({pd.to_datetime(v["date"], unit="s").normalize(): v["numerator"] / v["denominator"] for v in ev.values()})
    return s.sort_index()


def split_factor_after(sp: pd.Series, d: pd.Timestamp) -> float:
    return float(sp[sp.index > d].prod()) if len(sp) else 1.0


def fx_to_usd(ticker: str, dates: pd.Series) -> np.ndarray:
    f = CFG.get("foreign", {}).get(ticker, {})
    cur = f.get("currency", "USD")
    if cur == "USD":
        return np.ones(len(dates))
    s = pd.read_parquet(STAGED / f"{f['fx_series'].lower()}.parquet")["value"].dropna()
    r = s.reindex(pd.DatetimeIndex(dates), method="ffill").to_numpy()
    return 1 / r if f["fx_quote"] == "per_usd" else r


ALT_DEBT_TAGS = ["SeniorNotes", "ConvertibleNotesPayable", "ConvertibleNotesPayableCurrent", "ConvertibleDebtNoncurrent",
                 "ConvertibleDebtCurrent", "SecuredDebt", "UnsecuredDebt", "NotesPayable", "LongTermNotesPayable"]
_FACTS = {}


def alt_debt(ticker, period_end, filed) -> float:
    """Point-in-time sum of alternative debt tags at the period end (identical values counted once)."""
    if ticker not in _FACTS:
        f = pd.read_parquet(STAGED / "edgar" / f"facts_{ticker}.parquet")
        _FACTS[ticker] = f[f["concept"].isin(ALT_DEBT_TAGS) & f["start"].isna() & (f["unit"] == "USD")]
    f = _FACTS[ticker]
    g = f[(f["filed"] <= filed) & ((f["end"] - period_end).abs() <= pd.Timedelta(days=7))]
    if not len(g):
        return np.nan
    vals = g.sort_values("filed").groupby("concept")["val"].last()
    return float(pd.Series(vals.values).drop_duplicates().sum())


def debt(row) -> float:
    if not np.isnan(row["debt_total"]):
        d = row["debt_total"]
        d += 0 if np.isnan(row["short_term_borrowings"]) else row["short_term_borrowings"]
        return d
    parts = [row[c] for c in ("debt_noncurrent", "debt_current", "short_term_borrowings")]
    if not all(np.isnan(parts)):
        return np.nansum(parts)
    alt = alt_debt(row["ticker"], row["period_end"], row["filed"])
    if np.isfinite(alt):
        return alt
    # no debt tag at all: debt-free only if interest expense is immaterial, otherwise unknown (never a silent zero)
    return 0.0 if not (row["interest_expense_ttm"] > 5e6) else np.nan


def build(month_ends: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    P = pd.read_parquet(STAGED / "kbri_fundamentals_pit.parquet")
    P["usable"] = P["filed"] + BDay(CFG["fundamental_usable_lag_bdays"])
    if month_ends is None:
        month_ends = pd.date_range(CFG["sample_start"], "2026-10-31", freq="BME")
    from src.kbri.candidates import groups as _g
    groups = {t: g for t, g in _g().items() if t in set(P["ticker"])}
    out = []
    for t, grp in groups.items():
        pf = STAGED / f"px_{t.lower()}.parquet"
        if not pf.exists():
            continue
        px = pd.read_parquet(pf)["value"]
        sp = splits(t)
        f = P[P["ticker"] == t].sort_values("usable")
        if not len(f):
            continue
        adr = CFG.get("foreign", {}).get(t, {}).get("adr_ratio", 1)
        for M in month_ends:
            close = px.loc[:M]
            if not len(close) or (M - close.index[-1]).days > 7:
                continue
            fr = f[f["usable"] <= M]
            if not len(fr):
                continue
            r = fr.iloc[-1].copy()
            fx = fx_to_usd(t, pd.Series([r["period_end"]]))[0]
            sh, sd = r.get("shares_out_cover", np.nan), r.get("shares_out_date", pd.NaT)
            dsh = r.get("diluted_shares_ttm", np.nan)
            assets_usd = r["total_assets"] * fx
            plaus = lambda mc: np.isfinite(mc) and (not np.isfinite(assets_usd) or assets_usd <= 0 or 0.05 <= mc / assets_usd <= 100)
            mc_cover = close.iloc[-1] * sh / adr * split_factor_after(sp, sd) if pd.notna(sd) and sh > 0 else np.nan
            mc_dil = close.iloc[-1] * dsh / adr * split_factor_after(sp, r["period_end"]) if dsh > 0 else np.nan
            # both counts can be mis-scaled in XBRL; take cover unless implausible, then diluted, else none
            if plaus(mc_cover):
                mcap, sh_src = mc_cover, "cover"
            elif plaus(mc_dil):
                mcap, sh_src = mc_dil, "diluted_avg"
            elif np.isfinite(mc_cover) or np.isfinite(mc_dil):
                mcap, sh_src = np.nan, "rejected: implausible share counts"
            else:
                mcap, sh_src = np.nan, "missing share counts"
            out.append({"date": M, "ticker": t, "group": grp, "close": close.iloc[-1], "mcap_usd": mcap, "shares_source": sh_src,
                        "filed": r["filed"], "period_end": r["period_end"], "fx_to_usd": fx,
                        "fund_age_days": (M - r["period_end"]).days,
                        "debt_usd": debt(r) * fx, "cash_usd": (np.nan_to_num(r["cash"]) + np.nan_to_num(r["st_investments"])) * fx,
                        "revenue_ttm_usd": r["revenue_ttm"] * fx})
    D = pd.DataFrame(out)
    D["ev_usd"] = D["mcap_usd"] + D["debt_usd"] - D["cash_usd"]
    D.to_parquet(STAGED / "kbri_market_monthly.parquet")
    return D


if __name__ == "__main__":
    D = build()
    last = D[D["date"] == D["date"].max()].sort_values("mcap_usd", ascending=False)
    print(last[["ticker", "close", "mcap_usd", "ev_usd", "revenue_ttm_usd", "fund_age_days"]].assign(
        mcap_bn=lambda x: x.mcap_usd / 1e9, ev_bn=lambda x: x.ev_usd / 1e9, rev_bn=lambda x: x.revenue_ttm_usd / 1e9)[
        ["ticker", "close", "mcap_bn", "ev_bn", "rev_bn", "fund_age_days"]].round(1).to_string(index=False))
