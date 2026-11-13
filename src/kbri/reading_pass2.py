"""Reading-pass input for the rule-based pool: earliest and latest qualifying revenue-attribution passages."""
import re, sys
import pandas as pd
from src.kbri.universe_evidence import doc_text
from src.ingest.fetch import RAW
ROOT = RAW.parents[1]
AI = re.compile(r"(artificial intelligence|generative AI|\bAI\b|accelerated computing|AI infrastructure|AI data cent)", re.I)
GROW = re.compile(r"(revenue|revenues|net sales|sales)[^.]{0,120}(increase|grew|growth|higher)|(increase|growth|higher)[^.]{0,60}(revenue|net sales|sales)", re.I)
BAD = re.compile(r"(\bmay\b|\bcould\b|\bmight\b|risk|uncertain|if we|cyber|security incident|ethical|regulat)", re.I)

def hits(t, acc):
    s = re.split(r"(?<=[.!?])\s+", doc_text((RAW / "edgar_docs" / f"{t}_{acc}.htm").read_bytes()))
    out = []
    for i, x in enumerate(s):
        if GROW.search(x) and len(x) < 500:
            w = x if AI.search(x) else (" ".join(s[i:i + 2]) if i + 1 < len(s) and AI.search(s[i + 1]) and len(s[i + 1]) < 400 else None)
            if w and not BAD.search(w):
                out.append(w)
    return list(dict.fromkeys(out))

def main(tickers):
    E = pd.read_csv(ROOT / "reports" / "phase5_universe_ai_evidence.csv").sort_values(["ticker", "filed"])
    for t in tickers:
        rows = [(r, hits(t, r.accession)) for r in E[E.ticker == t].itertuples()]
        q = [(r, h) for r, h in rows if h]
        if not q:
            print(f"## {t}: none"); continue
        r, h = q[0]
        print(f"## {t}: first FY{str(r.period)[:4]} filed {r.filed} ({len(q)} filings w/ hits)  * {h[0][:260]}")
        if len(q) > 1:
            r2, h2 = q[-1]; print(f"     latest FY{str(r2.period)[:4]}: {h2[0][:200]}")

if __name__ == "__main__":
    main(sys.argv[1:])
