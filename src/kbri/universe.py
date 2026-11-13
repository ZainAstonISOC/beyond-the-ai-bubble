"""Point-in-time AI-basket membership (universe rule, spec section KBRI).

A company is a member at month-end M when all four conditions hold:
 1. US listed and files 10-K/10-Q, or 20-F with XBRL            (all candidates satisfy this)
 2. market cap at M >= $10bn ($2bn for specialist infrastructure)
 3. its AI-disclosure entry filing has been filed by M          (proposed by screen; human confirmation pending)
 4. at least four quarters of filings since listing             (>= 4 report filings, or >= 2 annual 20-Fs)

Secondary basket (deviation logged 13 Nov 2026, before any KBRI score): the AI value-chain basket = all
candidates meeting conditions 1, 2 and 4, used where the tests need longer history.

Condition 2 is tested monthly, so a member that falls below the threshold leaves and can re-enter.
Status column marks whether condition 3 is machine-proposed or human-confirmed.
"""
from __future__ import annotations

import pandas as pd

from src.kbri.fundamentals import CFG, ROOT

REP = ROOT / "reports"
STAGED = ROOT / "data" / "staged"


def build() -> pd.DataFrame:
    D = pd.read_parquet(STAGED / "kbri_market_monthly.parquet")
    R = pd.read_csv(REP / "phase5_universe_reading_pass.csv", parse_dates=["entry_filed"])
    R = R[R["human_confirmed"].astype(str).str.lower() == "yes"]
    entry = R.set_index("ticker")["entry_filed"]
    status = "reading pass, confirmed by Howden Research"
    fil = {}
    for t in D["ticker"].unique():
        fl = pd.concat([pd.read_parquet(STAGED / "edgar" / f"filings_{t}.parquet")] +
                       [pd.read_parquet(STAGED / "edgar" / f"filings_{t}_pred{pp['cik']}.parquet")
                        for pp in CFG.get("predecessors", {}).get(t, [])])      # predecessor filings count too
        fl = fl[fl["form"].isin(["10-K", "10-Q", "20-F"])]
        fil[t] = pd.to_datetime(fl["filingDate"]).sort_values().reset_index(drop=True)
    rows = []
    for r in D.itertuples():
        thr = float(CFG["universe"]["min_mcap_specialist_usd"] if r.group == "specialist_infra" else CFG["universe"]["min_mcap_usd"])
        c2 = r.mcap_usd >= thr
        c3 = r.ticker in entry.index and entry[r.ticker] <= r.date
        f = fil[r.ticker]
        n = (f <= r.date).sum()
        annual_only = r.ticker in CFG.get("foreign", {})
        c4 = n >= (2 if annual_only else 4)
        rows.append({"date": r.date, "ticker": r.ticker, "group": r.group, "c2_mcap": c2, "c3_ai": c3, "c4_history": c4,
                     "member": bool(c2 and c3 and c4),            # primary: registered disclosure basket
                     "member_value_chain": bool(c2 and c4)})      # secondary (logged deviation): AI value-chain basket
    U = pd.DataFrame(rows)
    U["c3_status"] = status
    U.to_parquet(STAGED / "kbri_universe_monthly.parquet")
    return U


if __name__ == "__main__":
    U = build()
    for col in ("member", "member_value_chain"):
        m = U[U[col]].groupby("date").size()
        print(col, "by year-end:", {d.year: n for d, n in m[m.index.month == 12].items()})
    last = U[U["date"] == U["date"].max()]
    print("latest members:", sorted(last[last.member].ticker), "\nnon-members:", sorted(last[~last.member].ticker))
