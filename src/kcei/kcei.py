"""KCEI v1.0: climate and energy exposure dashboard and scenario model (no composite score).

Outputs (data/outputs/):
  kcei_v1.0_company_scope2.csv   Scope 2 location- vs market-based, and the accounting gap
  kcei_v1.0_scenarios_us.csv     US data-centre load paths 2028 (LBNL) and incremental emissions
  kcei_v1.0_operator_stress.csv  specialist operators under utilisation cuts of 20/40/60%
Every input comes from config/kcei_inputs_v1.0.csv (with source URL) or the KBRI point-in-time panel.
Each output row is labelled reported / forecast / contingent (methodology s.11.3).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.kbri.fundamentals import ROOT

IN = pd.read_csv(ROOT / "config" / "kcei_inputs_v1.0.csv")
OUT = ROOT / "data" / "outputs"


def v(metric, entity, period):
    r = IN[(IN.metric == metric) & (IN.entity == entity) & (IN.period.astype(str) == str(period))]
    return float(r.value.iloc[0]) if len(r) else np.nan


def company_scope2():
    rows = []
    for (ent, per), _ in IN[IN.metric.str.startswith("scope2")].groupby(["entity", "period"]):
        loc, mkt = v("scope2_location", ent, per), v("scope2_market", ent, per)
        if np.isfinite(loc) and np.isfinite(mkt):
            rows.append({"entity": ent, "period": per, "scope2_location_t": loc, "scope2_market_t": mkt,
                         "accounting_gap_share": 1 - mkt / loc, "status": "reported"})
    S = pd.DataFrame(rows).sort_values(["entity", "period"])
    latest = S.groupby("entity").tail(1)
    tot = {"entity": "Four hyperscalers (latest year each)", "period": "mixed",
           "scope2_location_t": latest.scope2_location_t.sum(), "scope2_market_t": latest.scope2_market_t.sum(),
           "accounting_gap_share": 1 - latest.scope2_market_t.sum() / latest.scope2_location_t.sum(), "status": "reported (sum)"}
    S = pd.concat([S, pd.DataFrame([tot])], ignore_index=True)
    S.to_csv(OUT / "kcei_v1.0_company_scope2.csv", index=False)
    return S


def scenarios_us():
    base = v("dc_electricity", "US", 2023)
    paths = {"A: sustained build-out (LBNL high)": v("dc_electricity_high", "US", 2028),
             "B: correction and consolidation (LBNL midpoint)": (v("dc_electricity_high", "US", 2028) + v("dc_electricity_low", "US", 2028)) / 2,
             "C: overbuild and stranding (LBNL low)": v("dc_electricity_low", "US", 2028)}
    rows = []
    for name, load in paths.items():
        inc = load - base
        for lab, gi in (("Ember 2024 average", v("grid_intensity", "US", 2024)), ("EIA 2023 average", v("grid_intensity", "US", 2023))):
            rows.append({"scenario": name, "load_2028_TWh": load, "incremental_TWh_vs_2023": inc,
                         "cagr_2023_28": (load / base) ** (1 / 5) - 1, "grid_intensity_basis": lab, "gCO2_per_kWh": gi,
                         "incremental_location_based_MtCO2": inc * 1e9 * gi / 1e12, "status": "forecast"})
    S = pd.DataFrame(rows)
    S.to_csv(OUT / "kcei_v1.0_scenarios_us.csv", index=False)
    return S


def operator_stress(tickers=("CRWV", "NBIS", "APLD", "EQIX", "DLR")):
    P = pd.read_parquet(ROOT / "data" / "staged" / "kbri_fundamentals_pit.parquet")
    D = pd.read_parquet(ROOT / "data" / "staged" / "kbri_market_monthly.parquet")
    rows = []
    for t in tickers:
        x = P[P.ticker == t].sort_values("filed").iloc[-1]
        f = pd.read_parquet(ROOT / "data" / "staged" / "edgar" / f"facts_{t}.parquet")
        g = f[f.concept.isin(["PropertyPlantAndEquipmentNet", "RealEstateInvestmentPropertyNet"]) & f["start"].isna() & (f.unit == "USD")]
        ppe = float(g.sort_values(["end", "filed"]).iloc[-1]["val"]) if len(g) else np.nan
        m = D[D.ticker == t].sort_values("date").iloc[-1]
        rev = x["revenue_ttm"]
        ebit = x["operating_income_ttm"]
        ebitda = ebit + np.nan_to_num(x["dna_ttm"])
        interest = x["interest_expense_ttm"]
        for u in (0.0, 0.2, 0.4, 0.6):
            e = ebitda - u * rev                       # lost revenue falls straight to EBITDA (costs largely fixed)
            rows.append({"ticker": t, "period_end": x["period_end"].date(), "utilisation_cut": u, "revenue_ttm": rev,
                         "ebitda_ttm": ebitda, "ebitda_stressed": e, "interest_ttm": interest,
                         "interest_cover_stressed": e / interest if interest and interest > 0 else np.nan,
                         "ppe_net": ppe, "ppe_idle_at_cut": ppe * u, "net_debt": m.debt_usd - m.cash_usd,
                         "status": "reported" if u == 0 else "contingent"})
    S = pd.DataFrame(rows)
    S.to_csv(OUT / "kcei_v1.0_operator_stress.csv", index=False)
    return S


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    print(company_scope2().round(3).to_string(index=False))
    print(scenarios_us().round(2).to_string(index=False))
    s = operator_stress()
    print(s.assign(**{c: s[c] / 1e9 for c in ["revenue_ttm", "ebitda_ttm", "ebitda_stressed", "interest_ttm", "ppe_net", "ppe_idle_at_cut", "net_debt"]}).round(2).to_string(index=False))
