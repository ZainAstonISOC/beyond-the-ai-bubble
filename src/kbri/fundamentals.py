"""Point-in-time fundamentals panel for KBRI.

For each company and each filing date T, every item is recomputed from the XBRL
facts filed on or before T only. Restatements replace earlier values from the
date they were filed, never before.

Flows (income statement, cash flow) are trailing twelve months:
    TTM(E) = FY(E)                                   if a fiscal year ends at E
           = FY(last) + YTD(E) - YTD(E - 1 year)     otherwise
Quarterly values (needed for gross-margin stability) use 3-month facts, with
Q4 = FY - 9-month YTD. Stocks (balance sheet) take the instant value at E.
For each period the first tag in the frozen priority list that has a value is used,
so a company switching tags (e.g. Revenues -> RevenueFromContract... in 2018)
keeps a continuous series.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
ED = ROOT / "data" / "staged" / "edgar"
CFG = yaml.safe_load((ROOT / "config" / "kbri_v1.0.yaml").read_text())
FLOW_ITEMS = ["revenue", "cost_of_revenue", "gross_profit", "operating_income", "net_income", "pretax_income",
              "income_tax", "cfo", "capex", "dna", "interest_expense", "equity_issued", "equity_repurchased", "diluted_shares"]
STOCK_ITEMS = ["total_assets", "equity", "cash", "st_investments", "debt_total", "debt_noncurrent", "debt_current",
               "short_term_borrowings", "op_lease_liab", "op_lease_liab_noncurrent", "op_lease_liab_current",
               "fin_lease_liab", "fin_lease_liab_noncurrent", "fin_lease_liab_current", "rpo", "lease_liab"]
REPORT_FORMS = {"10-K", "10-Q", "20-F", "10-K/A", "10-Q/A", "20-F/A", "10-KT", "40-F"}
TOL = pd.Timedelta(days=7)
# tags in these lists measure the same quantity, so a mixed-tag TTM is allowed as a fallback
SYNONYM_ITEMS = {"revenue", "net_income", "cfo", "operating_income", "gross_profit", "cost_of_revenue"}
NONNEG_ITEMS = {"revenue", "capex", "diluted_shares"}
# capex: only these two tags are the same quantity (REIT property tags are not), so only they may be mixed
MIXABLE_SUBSET = {"capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"]}


def load_facts(ticker: str) -> pd.DataFrame:
    frames = [pd.read_parquet(ED / f"facts_{ticker}.parquet").assign(src=ticker)]
    for p in CFG.get("predecessors", {}).get(ticker, []):
        f = ED / f"facts_{ticker}_pred{p['cik']}.parquet"
        if f.exists():
            frames.append(pd.read_parquet(f).assign(src=f"pred{p['cik']}"))
    df = pd.concat(frames, ignore_index=True)
    df = df[df["form"].isin(REPORT_FORMS) & df["filed"].notna() & df["end"].notna()]
    # successor beats predecessor for the same period: rank successor first
    df["prio"] = (df["src"] != ticker).astype(int)
    df["days"] = (df["end"] - df["start"]).dt.days
    return df


def tagmap(ticker: str) -> tuple[dict, str]:
    if ticker == "TSM":
        return CFG["ifrs_tags"], "ifrs-full"
    return CFG["tags"], "us-gaap"


class AsOf:
    """Facts known at T: latest-filed value per (concept, unit, start, end)."""

    def __init__(self, facts: pd.DataFrame, T: pd.Timestamp, tax: str, tags: dict, currency: str | None):
        f = facts[(facts["filed"] <= T)]
        f = f[(f["taxonomy"] == tax) | (f["taxonomy"] == "dei")]
        if currency:
            f = f[f["unit"].isin([currency, "shares", f"{currency}/shares", "pure"])]
        f = f.sort_values(["prio", "filed"], ascending=[False, True])   # last row wins: successor, latest filed
        self.f = f.drop_duplicates(["concept", "unit", "start", "end"], keep="last")
        self.tags = tags
        self.by = {c: g for c, g in self.f.groupby("concept")}

    def _tag_vals(self, tag, cond):
        g = self.by.get(tag.split(":")[-1])
        if g is None:
            return np.nan
        h = g[cond(g)]
        return float(h.sort_values("filed").iloc[-1]["val"]) if len(h) else np.nan

    def _pick(self, item, cond):
        for tag in self.tags.get(item, []):
            v = self._tag_vals(tag, cond)
            if not np.isnan(v):
                return v
        return np.nan

    def _dur(self, tag, end, lo, hi):
        return self._tag_vals(tag, lambda g: ((g["end"] - end).abs() <= TOL) & g["days"].between(lo, hi))

    def duration(self, item, end, lo, hi):
        return self._pick(item, lambda g: ((g["end"] - end).abs() <= TOL) & g["days"].between(lo, hi))

    def instant(self, item, end):
        return self._pick(item, lambda g: g["start"].isna() & ((g["end"] - end).abs() <= TOL))

    def annual_ends(self, item):
        ends = []
        for tag in self.tags.get(item, []):
            g = self.by.get(tag)
            if g is not None:
                ends += list(g.loc[g["days"].between(350, 380), "end"])
        return sorted(set(ends))

    def ttm(self, item, E):
        """Each TTM value is built from ONE tag (no mixing of tags across FY and YTD)."""
        prior = [e for e in self.annual_ends("revenue") + self.annual_ends(item) if e < E - TOL]
        Ef = max(prior) if prior else None
        for tag in self.tags.get(item, []):
            fy = self._dur(tag, E, 350, 380)
            if not np.isnan(fy):
                return fy if not (item in NONNEG_ITEMS and fy < 0) else np.nan
            if Ef is None:
                continue
            ytd_days = (E - Ef).days
            if ytd_days < 60 or ytd_days > 330:
                continue
            v = (self._dur(tag, Ef, 350, 380) + self._dur(tag, E, ytd_days - 12, ytd_days + 12)
                 - self._dur(tag, E - pd.DateOffset(years=1), ytd_days - 12, ytd_days + 12))
            if not np.isnan(v):
                return v if not (item in NONNEG_ITEMS and v < 0) else np.nan
        if item in MIXABLE_SUBSET and Ef is not None:
            sub = AsOf.__new__(AsOf); sub.__dict__ = dict(self.__dict__); sub.tags = {item: MIXABLE_SUBSET[item]}
            fy = sub.duration(item, E, 350, 380)
            d = (E - Ef).days
            if np.isnan(fy) and 60 <= d <= 330:
                fy = (sub.duration(item, Ef, 350, 380) + sub.duration(item, E, d - 12, d + 12)
                      - sub.duration(item, E - pd.DateOffset(years=1), d - 12, d + 12))
            if not np.isnan(fy) and fy >= 0:
                return fy
        if item in SYNONYM_ITEMS and Ef is not None:
            fy = self.duration(item, E, 350, 380)
            if not np.isnan(fy):
                return fy
            d = (E - Ef).days
            if 60 <= d <= 330:
                v = (self.duration(item, Ef, 350, 380) + self.duration(item, E, d - 12, d + 12)
                     - self.duration(item, E - pd.DateOffset(years=1), d - 12, d + 12))
                if not np.isnan(v) and not (item in NONNEG_ITEMS and v < 0):
                    return v
        return np.nan

    def quarter(self, item, E):
        """3-month value from one tag; rejected if above 60% of the fiscal year containing it
        (guards against annual values tagged with quarterly contexts), then Q4 = FY - 9M."""
        for tag in self.tags.get(item, []):
            q = self._dur(tag, E, 80, 100)
            fy_next = [self._dur(tag, E + pd.Timedelta(days=d), 350, 380) for d in (0, 91, 182, 273)]
            fyv = next((x for x in fy_next if not np.isnan(x)), np.nan)
            if not np.isnan(q) and (np.isnan(fyv) or abs(q) <= 0.6 * abs(fyv)):
                return q
            fy = self._dur(tag, E, 350, 380)
            nine = self._dur(tag, E - pd.Timedelta(days=91), 260, 285)
            if not np.isnan(fy - nine):
                return fy - nine
        return np.nan

    def avg_shares(self, E):
        """Diluted weighted-average shares for the shortest period ending at E (an average, never summed)."""
        for lo, hi in ((80, 100), (170, 190), (260, 285), (350, 380)):
            v = self.duration("diluted_shares", E, lo, hi)
            if not np.isnan(v) and v > 0:
                return v
        return np.nan

    def fy_reconciles(self, item, Ef, tol=0.02):
        """Q1+Q2+Q3+Q4 within tol of FY (guards against mis-dated quarterly contexts)."""
        fy = self.duration(item, Ef, 350, 380)
        if np.isnan(fy) or fy == 0:
            return False
        qs = [self.quarter(item, Ef - pd.DateOffset(months=m)) if m else self.quarter(item, Ef) for m in (9, 6, 3, 0)]
        if any(np.isnan(qs)):
            ends = [e for e in period_ends(self) if Ef - pd.Timedelta(days=380) < e <= Ef + TOL]
            qs = [self.quarter(item, e) for e in ends[-4:]] if len(ends) >= 4 else [np.nan]
        return not any(np.isnan(qs)) and abs(sum(qs) / fy - 1) <= tol


def period_ends(af: AsOf) -> list[pd.Timestamp]:
    g = pd.concat([af.by[t] for t in af.tags["revenue"] if t in af.by] or [pd.DataFrame(columns=["end", "days"])])
    ends = g.loc[g["days"].between(80, 380), "end"] if len(g) else pd.Series(dtype="datetime64[ns]")
    return sorted(set(pd.to_datetime(ends)))


def build_company(ticker: str) -> pd.DataFrame:
    facts = load_facts(ticker)
    tags, tax = tagmap(ticker)
    fx = CFG.get("foreign", {}).get(ticker, {})
    cur = fx.get("currency", "USD")
    events = sorted(facts.loc[facts["taxonomy"] == tax, "filed"].unique())
    rows = []
    for T in events:
        T = pd.Timestamp(T)
        af = AsOf(facts, T, tax, tags, cur)
        ends = period_ends(af)
        if not ends:
            continue
        E = ends[-1]
        r = {"ticker": ticker, "filed": T, "period_end": E, "currency": cur}
        for it in FLOW_ITEMS:
            r[f"{it}_ttm"] = af.ttm(it, E) if it != "diluted_shares" else af.avg_shares(E)
        if np.isnan(r["gross_profit_ttm"]) and not np.isnan(r["cost_of_revenue_ttm"]):
            r["gross_profit_ttm"] = r["revenue_ttm"] - r["cost_of_revenue_ttm"]
        for it in STOCK_ITEMS:
            r[it] = af.instant(it, E)
        # 3-year-earlier TTM revenue and capex, and prior-year values, as known at T
        for lag, tag in [(1, "1y"), (3, "3y")]:
            El = E - pd.DateOffset(years=lag)
            cands = [e for e in ends if abs((e - El).days) <= 10]
            El = cands[-1] if cands else El
            r[f"revenue_ttm_{tag}"] = af.ttm("revenue", El)
            r[f"capex_ttm_{tag}"] = af.ttm("capex", El)
            r[f"diluted_shares_ttm_{tag}"] = af.avg_shares(El)
            r[f"total_assets_{tag}"] = af.instant("total_assets", El)
            r[f"operating_income_ttm_{tag}"] = af.ttm("operating_income", El)
            for it in ["equity", "cash", "debt_total", "debt_noncurrent", "debt_current", "op_lease_liab", "fin_lease_liab"]:
                r[f"{it}_{tag}"] = af.instant(it, El)
        # last 8 quarterly gross margins (US filers only; 20-F filers have annual data)
        qs = [e for e in ends if e <= E][-12:]
        gms = []
        fy_ok = {}
        aends = af.annual_ends("revenue")
        for e in qs:
            Ef = next((a for a in aends if a >= e - TOL), None)
            # quarters of the current, unfinished fiscal year cannot be reconciled yet and are accepted
            if Ef is not None and not fy_ok.setdefault(Ef, af.fy_reconciles("revenue", Ef)):
                continue
            rv = af.quarter("revenue", e)
            gp = af.quarter("gross_profit", e)
            if np.isnan(gp):
                cr = af.quarter("cost_of_revenue", e)
                gp = rv - cr
            if rv and not np.isnan(rv) and rv > 0 and not np.isnan(gp):
                gms.append((e, gp / rv))
        gms = sorted(set(gms))[-8:]
        r["gm_quarters"] = len(gms)
        r["gm_std8"] = float(np.std([g for _, g in gms], ddof=1)) if len(gms) == 8 else np.nan
        sh = af.by.get("EntityCommonStockSharesOutstanding")
        if sh is not None and len(sh):
            s = sh[sh["filed"] == sh["filed"].max()]
            r["shares_out_cover"] = float(s["val"].sum())        # sums share classes reported on the cover
            r["shares_out_date"] = s["end"].max()
        rows.append(r)
    df = pd.DataFrame(rows)
    if len(df):
        # one row per filing date; keep the latest period if several filings share a date
        df = df.sort_values(["filed", "period_end"]).drop_duplicates("filed", keep="last")
    return df


def main():
    tick = [t for g in CFG["universe"]["candidates"].values() for t in g]
    out = []
    for t in tick:
        d = build_company(t)
        out.append(d)
        last = d.iloc[-1] if len(d) else None
        print(f"{t:5s} events={len(d):3d} first={d.period_end.min().date() if len(d) else None} "
              f"last={last.period_end.date() if last is not None else None} rev_ttm={last.revenue_ttm/1e9 if last is not None else np.nan:9.2f}bn "
              f"cfo={last.cfo_ttm/1e9 if last is not None else np.nan:8.2f} capex={last.capex_ttm/1e9 if last is not None else np.nan:8.2f} "
              f"gm_std8={last.gm_std8 if last is not None else np.nan:.4f}")
    panel = pd.concat(out, ignore_index=True)
    panel.to_parquet(ROOT / "data" / "staged" / "kbri_fundamentals_pit.parquet")
    return panel


if __name__ == "__main__":
    main()
