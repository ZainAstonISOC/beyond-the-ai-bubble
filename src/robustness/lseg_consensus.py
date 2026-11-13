"""Exploratory (not registered): price-implied growth (g*) against I/B/E/S consensus growth.

Inputs: KBRI v1.0 variables (public pipeline) and LSEG I/B/E/S monthly consensus pulled via the LSEG
Data Library in Workspace CodeBook on 13 Nov 2026 (data/licensed/lseg/, not redistributed).
Outputs: data/outputs/robustness_lseg_consensus_summary.json and a basket-level monthly CSV of medians
(derived statistics only, no vendor values at firm level).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.kmsi import engine as E

ROOT = E.ROOT
LIC = ROOT / "data" / "licensed" / "lseg"
OUT = ROOT / "data" / "outputs"


def consensus_panel() -> pd.DataFrame:
    c = pd.read_csv(LIC / "lseg_rev_consensus_monthly.csv")
    c = c.rename(columns={"Calc Date": "date", "Revenue - Mean": "rev", "Financial Period Absolute": "fp",
                          "Revenue - Number of Included Estimates": "n_est"})
    c["ticker"] = c["Instrument"].str.split(".").str[0]
    c["date"] = pd.to_datetime(c["date"]) + pd.offsets.MonthEnd(0)
    c = c.dropna(subset=["rev"]).drop_duplicates(["ticker", "date", "period"])
    w = c.pivot_table(index=["ticker", "date"], columns="period", values="rev", aggfunc="first")
    n = c[c.period == "FY1"].set_index(["ticker", "date"])["n_est"]
    w = w.join(n.rename("n_est_fy1"))
    w["cg_fwd"] = w["FY2"] / w["FY1"] - 1            # consensus one-year-forward revenue growth (currency-free)
    l = pd.read_csv(LIC / "lseg_ltg_monthly.csv").rename(columns={"Calc Date": "date", "Long Term Growth - Mean": "ltg"})
    l["ticker"] = l["Instrument"].str.split(".").str[0]
    l["date"] = pd.to_datetime(l["date"]) + pd.offsets.MonthEnd(0)
    l = l.dropna(subset=["ltg"]).drop_duplicates(["ticker", "date"]).set_index(["ticker", "date"])["ltg"] / 100
    return w.join(l, how="left").reset_index()


def main():
    V = pd.read_parquet(OUT / "kbri_v1.0_variables.parquet")[["date", "ticker", "group", "g_star", "revenue_usd"]]
    V["date"] = pd.to_datetime(V["date"]) + pd.offsets.MonthEnd(0)
    U = pd.read_parquet(ROOT / "data" / "staged" / "kbri_universe_monthly.parquet")[["date", "ticker", "member", "member_value_chain"]]
    U["date"] = pd.to_datetime(U["date"]) + pd.offsets.MonthEnd(0)
    M = pd.read_parquet(ROOT / "data" / "staged" / "kbri_market_monthly.parquet")[["date", "ticker", "close"]]
    M["date"] = pd.to_datetime(M["date"]) + pd.offsets.MonthEnd(0)
    P = V.merge(U, on=["date", "ticker"], how="left").merge(consensus_panel(), on=["ticker", "date"], how="left")
    P = P.merge(M, on=["date", "ticker"], how="left").sort_values(["ticker", "date"])
    # outcomes (realised, for evaluation only)
    P["rev_fwd12"] = P.groupby("ticker")["revenue_usd"].shift(-12) / P["revenue_usd"] - 1
    P["ret_fwd12"] = P.groupby("ticker")["close"].shift(-12) / P["close"] - 1
    P["gap_fwd"] = P["g_star"] - P["cg_fwd"]
    P["gap_ltg"] = P["g_star"] - P["ltg"]
    vc = P[(P.member_value_chain == True) & P.g_star.notna() & P.cg_fwd.notna()].copy()  # noqa: E712
    vc = vc[(vc.cg_fwd.abs() < 2) & (vc.g_star.abs() < 2)]                                   # drop broken ratios

    res = {"note": "Exploratory, not registered. Value-chain basket members with both g* and consensus.",
           "firm_months": int(len(vc)), "firms": int(vc.ticker.nunique()),
           "coverage_share_of_vc_firm_months": float(len(vc) / max(1, ((P.member_value_chain == True) & P.g_star.notna()).sum()))}  # noqa: E712
    # 1. level comparison
    res["median_g_star"] = float(vc.g_star.median())
    res["median_consensus_fwd_growth"] = float(vc.cg_fwd.median())
    lt = vc.dropna(subset=["ltg"])
    lt = lt[lt.ltg.abs() < 1]
    res["median_consensus_ltg"] = float(lt.ltg.median())
    res["share_firm_months_gstar_above_consensus_fwd"] = float((vc.gap_fwd > 0).mean())
    res["share_firm_months_gstar_above_ltg"] = float((lt.gap_ltg > 0).mean())
    # 2. basket medians over time
    b = vc.groupby("date").agg(g_star=("g_star", "median"), cg_fwd=("cg_fwd", "median"), n=("ticker", "count"))
    b = b.join(lt.groupby("date")["ltg"].median())
    b["gap_fwd"] = b.g_star - b.cg_fwd
    b.to_csv(LIC / "robustness_lseg_basket_medians.csv")  # vendor-derived monthly series, kept private
    yr = b.resample("YE").last()
    res["basket_median_by_year_end"] = {str(d.year): {"g_star": round(r.g_star, 4), "cons_fwd": round(r.cg_fwd, 4),
                                                       "ltg": None if pd.isna(r.ltg) else round(r.ltg, 4), "n": int(r.n)}
                                        for d, r in yr.iterrows()}
    # 3. forecasting realised 12-month revenue growth: rank correlation by month, averaged
    ev = vc.dropna(subset=["rev_fwd12"])

    def mean_ic(df, x, y):
        ics = [spearmanr(d[x], d[y]).correlation for _, d in df.groupby("date") if len(d) >= 10]
        ics = np.array([i for i in ics if np.isfinite(i)])
        return float(ics.mean()), float(ics.mean() / (ics.std(ddof=1) / np.sqrt(len(ics)))), int(len(ics))

    res["ic_realised_rev_growth"] = {k: dict(zip(("mean_ic", "t_naive", "months"), mean_ic(ev, k, "rev_fwd12")))
                                     for k in ("g_star", "cg_fwd")}
    res["mae_realised_rev_growth"] = {"g_star": float((ev.g_star - ev.rev_fwd12).abs().median()),
                                      "cg_fwd": float((ev.cg_fwd - ev.rev_fwd12).abs().median())}
    # 4. does the gap (price ahead of analysts) predict 12-month returns across firms?
    er = vc.dropna(subset=["ret_fwd12"])
    res["ic_fwd12_return"] = {k: dict(zip(("mean_ic", "t_naive", "months"), mean_ic(er, k, "ret_fwd12")))
                              for k in ("gap_fwd", "g_star", "cg_fwd")}
    # by period (sign stability, as in Section 7)
    res["ic_fwd12_return_by_period"] = {}
    for lab, lo, hi in (("2012_2018", "2012-01-01", "2018-12-31"), ("2019_2025", "2019-01-01", "2025-10-31")):
        s = er[(er.date >= lo) & (er.date <= hi)]
        res["ic_fwd12_return_by_period"][lab] = {k: round(mean_ic(s, k, "ret_fwd12")[0], 4) for k in ("gap_fwd", "g_star")}
    # quintile spread on the gap
    er = er.copy()
    er["q"] = er.groupby("date")["gap_fwd"].transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) if len(s) >= 10 else np.nan)
    qs = er.groupby(["date", "q"])["ret_fwd12"].mean().unstack()
    res["quintile_mean_fwd12_return"] = {f"Q{int(k)+1}": float(v) for k, v in qs.mean().items()}
    res["q5_minus_q1_fwd12"] = float((qs[4] - qs[0]).mean())
    (OUT / "robustness_lseg_consensus_summary.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
