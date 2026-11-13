"""Extract candidate passages for the AI-disclosure condition (reading pass input).

For each candidate and each 10-K/20-F since FY2015 (cached documents), keep sentences that contain
an AI / accelerated-computing / data-centre term AND a revenue-attribution term, ranked by how
directly they attribute revenue or growth. A person (and the reading pass) judges them against the
spec wording; nothing here decides membership.
"""
import re, sys
import pandas as pd
from src.kbri.universe_evidence import doc_text
from src.ingest.fetch import RAW
ROOT = RAW.parents[1]
AI_T = re.compile(r"(artificial intelligence|generative AI|\bAI\b|accelerated computing|data ?cent(?:er|re)s?|\bGPUs?\b|\bHBM\b|AI infrastructure)", re.I)
REV_T = re.compile(r"\b(revenue|revenues|net sales|sales)\b", re.I)
ATT_T = re.compile(r"\b(increase[sd]?|grew|growth|driven|due to|primarily|demand|record|strength|led by)\b", re.I)

def score(s):
    return 3*bool(re.search(r"(driven by|due to|primarily|led by)", s, re.I)) + len(AI_T.findall(s)) + 2*bool(re.search(r"(increase|grew|growth)", s, re.I))

def main(tickers):
    E = pd.read_csv(ROOT / "reports" / "phase5_universe_ai_evidence.csv").sort_values(["ticker", "filed"])
    for t in tickers:
        print(f"\n######## {t}")
        shown = 0
        for r in E[E.ticker == t].itertuples():
            p = RAW / "edgar_docs" / f"{t}_{r.accession}.htm"
            sents = re.split(r"(?<=[.!?])\s+", doc_text(p.read_bytes()))
            hits = [s for s in sents if AI_T.search(s) and REV_T.search(s) and ATT_T.search(s) and 50 < len(s) < 500]
            hits = sorted(set(hits), key=score, reverse=True)[:2]
            if not hits:
                continue
            print(f"-- {r.form} FY{str(r.period)[:4]} filed {r.filed} {r.accession}")
            for h in hits:
                print("   *", h[:300])
            shown += 1
            if shown >= 4:
                break

if __name__ == "__main__":
    main(sys.argv[1:])
