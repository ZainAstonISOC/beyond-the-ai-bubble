"""Exploratory (not registered): replace the KBRI debt-due-24m proxy with LSEG maturity data.

v1.0 proxies debt due within 24 months by current debt / cash (SEC XBRL). Here the numerator is LSEG
(Refinitiv Fundamentals) 'Short-Term Debt & Current Portion of Long-Term Debt' plus 'Debt - Long-Term -
Maturities - Year 2', in USD, usable from fiscal year end + 90 days. Everything else in KBRI is unchanged.
Outputs aggregate comparison statistics only.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.kbri import engine as K
from src.kmsi import engine as E

ROOT = E.ROOT
LIC = ROOT / "data" / "licensed" / "lseg"
OUT = ROOT / "data" / "outputs"


def lseg_due24m() -> pd.DataFrame:
    d = pd.read_csv(LIC / "lseg_debt_maturity_fy.csv")
    d.columns = ["ric", "fy_end", "st_debt", "lt_mat_y2", "lt_mat_tot"]
    d["ticker"] = d["ric"].str.split(".").str[0]
    d["fy_end"] = pd.to_datetime(d["fy_end"], errors="coerce")
    d = d.dropna(subset=["fy_end"])
    d["due24m"] = d[["st_debt", "lt_mat_y2"]].sum(axis=1, min_count=1)
    d["usable"] = d["fy_end"] + pd.Timedelta(days=90)
    return d.dropna(subset=["due24m"]).sort_values("usable")[["ticker", "usable", "due24m"]].drop_duplicates()


def main():
    V = pd.read_parquet(OUT / "kbri_v1.0_variables.parquet")
    V["date"] = pd.to_datetime(V["date"])
    M = pd.read_parquet(ROOT / "data" / "staged" / "kbri_market_monthly.parquet")[["date", "ticker", "cash_usd"]]
    M["date"] = pd.to_datetime(M["date"])
    L = lseg_due24m()
    W = V.merge(M, on=["date", "ticker"], how="left").sort_values("date")
    W["ticker"] = W["ticker"].astype(str); L["ticker"] = L["ticker"].astype(str); L["usable"] = L["usable"].astype(W["date"].dtype)
    W = pd.merge_asof(W, L.rename(columns={"usable": "date"}).sort_values("date"), on="date", by="ticker", direction="backward")
    new = W["due24m"] / W["cash_usd"].where(W["cash_usd"] > 0)
    V2 = W[V.columns].copy()
    V2["debt_due24m_to_cash"] = new.where(new.notna(), np.nan)
    cov_old = V["debt_due24m_to_cash"].notna().mean()
    cov_new = V2["debt_due24m_to_cash"].notna().mean()
    S1 = pd.read_parquet(OUT / "kbri_v1.0_company_abs.parquet")
    S2 = K.score(V2, "abs")
    U = pd.read_parquet(ROOT / "data" / "staged" / "kbri_universe_monthly.parquet")
    B1 = pd.read_parquet(OUT / "kbri_v1.0_basket_value_chain.parquet")
    B2 = K.basket(S2, V2, U, "member_value_chain")
    m = S1.merge(S2, on=["date", "ticker"], suffixes=("_v1", "_lseg")).dropna(subset=["kbri_v1", "kbri_lseg"])
    band = lambda x: np.floor(np.clip(x, 0, 99.999) / 20)  # noqa: E731
    both = V[["date", "ticker", "debt_due24m_to_cash"]].merge(V2[["date", "ticker", "debt_due24m_to_cash"]], on=["date", "ticker"], suffixes=("_old", "_new")).dropna()
    both = both[["debt_due24m_to_cash_old", "debt_due24m_to_cash_new"]]
    res = {"note": "Exploratory, not registered. LSEG maturity data replace the debt_due24m_to_cash proxy.",
           "coverage_old_proxy": float(cov_old), "coverage_lseg": float(cov_new),
           "rank_corr_variable_old_vs_new": float(both.rank().corr().iloc[0, 1]) if len(both) else None,
           "firm_months_compared": int(len(m)),
           "corr_company_kbri": float(m["kbri_v1"].corr(m["kbri_lseg"])),
           "corr_financing_component": float(m["c_financing_v1"].corr(m["c_financing_lseg"])),
           "company_band_agreement": float((band(m["kbri_v1"]) == band(m["kbri_lseg"])).mean()),
           "corr_value_chain_basket": float(B1["kbri_basket"].corr(B2["kbri_basket"])),
           "max_abs_basket_diff": float((B1["kbri_basket"] - B2["kbri_basket"]).abs().max())}
    d = (B2["kbri_basket"] - B1["kbri_basket"]).dropna()
    res["basket_diff_by_year"] = {str(k.year): round(float(v), 2) for k, v in d.resample("YE").mean().items()}
    res["corr_value_chain_basket_2012_on"] = float(B1.loc["2012":, "kbri_basket"].corr(B2.loc["2012":, "kbri_basket"]))
    (OUT / "robustness_lseg_debt_summary.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
