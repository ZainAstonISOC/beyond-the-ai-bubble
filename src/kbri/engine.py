"""KBRI v1.0 calculation engine.

Month-end panel, January 2010 onwards, for every candidate company.
  1. Variables from the latest usable filing (filing date + 1 business day <= M) and prices to M.
  2. Market-implied 10-year revenue growth g* by reverse DCF.
  3. KBRI-abs: percentile of each variable against the pooled history of all candidate
     firm-months in the same business-model group, 2010..M (min 40 observations).
     KBRI-rel: percentile against the group's candidates on date M (min 3 firms).
  4. Components need >= 2/3 of their defined variables; company score needs >= 75% of the
     company-level weight (concentration excluded and the other 90% rescaled).
  5. Basket score = 0.9 x equal-weighted mean of members' KBRI-abs + 0.1 x concentration score,
     for the primary (disclosure) basket and the secondary (value-chain) basket.

Documented substitutions in v1.0 (see change log):
  - debt_due24m_to_cash uses current debt (due within 12 months) / cash, because maturity
    ladders are in untagged notes; flagged as a proxy.
  - top_customer_share is not yet extracted (needs reviewed extraction from notes); missing.
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay
from scipy.optimize import brentq

from src.kbri.fundamentals import CFG, ROOT

warnings.simplefilter("ignore")
STAGED = ROOT / "data" / "staged"
OUT = ROOT / "data" / "outputs"
DCF = CFG["reverse_dcf"]


# ------------------------------------------------------------------ helpers
def px(t):
    return pd.read_parquet(STAGED / f"px_{t.lower().replace('^', 'idx_')}.parquet")["value"]


def asof_value(sid, M, lag_bdays=1):
    s = pd.read_parquet(STAGED / f"{sid}.parquet")
    s = s[s["published"] <= M]["value"].dropna()
    return float(s.iloc[-1]) if len(s) else np.nan


def ev_from_g(g, R0, m, r, gT=None, H=None):
    gT = DCF["terminal_growth"] if gT is None else gT
    H = DCF["horizon_years"] if H is None else H
    k = np.arange(1, H + 1)
    pv = (R0 * (1 + g) ** k * m / (1 + r) ** k).sum()
    tv = R0 * (1 + g) ** H * (1 + gT) * m / ((r - gT) * (1 + r) ** H)
    return pv + tv


def solve_g(EV, R0, m, r, gT=None):
    if not all(np.isfinite([EV, R0, m, r])) or EV <= 0 or R0 <= 0 or m <= 0 or r <= (gT or DCF["terminal_growth"]):
        return np.nan
    f = lambda g: ev_from_g(g, R0, m, r, gT) - EV
    lo, hi = -0.5, 3.0
    if f(lo) > 0 or f(hi) < 0:
        return np.nan if f(lo) > 0 else hi        # implied growth above 300% a year is capped
    return brentq(f, lo, hi, xtol=1e-10)


def safe_div(a, b, positive_den=True):
    if not np.isfinite(a) or not np.isfinite(b) or b == 0 or (positive_den and b <= 0):
        return np.nan
    return a / b


# ------------------------------------------------------------------ step 1-2: variables
def build_variables() -> pd.DataFrame:
    P = pd.read_parquet(STAGED / "kbri_fundamentals_pit.parquet")
    P["usable"] = P["filed"] + BDay(CFG["fundamental_usable_lag_bdays"])
    D = pd.read_parquet(STAGED / "kbri_market_monthly.parquet")
    spx = px("^GSPC")
    spx_m = spx.resample("BME").last()
    rows = []
    # best 3-year average FCF margin per company, point in time
    for t, d in D.groupby("ticker"):
        f = P[P["ticker"] == t].sort_values("usable").copy()
        f["fcf_margin"] = (f["cfo_ttm"] - f["capex_ttm"]) / f["revenue_ttm"]
        close = px(t)
        lr = np.log(close).diff()
        cm = close.resample("BME").last()
        for r in d.itertuples():
            M = r.date
            fr = f[f["usable"] <= M]
            if not len(fr):
                continue
            x = fr.iloc[-1].copy()
            fx = r.fx_to_usd
            if np.isfinite(x["gross_profit_ttm"]) and np.isfinite(x["revenue_ttm"]) and x["gross_profit_ttm"] > x["revenue_ttm"] * 1.0001:
                x["revenue_ttm"] = x["gross_profit_ttm"] = np.nan      # identity break: reject both
            # point-in-time best 3-year average FCF margin since 2010
            hist = fr[fr["period_end"] >= "2010-01-01"][["period_end", "fcf_margin"]].dropna()
            m3 = [hist[(hist.period_end > e - pd.DateOffset(years=3)) & (hist.period_end <= e)]["fcf_margin"].mean()
                  for e in hist["period_end"]]
            best_m = np.nanmax(m3) if len(m3) else np.nan
            # beta from 60 monthly returns
            rr = pd.concat([cm.pct_change(), spx_m.pct_change()], axis=1).loc[:M].dropna().iloc[-DCF["beta_months"]:]
            beta = np.cov(rr.iloc[:, 0], rr.iloc[:, 1])[0, 1] / rr.iloc[:, 1].var() if len(rr) >= 36 else 1.0
            beta = float(np.clip(beta, *DCF["beta_cap"]))
            rf = asof_value("dgs10", M) / 100
            rev = x["revenue_ttm"] * fx
            cfo, capex, ni = x["cfo_ttm"] * fx, x["capex_ttm"] * fx, x["net_income_ttm"] * fx
            fcf = cfo - capex
            ebit = x["operating_income_ttm"]
            if not np.isfinite(ebit) and np.isfinite(x["pretax_income_ttm"]):
                ebit = x["pretax_income_ttm"] + np.nan_to_num(x["interest_expense_ttm"])
            ebit = ebit * fx
            ebit3 = x["operating_income_ttm_3y"] * fx
            debt, cash = r.debt_usd, r.cash_usd
            ic = np.nansum([x["equity"] * fx, debt]) - cash if np.isfinite(x["equity"]) else np.nan
            ic3 = (x["equity_3y"] + np.nansum([x["debt_total_3y"], 0]) - np.nan_to_num(x["cash_3y"])) * fx \
                if np.isfinite(x.get("equity_3y", np.nan)) else np.nan
            lease = np.nansum([x["op_lease_liab"], x["fin_lease_liab"]]) if np.isfinite(x["op_lease_liab"]) or np.isfinite(x["fin_lease_liab"]) \
                else (np.nansum([x["op_lease_liab_noncurrent"], x["op_lease_liab_current"]]) if np.isfinite(x["op_lease_liab_noncurrent"]) else np.nan)
            dna = x["dna_ttm"] * fx
            interest = x["interest_expense_ttm"] * fx
            c = close.loc[:M]
            l = lr.loc[:M]
            sma = c.iloc[-200:].mean() if len(c) >= 200 else np.nan
            rv63 = l.iloc[-63:].std() * np.sqrt(252) if l.iloc[-63:].notna().sum() >= 60 else np.nan
            sd252 = l.iloc[-252:].std()
            tail = (l.iloc[-63:].abs() > 3 * sd252).mean() if len(l) >= 252 else np.nan
            rev_cagr3 = (x["revenue_ttm"] / x["revenue_ttm_3y"]) ** (1 / 3) - 1 if x["revenue_ttm_3y"] and x["revenue_ttm_3y"] > 0 and x["revenue_ttm"] > 0 else np.nan
            row = {
                "date": M, "ticker": t, "group": r.group, "mcap_usd": r.mcap_usd, "ev_usd": r.ev_usd,
                "revenue_usd": rev, "fcf_usd": fcf, "best_fcf_margin": best_m, "beta": beta, "rf": rf,
                "ev_sales": safe_div(r.ev_usd, rev),
                "fcf_yield": safe_div(fcf, r.mcap_usd),
                "rev_cagr3": rev_cagr3,
                "cfo_to_ni": safe_div(cfo, ni),
                "fcf_margin": safe_div(fcf, rev),
                "sloan_accruals": safe_div(ni - cfo, np.nanmean([x["total_assets"], x["total_assets_1y"]]) * fx),
                "gm_std8": x["gm_std8"],
                "top_customer_share": np.nan,
                "capex_to_rev": safe_div(capex, rev),
                "capex_to_cfo": safe_div(capex, cfo),
                "capex_growth_minus_rev_growth": (safe_div(x["capex_ttm"], x["capex_ttm_1y"]) - safe_div(x["revenue_ttm"], x["revenue_ttm_1y"])),
                "incr_roic3": safe_div(ebit * (1 - 0.21) - ebit3 * (1 - 0.21), ic - ic3),
                "net_debt_to_ebitda": safe_div(debt - cash, ebit + np.nan_to_num(dna)),
                "interest_cover": min(safe_div(ebit, interest), 100.0) if np.isfinite(interest) and interest > 0 else (100.0 if debt <= 0.05 * max(r.mcap_usd, 1) else np.nan),
                "leases_to_assets": safe_div(lease, x["total_assets"]),
                "share_growth": safe_div(x["diluted_shares_ttm"], x["diluted_shares_ttm_1y"]) - 1,
                "debt_due24m_to_cash": safe_div(np.nansum([x["debt_current"], x["short_term_borrowings"]]) * fx, cash) if np.isfinite(cash) else np.nan,
                "px_vs_sma200": c.iloc[-1] / sma - 1 if np.isfinite(sma) else np.nan,
                "rv63": rv63,
                "net_equity_issuance_to_mcap": safe_div((np.nan_to_num(x["equity_issued_ttm"]) - np.nan_to_num(x["equity_repurchased_ttm"])) * fx, r.mcap_usd),
                "tail_day_share63": tail,
            }
            rows.append(row)
    V = pd.DataFrame(rows)
    # steady-state margin: own best 3-year margin, else group median of positive margins at M
    gm = V[V["best_fcf_margin"] > 0].groupby(["date", "group"])["best_fcf_margin"].median().rename("grp_margin")
    V = V.join(gm, on=["date", "group"])
    V["m_used"] = np.where(V["best_fcf_margin"] > 0, V["best_fcf_margin"], V["grp_margin"])
    V["r_used"] = V["rf"] + V["beta"] * DCF["erp"]
    V["g_star"] = [solve_g(e, R, m, r) for e, R, m, r in zip(V["ev_usd"], V["revenue_usd"], V["m_used"], V["r_used"])]
    V["g_star_minus_rev_cagr3"] = V["g_star"] - V["rev_cagr3"]
    return V


# ------------------------------------------------------------------ step 3: normalisation
def _direct_pct(pool, v):
    """Direct comparison (rows x pool broadcast): share below plus half of ties."""
    return 100 * ((pool[None, :] < v[:, None]).sum(1) + 0.5 * (pool[None, :] == v[:, None]).sum(1)) / len(pool)


def pooled_percentile(V: pd.DataFrame, var: str, min_obs: int) -> pd.Series:
    out = pd.Series(np.nan, index=V.index)
    for g, d in V.groupby("group"):
        vals, dates = d[var].to_numpy(float), d["date"].to_numpy()
        for dt in np.unique(dates):
            rows = (dates == dt) & np.isfinite(vals)
            if not rows.any():
                continue
            pool = vals[(dates <= dt) & np.isfinite(vals)]
            if len(pool) < min_obs:
                continue
            out.loc[d.index[rows]] = _direct_pct(pool, vals[rows])
    return out


def cross_percentile(V: pd.DataFrame, var: str, min_n: int = 3) -> pd.Series:
    out = pd.Series(np.nan, index=V.index)
    for (dt, g), d in V.groupby(["date", "group"]):
        vals = d[var].to_numpy(float)
        ok = np.isfinite(vals)
        if ok.sum() < min_n:
            continue
        out.loc[d.index[ok]] = _direct_pct(vals[ok], vals[ok])
    return out


def score(V: pd.DataFrame, kind: str = "abs") -> pd.DataFrame:
    S = V[["date", "ticker", "group"]].copy()
    comp_cfg = {k: v for k, v in CFG["components"].items() if not v.get("basket_only")}
    for cname, c in comp_cfg.items():
        cols = []
        for var, direction in c["vars"].items():
            p = pooled_percentile(V, var, CFG["normalisation"]["abs_min_obs"]) if kind == "abs" else cross_percentile(V, var)
            S[f"s_{var}"] = 100 - p if direction == "inverse" else p
            cols.append(f"s_{var}")
        n_ok = S[cols].notna().sum(axis=1)
        S[f"c_{cname}"] = S[cols].mean(axis=1).where(n_ok >= CFG["component_min_share"] * len(cols) - 1e-9)
    w = pd.Series({k: v["weight"] for k, v in comp_cfg.items()})
    C = S[[f"c_{k}" for k in w.index]]
    C.columns = w.index
    avail = C.notna().mul(w, axis=1).sum(axis=1)
    S["weight_coverage"] = avail / w.sum()
    S["kbri"] = (C.fillna(0).mul(w, axis=1).sum(axis=1) / avail.where(avail > 0)).where(S["weight_coverage"] >= CFG["company_min_weight"] - 1e-9)
    return S


# ------------------------------------------------------------------ step 5: baskets
def concentration(V: pd.DataFrame, members: pd.DataFrame, col: str) -> pd.DataFrame:
    rows = []
    rets = {t: px(t).resample("BME").last().pct_change(3) for t in V["ticker"].unique()}   # ~63 trading days
    for M, d in members[members[col]].groupby("date"):
        m = V[(V["date"] == M) & V["ticker"].isin(d["ticker"])].dropna(subset=["mcap_usd"])
        if len(m) < 3:
            continue
        w = m["mcap_usd"] / m["mcap_usd"].sum()
        top = w.sort_values(ascending=False).index[:5]
        r63 = np.array([rets[t].get(M, np.nan) for t in m["ticker"]])
        contrib = w.to_numpy() * r63
        tot_abs = np.nansum(np.abs(contrib))
        n = len(m)
        k = min(5, n) / n                                   # top-5 share under equal weights
        t5 = w.loc[top].sum()
        t5r = np.nansum(np.abs(contrib[[list(w.index).index(i) for i in top]])) / tot_abs if tot_abs > 0 else np.nan
        hhi = (w ** 2).sum()
        rows.append({"date": M, "n": n, "top5_mcap_share_raw": t5, "herfindahl_raw": hhi, "top5_ret63_share_raw": t5r,
                     # size-neutral: excess over an equal-weighted basket of the same size (basket grows 6 -> 25 members)
                     "top5_mcap_share": (t5 - k) / (1 - k) if k < 1 else np.nan,
                     "herfindahl": (hhi - 1 / n) / (1 - 1 / n),
                     "top5_ret63_share": (t5r - k) / (1 - k) if k < 1 and np.isfinite(t5r) else np.nan})
    Cn = pd.DataFrame(rows).set_index("date").sort_index()
    for v in ("top5_mcap_share", "herfindahl", "top5_ret63_share"):
        x = Cn[v]
        Cn[f"p_{v}"] = [100 * ((x.iloc[:i + 1] < x.iloc[i]).sum() + 0.5 * (x.iloc[:i + 1] == x.iloc[i]).sum()) / (i + 1)
                        if i + 1 >= 24 else np.nan for i in range(len(x))]
    Cn["r_conc"] = Cn[[c for c in Cn if c.startswith("p_")]].mean(axis=1)
    return Cn


def basket(S: pd.DataFrame, V: pd.DataFrame, U: pd.DataFrame, col: str) -> pd.DataFrame:
    Cn = concentration(V, U, col)
    m = S.merge(U[["date", "ticker", col]], on=["date", "ticker"])
    m = m[m[col]].merge(V[["date", "ticker", "mcap_usd"]], on=["date", "ticker"])
    g = m.groupby("date")
    B = pd.DataFrame({
        "n_members": g["ticker"].nunique(),
        "n_scored": g["kbri"].count(),
        "kbri_company_mean_ew": g["kbri"].mean(),
        "kbri_company_mean_cw": g.apply(lambda d: np.average(d["kbri"].dropna(), weights=d.loc[d["kbri"].notna(), "mcap_usd"]) if d["kbri"].notna().any() else np.nan),
    })
    B = B.join(Cn[["r_conc", "top5_mcap_share", "herfindahl", "top5_ret63_share", "top5_mcap_share_raw", "herfindahl_raw"]])
    conc = CFG["components"]["concentration"]["weight"]
    B["kbri_basket"] = np.where(B["r_conc"].notna(), (1 - conc) * B["kbri_company_mean_ew"] + conc * B["r_conc"], B["kbri_company_mean_ew"])
    B["kbri_basket_cw"] = np.where(B["r_conc"].notna(), (1 - conc) * B["kbri_company_mean_cw"] + conc * B["r_conc"], B["kbri_company_mean_cw"])
    B["concentration_included"] = B["r_conc"].notna()
    return B


def run():
    V = build_variables()
    V.to_parquet(OUT / "kbri_v1.0_variables.parquet")
    S_abs, S_rel = score(V, "abs"), score(V, "rel")
    S_abs.to_parquet(OUT / "kbri_v1.0_company_abs.parquet")
    S_rel.to_parquet(OUT / "kbri_v1.0_company_rel.parquet")
    U = pd.read_parquet(STAGED / "kbri_universe_monthly.parquet")
    B1, B2 = basket(S_abs, V, U, "member"), basket(S_abs, V, U, "member_value_chain")
    B1.to_parquet(OUT / "kbri_v1.0_basket_disclosure.parquet")
    B2.to_parquet(OUT / "kbri_v1.0_basket_value_chain.parquet")
    meta = {"model_version": "1.0", "calculation_utc": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
            "data_cutoff": str(V["date"].max().date()), "baskets": {"primary": "registered disclosure basket",
            "secondary": "AI value-chain basket (logged deviation, 13 Nov 2026)"},
            "substitutions": ["debt_due24m_to_cash proxied by current debt / cash", "top_customer_share not yet extracted"],
            "reverse_dcf": DCF}
    (OUT / "kbri_v1.0_release.json").write_text(json.dumps(meta, indent=1, default=str))
    return V, S_abs, S_rel, B1, B2


if __name__ == "__main__":
    V, Sa, Sr, B1, B2 = run()
    last = V["date"].max()
    print(Sa[Sa.date == last].merge(V[["date", "ticker", "g_star", "ev_sales"]], on=["date", "ticker"])[
        ["ticker", "group", "kbri", "weight_coverage", "c_valuation", "c_quality", "c_capex", "c_financing", "c_speculative", "g_star", "ev_sales"]
    ].sort_values("kbri", ascending=False).round(2).to_string(index=False))
    print("\nDisclosure basket:\n", B1[["n_members", "n_scored", "kbri_basket", "kbri_basket_cw"]].dropna().iloc[::6].tail(12).round(1))
    print("\nValue-chain basket:\n", B2[["n_members", "n_scored", "kbri_basket", "kbri_basket_cw", "r_conc"]].iloc[::12].round(1).to_string())
