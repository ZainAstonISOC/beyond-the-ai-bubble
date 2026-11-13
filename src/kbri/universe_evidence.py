"""Universe rule, condition 3: evidence that a filing names AI as a revenue source or growth driver.

For each candidate's 10-K / 20-F since fiscal 2015 the primary document is downloaded,
reduced to text, and scanned for sentences that pair an AI term with a revenue/demand
term. Output is an evidence table (filing, counts, best passages with accession
number) for a PERSON to confirm. The proposed entry filing is the first one meeting
the mechanical screen; it is not final until confirmed.
"""
from __future__ import annotations

import html
import json
import re
import time

import pandas as pd

from src.ingest.edgar import CFG, SEC_UA, STAGED
from src.ingest.fetch import fetch

ROOT = STAGED.parents[2]
AI = re.compile(r"\b(artificial intelligence|generative AI|AI|accelerated computing|machine learning|large language model|GPU)\b")
REV = re.compile(r"\b(revenue|revenues|demand|growth|sales|bookings|backlog|customers|data center)\b", re.I)
SCREEN_MIN_MENTIONS = 10       # AI-term mentions in the document
SCREEN_MIN_LINKED = 3          # sentences pairing an AI term with a revenue/demand term
# Strict screen = the spec's wording: revenue growth ATTRIBUTED to AI / data centre / accelerated computing,
# or an AI / data-centre / accelerated-computing revenue line or segment.
AI_STRICT = r"(artificial intelligence|generative AI|\bAI\b|accelerated computing|data ?cent(er|re)|GPU)"
ATTRIB = re.compile(r"(revenue|net sales|sales)[^.]{0,80}(increase|grew|growth|up \d)[^.]{0,120}(driven|due|primarily|reflect|led by|attributable)[^.]{0,120}" + AI_STRICT, re.I)
LINE = re.compile(AI_STRICT + r"[^.]{0,40}(segment|platform)? revenue[^.]{0,60}(was|were|increased|grew|of \$|totaled)", re.I)


def doc_text(raw: bytes) -> str:
    t = raw.decode("utf-8", "ignore")
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
    t = re.sub(r"(?s)<ix:header>.*?</ix:header>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t)


def scan(t: str) -> dict:
    sents = re.split(r"(?<=[.!?])\s+", t)
    linked = [s for s in sents if AI.search(s) and REV.search(s) and 40 < len(s) < 600]
    score = lambda s: len(AI.findall(s)) + len(REV.findall(s))
    best = sorted(linked, key=score, reverse=True)[:3]
    strict = [s for s in sents if (ATTRIB.search(s) or LINE.search(s)) and 40 < len(s) < 700]
    return {"ai_mentions": len(AI.findall(t)), "linked_sentences": len(linked), "best_passages": " || ".join(best),
            "strict_sentences": len(strict), "strict_passages": " || ".join(strict[:3])}


def main():
    from src.kbri.candidates import pool, ciks
    cmap = ciks()
    rows = []
    for g, ts in pool().groupby("group")["ticker"]:
        for t in ts:
            if not (STAGED / f"filings_{t}.parquet").exists():
                continue
            fl = pd.read_parquet(STAGED / f"filings_{t}.parquet")
            fl = fl[fl["form"].isin(["10-K", "20-F"]) & (fl["reportDate"] >= "2015-01-01")].sort_values("filingDate")
            for _, r in fl.iterrows():
                accn = r["accessionNumber"]
                url = f"https://www.sec.gov/Archives/edgar/data/{cmap[t]}/{accn.replace('-', '')}/{r['primaryDocument']}"
                try:
                    p = fetch("edgar_docs", f"{t}_{accn}.htm", url, ua=SEC_UA)
                    res = scan(doc_text(p.read_bytes()))
                except Exception as e:
                    res = {"ai_mentions": None, "linked_sentences": None, "best_passages": f"ERROR {e}"}
                rows.append({"group": g, "ticker": t, "form": r["form"], "filed": r["filingDate"], "period": r["reportDate"],
                             "accession": accn, "url": url, **res})
                time.sleep(0.15)
            d = pd.DataFrame([x for x in rows if x["ticker"] == t])
            print(t, d[["period", "ai_mentions", "linked_sentences"]].to_string(index=False, header=False).replace("\n", " | "))
    E = pd.DataFrame(rows)
    E["passes_screen"] = (E["ai_mentions"] >= SCREEN_MIN_MENTIONS) & (E["linked_sentences"] >= SCREEN_MIN_LINKED)
    first = E[E["passes_screen"]].sort_values("filed").groupby("ticker").head(1)
    E["passes_strict"] = E["strict_sentences"] >= 2
    first = E[E["passes_strict"] & E["passes_screen"]].sort_values("filed").groupby("ticker").head(1)
    E["proposed_entry_filing"] = E["accession"].isin(first["accession"])
    E["human_confirmed"] = ""                      # to be completed by Howden Research
    E.to_csv(ROOT / "reports" / "phase5_universe_ai_evidence.csv", index=False)
    print(first[["ticker", "filed", "period", "ai_mentions", "linked_sentences"]].to_string(index=False))


if __name__ == "__main__":
    main()
