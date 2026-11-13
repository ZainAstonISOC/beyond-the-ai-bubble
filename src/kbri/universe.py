"""Point-in-time AI-basket membership (universe rule, spec section KBRI).

A company is a member at month-end M when all four conditions hold:
 1. US listed and files 10-K/10-Q, or 20-F with XBRL            (all candidates satisfy this)
 2. market cap at M >= $10bn ($2bn for specialist infrastructure)
 3. its AI-disclosure entry filing has been filed by M          (proposed by screen; human confirmation pending)
 4. at least four quarters of filings since listing             (>= 4 report filings, or >= 2 annual 20-Fs)

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
    E = pd.read_csv(REP / "phase5_universe_ai_evidence.csv", parse_dates=["filed"])
    conf = E["human_confirmed"].astype(str).str.lower().isin(["yes", "y", "true", "confirmed"])
    reject = E["human_confirmed"].astype(str).str.lower().isin(["no", "n", "false", "rejected"])
    if conf.any():
        entry = E[conf].sort_values("filed").groupby("ticker")["filed"].first()
        status = "human-confirmed"
    else:
        entry = E[E["proposed_entry_filing"] & ~reject].groupby("ticker")["filed"].first()
        status = "machine-proposed"
    fil = {}
    for t in D["ticker"].unique():
        fl = pd.read_parquet(STAGED / "edgar" / f"filings_{t}.parquet")
        fl = fl[fl["form"].isin(["10-K", "10-Q", "20-F"])]
        fil[t] = pd.to_datetime(fl["filingDate"]).sort_values().reset_index(drop=True)
    rows = []
    for r in D.itertuples():
        thr = CFG["universe"]["min_mcap_specialist_usd"] if r.group == "specialist_infra" else CFG["universe"]["min_mcap_usd"]
        c2 = r.mcap_usd >= thr
        c3 = r.ticker in entry.index and entry[r.ticker] <= r.date
        f = fil[r.ticker]
        n = (f <= r.date).sum()
        annual_only = r.ticker in CFG.get("foreign", {})
        c4 = n >= (2 if annual_only else 4)
        rows.append({"date": r.date, "ticker": r.ticker, "group": r.group, "c2_mcap": c2, "c3_ai": c3, "c4_history": c4,
                     "member": bool(c2 and c3 and c4)})
    U = pd.DataFrame(rows)
    U["c3_status"] = status
    U.to_parquet(STAGED / "kbri_universe_monthly.parquet")
    return U


if __name__ == "__main__":
    U = build()
    m = U[U["member"]].groupby("date").size()
    print("members by year-end:", m[m.index.month == 12].to_dict())
    last = U[U["date"] == U["date"].max()]
    print("latest members:", sorted(last[last.member].ticker), "\nnon-members:", sorted(last[~last.member].ticker))
