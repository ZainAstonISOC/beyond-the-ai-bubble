"""KBRI v1.0 validation: sensitivity, ablation, reverse-DCF sensitivity, survivorship.

Pre-registered checks (spec: Validation and robustness suite):
  - weight sensitivity (equal weights; valuation-heavy) and window/transform analogue (KBRI-rel vs KBRI-abs)
  - component ablation
  - g* recomputed under terminal growth 2% / 4%, margin -5 / +5 points, Damodaran implied ERP
  - value-chain basket with and without companies that left the universe
Agreement on the 5-band scale and correlations are reported; nothing feeds back into parameters.
Writes reports/phase6_kbri_validation.md.
"""
from __future__ import annotations

import copy

import numpy as np
import pandas as pd

from src.kbri import engine as K
from src.kbri.fundamentals import CFG, ROOT

OUT = ROOT / "data" / "outputs"
BANDS = [0, 20, 40, 60, 80, 100.0001]


def band(x):
    return pd.cut(x, BANDS, right=False, labels=False)


def agree(a, b):
    m = a.notna() & b.notna()
    return float((band(a[m]) == band(b[m])).mean()), float(np.corrcoef(a[m], b[m])[0, 1])


def damodaran_erp() -> pd.Series:
    x = pd.read_excel(ROOT / "data" / "raw" / "damodaran" / "histimpl.xls", header=6)
    x = x[pd.to_numeric(x["Year"], errors="coerce").notna()]
    s = pd.Series(x["Implied ERP (FCFE)"].values, index=x["Year"].astype(int))
    return s          # value at end of year Y, usable from January of Y+1


def rescore_with(V, cfg_components=None):
    saved = copy.deepcopy(CFG["components"])
    if cfg_components:
        CFG["components"] = cfg_components
    try:
        S = K.score(V, "abs")
    finally:
        CFG["components"] = saved
    return S


def basket_series(S, V, U, col="member_value_chain"):
    return K.basket(S, V, U, col)["kbri_basket"]


def main():
    V = pd.read_parquet(OUT / "kbri_v1.0_variables.parquet")
    S = pd.read_parquet(OUT / "kbri_v1.0_company_abs.parquet")
    Sr = pd.read_parquet(OUT / "kbri_v1.0_company_rel.parquet")
    U = pd.read_parquet(ROOT / "data" / "staged" / "kbri_universe_monthly.parquet")
    base_vc = pd.read_parquet(OUT / "kbri_v1.0_basket_value_chain.parquet")["kbri_basket"]
    base_dc = pd.read_parquet(OUT / "kbri_v1.0_basket_disclosure.parquet")["kbri_basket"]
    rows = []

    # weights
    comps = copy.deepcopy(CFG["components"])
    names = [k for k, v in comps.items() if not v.get("basket_only")]
    eq = copy.deepcopy(comps)
    for n in names:
        eq[n]["weight"] = 0.9 / len(names)
    vh = copy.deepcopy(comps)
    for n, w in zip(names, [0.40, 0.15, 0.15, 0.10, 0.10]):
        vh[n]["weight"] = w
    for lab, c in (("equal weights", eq), ("valuation-heavy (40%)", vh)):
        S2 = rescore_with(V, c)
        a_co = agree(S["kbri"], S2["kbri"])
        a_vc = agree(base_vc, basket_series(S2, V, U))
        rows.append((f"Weights: {lab}", f"company bands agree {100*a_co[0]:.1f}% (r={a_co[1]:.3f}); value-chain basket bands agree {100*a_vc[0]:.1f}% (r={a_vc[1]:.3f})"))

    # abs vs rel
    a = agree(S["kbri"], Sr["kbri"])
    rows.append(("KBRI-abs vs KBRI-rel (company)", f"bands agree {100*a[0]:.1f}%, r={a[1]:.3f}"))

    # ablation
    abl = []
    for n in names:
        c = copy.deepcopy(comps)
        c[n]["weight"] = 0.0
        S2 = rescore_with(V, c)
        abl.append(f"{n} r={agree(S['kbri'], S2['kbri'])[1]:.3f}")
    rows.append(("Ablation (company KBRI correlation without component)", "; ".join(abl)))

    # reverse-DCF sensitivity
    erp = damodaran_erp()
    sens = {
        "terminal growth 2%": dict(gT=0.02), "terminal growth 4%": dict(gT=0.04),
        "margin -5 points": dict(dm=-0.05), "margin +5 points": dict(dm=0.05), "Damodaran implied ERP": dict(erp=True)}
    last = V["date"].max()
    for lab, kw in sens.items():
        V2 = V.copy()
        m = V2["m_used"] + kw.get("dm", 0.0)
        if kw.get("erp"):
            e = V2["date"].dt.year.map(lambda y: erp.get(y - 1, np.nan))
            r = V2["rf"] + V2["beta"] * e
        else:
            r = V2["r_used"]
        gT = kw.get("gT", CFG["reverse_dcf"]["terminal_growth"])
        V2["g_star"] = [K.solve_g(ev, R, mm, rr, gT) for ev, R, mm, rr in zip(V2["ev_usd"], V2["revenue_usd"], m, r)]
        V2["g_star_minus_rev_cagr3"] = V2["g_star"] - V2["rev_cagr3"]
        S2 = rescore_with(V2)
        a_co, a_vc = agree(S["kbri"], S2["kbri"]), agree(base_vc, basket_series(S2, V2, U))
        rk = S[S.date == last].set_index("ticker")["kbri"].rank().corr(S2[S2.date == last].set_index("ticker")["kbri"].rank())
        dg = (V2["g_star"] - V["g_star"]).median()
        rows.append((f"Reverse DCF: {lab}", f"median g* shift {100*dg:+.1f} pts; company bands agree {100*a_co[0]:.1f}%; "
                     f"value-chain basket r={a_vc[1]:.3f}; latest company rank correlation {rk:.3f}"))

    # survivorship: value-chain basket restricted to firms that are members at the end
    end_members = set(U[(U.date == U.date.max()) & U.member_value_chain].ticker)
    U2 = U.copy()
    U2["member_value_chain"] = U2["member_value_chain"] & U2["ticker"].isin(end_members)
    leavers = sorted(set(U[U.member_value_chain].ticker) - end_members)
    a = agree(base_vc, basket_series(S, V, U2))
    rows.append(("Survivorship (value-chain basket, end members only)", f"firms that left at some point and are excluded: {leavers or 'none'}; bands agree {100*a[0]:.1f}%, r={a[1]:.3f}"))

    md = ["# Phase 6: KBRI v1.0 validation", "",
          f"Company-months scored: {S['kbri'].notna().sum()}; value-chain basket {base_vc.first_valid_index().date()} to {base_vc.last_valid_index().date()}; "
          f"disclosure basket {base_dc.first_valid_index().date()} to {base_dc.last_valid_index().date()}.", "",
          "| Check | Result |", "| --- | --- |"] + [f"| {a} | {b} |" for a, b in rows]
    md += ["", "Independent recalculation: see src/kbri/recalc_numpy.py (g* to 2.5e-11; company scores and basket mean exact)."]
    (ROOT / "reports" / "phase6_kbri_validation.md").write_text("\n".join(md) + "\n")
    for a, b in rows:
        print(f"- {a}: {b}")


if __name__ == "__main__":
    main()
