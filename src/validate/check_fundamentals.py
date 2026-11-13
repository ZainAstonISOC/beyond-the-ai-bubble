"""Phase 5 gate: reconcile the point-in-time fundamentals panel to the filings.

1. Quarter-sum test: for every fiscal year since 2010, Q1+Q2+Q3+Q4 revenue (3-month
   facts, Q4 derived) must equal the annual 10-K revenue within 0.5%. US quarterly filers.
2. Identity tests on every panel row: gross profit <= revenue, capex >= 0, assets > 0.
3. Continuity: |log change| of TTM revenue between consecutive filings > 0.4 is listed
   for manual review (a list, not a failure: real step changes exist).
4. Item coverage per company.
Writes reports/phase5_fundamentals_reconciliation.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.kbri import fundamentals as F

ROOT = F.ROOT
REPORT = ROOT / "reports" / "phase5_fundamentals_reconciliation.md"


def quarter_sum(ticker: str):
    facts = F.load_facts(ticker)
    tags, tax = F.tagmap(ticker)
    af = F.AsOf(facts, facts["filed"].max(), tax, tags, CFG_cur(ticker))
    out = []
    for E in af.annual_ends("revenue"):
        if E < pd.Timestamp("2010-06-01"):
            continue
        fy = af.duration("revenue", E, 350, 380)
        qe = [E - pd.DateOffset(months=m) for m in (9, 6, 3)]
        qs = []
        for e in qe:
            ends = [x for x in F.period_ends(af) if abs((x - e).days) <= 12]
            qs.append(af.duration("revenue", ends[0], 80, 100) if ends else np.nan)
        q4 = af.quarter("revenue", E)
        tot = np.nansum(qs) + q4 if not any(np.isnan(qs)) else np.nan
        out.append((ticker, E.date(), fy, tot, abs(tot / fy - 1) if fy and not np.isnan(tot) else np.nan))
    return out


def CFG_cur(t):
    return F.CFG.get("foreign", {}).get(t, {}).get("currency", "USD")


def main():
    P = pd.read_parquet(ROOT / "data" / "staged" / "kbri_fundamentals_pit.parquet")
    tick = P["ticker"].unique()
    us_quarterly = [t for t in tick if t not in F.CFG.get("foreign", {})]
    qs = [r for t in us_quarterly for r in quarter_sum(t)]
    Q = pd.DataFrame(qs, columns=["ticker", "fy_end", "fy_revenue", "sum_of_quarters", "abs_diff"])
    Qv = Q.dropna(subset=["abs_diff"])
    qfail = Qv[Qv["abs_diff"] > 0.005]
    ident = pd.DataFrame({
        "gp_gt_rev": (P["gross_profit_ttm"] > P["revenue_ttm"] * 1.0001),
        "neg_capex": (P["capex_ttm"] < 0),
        "assets_nonpos": (P["total_assets"] <= 0),
    })
    P2 = P.sort_values(["ticker", "filed"]).copy()
    P2["dlog_rev"] = P2.groupby("ticker")["revenue_ttm"].transform(lambda s: np.log(s.where(s > 0)).diff())
    jumps = P2[P2["dlog_rev"].abs() > 0.4][["ticker", "filed", "period_end", "revenue_ttm", "dlog_rev"]]
    items = ["revenue_ttm", "gross_profit_ttm", "operating_income_ttm", "net_income_ttm", "cfo_ttm", "capex_ttm", "dna_ttm",
             "interest_expense_ttm", "total_assets", "equity", "cash", "debt_total", "op_lease_liab", "diluted_shares_ttm", "gm_std8"]
    recent = P[P["period_end"] >= "2015-01-01"]
    cov = recent.groupby("ticker")[items].apply(lambda d: d.notna().mean()).round(2)

    md = ["# Phase 5: fundamentals reconciliation", "",
          f"Panel rows (company x filing date): {len(P)}; companies: {len(tick)}.", "",
          f"Quarter-sum test: {len(Qv)} fiscal years tested across {Qv.ticker.nunique()} US quarterly filers; "
          f"{len(qfail)} differ from the annual figure by more than 0.5%. Median absolute difference {Qv.abs_diff.median():.2e}.", ""]
    if len(qfail):
        md += ["| Company | FY end | Annual revenue | Sum of quarters | Difference |", "| --- | --- | --- | --- | --- |"]
        md += [f"| {r.ticker} | {r.fy_end} | {r.fy_revenue:,.0f} | {r.sum_of_quarters:,.0f} | {100*r.abs_diff:.2f}% |" for r in qfail.itertuples()]
    md += ["", f"Identity tests: gross profit above revenue {int(ident.gp_gt_rev.sum())} rows; negative capex {int(ident.neg_capex.sum())}; "
           f"non-positive assets {int(ident.assets_nonpos.sum())}.", "",
           f"TTM revenue changes above 40% between consecutive filings ({len(jumps)}), for review:", "",
           "| Company | Filed | Period end | TTM revenue | log change |", "| --- | --- | --- | --- | --- |"]
    md += [f"| {r.ticker} | {r.filed.date()} | {r.period_end.date()} | {r.revenue_ttm:,.0f} | {r.dlog_rev:+.2f} |" for r in jumps.itertuples()]
    md += ["", "Item coverage since 2015 (share of filing dates with a value):", "", cov.to_markdown()]
    REPORT.write_text("\n".join(md) + "\n")
    Q.to_csv(ROOT / "reports" / "phase5_quarter_sum_test.csv", index=False)
    print(md[2]); print(md[4]); print(md[-5 - len(jumps) - 4] if False else "")
    print("quarter-sum fails:\n", qfail.to_string()); print("identity:", ident.sum().to_dict())
    print("jumps:\n", jumps.to_string()); print(cov.to_string())


if __name__ == "__main__":
    main()
