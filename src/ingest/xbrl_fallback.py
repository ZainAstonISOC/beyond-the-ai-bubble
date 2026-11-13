"""Fallback for report filings the SEC company-facts API has not ingested.

Rule: a 10-K, 10-Q or 20-F (XBRL, filed 2010 or later) is re-parsed from the
EDGAR archive if the API holds fewer than 50 facts for its accession number.
Only non-dimensional facts are kept (the same scope as the company-facts API).
Parsed facts are appended to the staged facts file with source flag 'archive'.
"""
from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET

import pandas as pd

from .edgar import CFG, SEC_UA, STAGED, candidates
from .fetch import fetch

NS_TAX = {"us-gaap": "us-gaap", "ifrs-full": "ifrs-full", "dei": "dei", "srt": "srt"}


def instance_url(cik: int, accn: str) -> tuple[str, str]:
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}"
    p = fetch("edgar_archive", f"{accn}_index.json", f"{base}/index.json", ua=SEC_UA)
    items = [i["name"] for i in json.loads(p.read_text())["directory"]["item"]]
    xml = [n for n in items if n.endswith("_htm.xml")] or \
          [n for n in items if n.endswith(".xml") and not re.search(r"(_cal|_def|_lab|_pre|FilingSummary)", n)]
    if not xml:
        raise RuntimeError(f"no XBRL instance in {base}")
    return f"{base}/{xml[0]}", xml[0]


def parse_instance(path, accn, form, filed) -> pd.DataFrame:
    root = ET.parse(path).getroot()
    tag = lambda e: e.tag.split("}")[-1]
    nsmap = {}
    for ev, (pfx, uri) in ET.iterparse(path, events=["start-ns"]):
        nsmap[uri] = pfx
    ctx = {}
    for c in root:
        if tag(c) != "context":
            continue
        cid = c.attrib["id"]
        seg = c.find(".//{*}segment")
        if seg is not None and len(seg):
            continue                                        # dimensional: out of scope
        per = c.find("{*}period")
        inst = per.find("{*}instant")
        if inst is not None:
            ctx[cid] = (None, inst.text.strip())
        else:
            ctx[cid] = (per.find("{*}startDate").text.strip(), per.find("{*}endDate").text.strip())
    units = {}
    for u in root:
        if tag(u) != "unit":
            continue
        meas = [m.text.split(":")[-1] for m in u.iter() if tag(m) == "measure"]
        units[u.attrib["id"]] = "/".join(meas) if len(meas) <= 2 else meas[0]
    rows = []
    for e in root:
        cref = e.attrib.get("contextRef")
        if cref is None or cref not in ctx or e.text is None:
            continue
        uri = e.tag.split("}")[0].strip("{")
        tax = nsmap.get(uri, "")
        if tax not in NS_TAX:
            continue
        try:
            val = float(e.text.strip())
        except ValueError:
            continue
        s, en = ctx[cref]
        rows.append({"taxonomy": tax, "concept": tag(e), "unit": units.get(e.attrib.get("unitRef"), ""), "start": s, "end": en,
                     "val": val, "fy": None, "fp": None, "form": form, "filed": filed, "accn": accn, "frame": None})
    df = pd.DataFrame(rows)
    if len(df):
        for c in ("start", "end", "filed"):
            df[c] = pd.to_datetime(df[c], errors="coerce")
        df = df.drop_duplicates(["concept", "unit", "start", "end"])
    return df


def main():
    added = []
    tickers = [t for t in candidates() if (STAGED / f"facts_{t}.parquet").exists()]
    for t in tickers:
        ff = STAGED / f"facts_{t}.parquet"
        facts = pd.read_parquet(ff)
        fl = pd.read_parquet(STAGED / f"filings_{t}.parquet")
        fl = fl[fl["form"].isin(["10-K", "10-Q", "20-F"]) & (fl["isXBRL"] == 1) & (fl["filingDate"] >= "2010-01-01")]
        counts = facts.groupby("accn").size()
        todo = fl[fl["accessionNumber"].map(counts).fillna(0) < 50]
        if not len(todo):
            continue
        from src.kbri.candidates import ciks
        cmap = ciks()
        new = []
        for _, r in todo.iterrows():
            try:
                url, name = instance_url(cmap[t], r["accessionNumber"])
                p = fetch("edgar_archive", f"{r['accessionNumber']}_{name}", url, ua=SEC_UA)
                d = parse_instance(p, r["accessionNumber"], r["form"], r["filingDate"])
                new.append(d)
                added.append((t, r["form"], r["filingDate"], len(d)))
                print(f"{t:5s} {r['form']} {r['filingDate']} parsed {len(d)} facts")
            except Exception as e:
                print(f"{t:5s} {r['form']} {r['filingDate']} FAILED {e}")
            time.sleep(0.2)
        new = [d for d in new if len(d)]
        if new:
            nd = pd.concat(new, ignore_index=True)
            facts = facts[~facts["accn"].isin(nd["accn"].unique())]
            pd.concat([facts, nd], ignore_index=True).to_parquet(ff)
    pd.DataFrame(added, columns=["ticker", "form", "filed", "facts_parsed"]).to_csv(
        STAGED.parents[1] / ".." / "reports" / "phase5_xbrl_fallback.csv", index=False)


if __name__ == "__main__":
    main()
