"""SEC EDGAR ingestion for KBRI: CIK map, filing histories and XBRL company facts.

SEC fair-access policy: identify the requester in the User-Agent and stay under
10 requests per second. Raw JSON is stored unmodified with its hash in the manifest.
"""
from __future__ import annotations

import json
import time

import pandas as pd
import yaml

from .fetch import RAW, ROOT, fetch

SEC_UA = "Howden Research research@howdenresearch.uk"
CFG = yaml.safe_load((ROOT / "config" / "kbri_v1.0.yaml").read_text())
STAGED = ROOT / "data" / "staged" / "edgar"
STAGED.mkdir(parents=True, exist_ok=True)


def candidates() -> dict[str, str]:
    from src.kbri.candidates import pool
    return pool().set_index("ticker")["group"].to_dict()


def cik_map() -> dict[str, int]:
    p = fetch("edgar", "company_tickers.json", "https://www.sec.gov/files/company_tickers.json", ua=SEC_UA)
    j = json.loads(p.read_text())
    return {v["ticker"].upper(): int(v["cik_str"]) for v in j.values()}


def pull(ticker: str, cik: int) -> dict:
    c10 = f"{cik:010d}"
    sub = fetch("edgar", f"submissions_{ticker}.json", f"https://data.sec.gov/submissions/CIK{c10}.json", ua=SEC_UA)
    time.sleep(0.15)
    s = json.loads(sub.read_text())
    filings = [pd.DataFrame(s["filings"]["recent"])]
    for extra in s["filings"].get("files", []):        # older filing pages
        p = fetch("edgar", f"submissions_{ticker}_{extra['name']}", f"https://data.sec.gov/submissions/{extra['name']}", ua=SEC_UA)
        filings.append(pd.DataFrame(json.loads(p.read_text())))
        time.sleep(0.15)
    f = pd.concat(filings, ignore_index=True)
    f.to_parquet(STAGED / f"filings_{ticker}.parquet")
    facts = fetch("edgar", f"companyfacts_{ticker}.json", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c10}.json", ua=SEC_UA)
    time.sleep(0.15)
    j = json.loads(facts.read_text())
    rows = []
    for tax, concepts in j.get("facts", {}).items():
        for concept, body in concepts.items():
            for unit, obs in body.get("units", {}).items():
                for o in obs:
                    rows.append({"taxonomy": tax, "concept": concept, "unit": unit, "start": o.get("start"),
                                 "end": o.get("end"), "val": o.get("val"), "fy": o.get("fy"), "fp": o.get("fp"),
                                 "form": o.get("form"), "filed": o.get("filed"), "accn": o.get("accn"), "frame": o.get("frame")})
    df = pd.DataFrame(rows)
    for c in ("start", "end", "filed"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df.to_parquet(STAGED / f"facts_{ticker}.parquet")
    forms = f["form"].value_counts()
    return {"ticker": ticker, "cik": cik, "name": s.get("name"), "sic": s.get("sic"), "sicDescription": s.get("sicDescription"),
            "taxonomies": sorted(df["taxonomy"].unique().tolist()) if len(df) else [],
            "n_facts": len(df), "first_filed": str(df["filed"].min().date()) if len(df) else None,
            "n_10K": int(forms.get("10-K", 0)), "n_10Q": int(forms.get("10-Q", 0)), "n_20F": int(forms.get("20-F", 0)),
            "n_6K": int(forms.get("6-K", 0)), "fiscal_year_end": s.get("fiscalYearEnd")}


def main():
    from src.kbri.candidates import ciks
    cm = ciks()
    out = []
    for t, g in candidates().items():
        if (STAGED / f"facts_{t}.parquet").exists() and (STAGED / f"filings_{t}.parquet").exists():
            continue
        try:
            r = pull(t, cm[t])
        except Exception as e:
            print("FAIL", t, e)
            continue
        r["group"] = g
        out.append(r)
        print(f"{t:5s} {r['name'][:28]:28s} tax={','.join(r['taxonomies']):24s} facts={r['n_facts']:6d} first={r['first_filed']} "
              f"10K={r['n_10K']} 10Q={r['n_10Q']} 20F={r['n_20F']} FYE={r['fiscal_year_end']}")
    pd.DataFrame(out).to_csv(ROOT / "reports" / "phase5_edgar_coverage.csv", index=False)


if __name__ == "__main__":
    main()
