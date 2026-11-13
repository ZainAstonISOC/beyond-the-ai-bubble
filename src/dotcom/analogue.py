"""Dot-com analogue (index and industry level, 1996-2026). Reported separately; never spliced onto KBRI.

Series:
  - Shiller CAPE and excess CAPE yield (ECY), monthly
  - Nasdaq-100 and PHLX Semiconductor distance from 200-day average; Nasdaq-100 63-day realised volatility
  - Damodaran industry EV/Sales (Jan vintages 1999-2020 and current): semiconductors, software, computers,
    telecom equipment, internet / information services
Each series is also expressed relative to its value at the dot-com peak (March 2000; Jan 2000 for Damodaran).
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from src.ingest.fetch import fetch, ROOT
from src.kmsi import engine as E

OUT = ROOT / "data" / "outputs"
IND = {
    "semiconductors": r"^semiconductor(?!.*equip)",
    "semiconductor equipment": r"semiconductor equip",
    "software": r"software|computer software",
    "computers and peripherals": r"computers?/peripherals|computer hardware|computers & peripherals",
    "telecom equipment": r"telecom\.? equipment|telecommunications equipment",
    "internet and information services": r"internet|information services",
}


def damodaran_evs():
    vintages = [f"{y:02d}" for y in list(range(99, 100)) + list(range(0, 21))]
    rows = []
    files = [(f"psdata{v}.xls", f"https://pages.stern.nyu.edu/~adamodar/pc/archives/psdata{v}.xls", 1900 + int(v) if v == "99" else 2000 + int(v)) for v in vintages]
    files.append(("psdata_current.xls", "https://pages.stern.nyu.edu/~adamodar/pc/datasets/psdata.xls", 2026))
    for name, url, year in files:
        try:
            p = fetch("damodaran", name, url)
            sheets = pd.read_excel(p, header=None, sheet_name=None)
        except Exception as e:
            print("skip", name, e)
            continue
        x, hdr = None, None
        for sh in sheets.values():          # data sit on the sheet whose header row names the industry
            h = next((i for i in range(min(15, len(sh))) if any("industry" in str(c).lower() for c in sh.iloc[i])
                      and any(re.search(r"(EV|Value)\s*/\s*Sales", str(c), re.I) for c in sh.iloc[i])), None)
            if h is not None:
                x, hdr = sh, h
                break
        if x is None:
            print("no EV/Sales table", name)
            continue
        cols = [str(c).strip() for c in x.iloc[hdr]]
        ev = [j for j, c in enumerate(cols) if re.search(r"(EV|Value)\s*/\s*Sales", c, re.I) and "trailing" not in c.lower()]
        if not ev:
            continue
        body = x.iloc[hdr + 1:, :]
        ind = pd.Series([str(c).strip().lower() for c in body.iloc[:, 0]], index=body.index)
        for lab, pat in IND.items():
            hit = body[ind.str.contains(pat, regex=True)]
            if len(hit):
                vals = pd.to_numeric(hit.iloc[:, ev[0]], errors="coerce").dropna()
                if len(vals):
                    rows.append({"vintage_year": year, "industry": lab, "ev_sales": float(vals.mean()),
                                 "matched": "; ".join(str(c).strip() for c in hit.iloc[:, 0])[:120]})
    return pd.DataFrame(rows)


def shiller():
    p = fetch("shiller", "ie_data.xls", "http://www.econ.yale.edu/~shiller/data/ie_data.xls")
    x = pd.read_excel(p, sheet_name="Data", header=None)
    hdr = next(i for i in range(15) if str(x.iloc[i, 0]).strip() == "Date")
    # header spans three rows: join them per column ("Excess" / "CAPE" / "Yield")
    cols = [" ".join(str(x.iloc[r, j]).strip() for r in range(hdr - 2, hdr + 1) if str(x.iloc[r, j]) != "nan") for j in range(x.shape[1])]
    body = x.iloc[hdr + 1:].copy()
    body.columns = range(body.shape[1])
    date = pd.to_numeric(body[0], errors="coerce")
    cape_j = next(j for j, c in enumerate(cols) if c.split()[-1:] == ["CAPE"] and "TR" not in c)
    ecy_j = next((j for j, c in enumerate(cols) if c.lower().startswith("excess cape")), None)
    y, m = np.floor(date), np.round((date - np.floor(date)) * 100)
    d = pd.to_datetime(dict(year=y.fillna(1900).astype(int), month=m.fillna(1).clip(1, 12).astype(int), day=1), errors="coerce") + pd.offsets.MonthEnd(0)
    S = pd.DataFrame({"cape": pd.to_numeric(body[cape_j], errors="coerce").values,
                      "ecy": pd.to_numeric(body[ecy_j], errors="coerce").values if ecy_j is not None else np.nan}, index=d.values)
    return S[S.index.notna()].dropna(how="all")


def market():
    cal = E.calendar()
    a = lambda s: E.align(s, cal)
    ndx, sox = a("px_idx_ndx"), a("px_idx_sox")
    df = pd.DataFrame({
        "ndx_vs_sma200": ndx / ndx.rolling(200).mean() - 1,
        "sox_vs_sma200": sox / sox.rolling(200).mean() - 1,
        "ndx_rv63": np.log(ndx).diff().rolling(63).std() * np.sqrt(252),
    })
    return df.resample("ME").last()


def main():
    M = market().join(shiller(), how="left")
    M = M[M.index >= "1996-01-01"]
    peak = M.loc["2000-03-31"]
    for c in ["cape", "ndx_vs_sma200", "sox_vs_sma200", "ndx_rv63"]:
        M[f"{c}_vs_mar2000"] = M[c] / peak[c]
    M.to_csv(OUT / "dotcom_analogue_monthly.csv", float_format="%.5f")
    D = damodaran_evs()
    if len(D):
        base = D[D.vintage_year == 2000].set_index("industry")["ev_sales"]
        D["vs_jan2000"] = D.apply(lambda r: r.ev_sales / base.get(r.industry, np.nan), axis=1)
        D.to_csv(OUT / "dotcom_damodaran_ev_sales.csv", index=False)
    return M, D


if __name__ == "__main__":
    M, D = main()
    print(M.loc[["2000-03-31", "2007-10-31", "2021-12-31", "2024-12-31", "2026-10-31"], ["cape", "ecy", "ndx_vs_sma200", "sox_vs_sma200", "ndx_rv63"]].round(3))
    if len(D):
        print(D.pivot_table(index="vintage_year", columns="industry", values="ev_sales").loc[[1999, 2000, 2001, 2002, 2010, 2020, 2026]].round(2))
