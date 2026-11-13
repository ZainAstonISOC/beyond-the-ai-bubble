"""Rule-based candidate pool: SIC filers listed on NYSE/Nasdaq, screened on size.

Size pre-screen: market cap >= 80% of the threshold ($8bn; $1.6bn for specialist) at any
year-end 2010-2025 or at the latest month-end, using SEC frames (cover-page shares) and
Yahoo split-adjusted closes. The exact monthly test runs later in the full pipeline.
"""
import json, re, time, urllib.request
import numpy as np, pandas as pd, yaml
from src.ingest.fetch import ROOT, fetch
from src.ingest import sources as S
UA = "Howden Research research@howdenresearch.uk"
CFG = yaml.safe_load((ROOT / "config" / "kbri_v1.0.yaml").read_text())
PR = CFG["pool_rules"]


def ticker_map():
    j = json.loads(fetch("edgar", "company_tickers_exchange.json", "https://www.sec.gov/files/company_tickers_exchange.json", ua=UA).read_text())
    m = {}
    for cik, name, tkr, ex in j["data"]:
        if ex not in PR["exchanges"] or tkr is None:
            continue
        # prefer the common-share ticker (no preferred/warrant suffix, shortest)
        if cik not in m or ("-" in m[cik][0] and "-" not in tkr) or (("-" in m[cik][0]) == ("-" in tkr) and len(tkr) < len(m[cik][0])):
            m[cik] = (tkr, name)
    return m


def frames():
    out = []
    periods = [f"CY{y}Q4I" for y in range(2010, 2026)] + ["CY2026Q2I"]
    for p in periods:
        f = fetch("edgar_frames", f"shares_{p}.json", f"https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/{p}.json", ua=UA)
        for d in json.loads(f.read_text())["data"]:
            out.append({"cik": d["cik"], "end": d["end"], "shares": d["val"], "period": p})
        time.sleep(0.15)
    df = pd.DataFrame(out)
    df["end"] = pd.to_datetime(df["end"])
    return df


def diluted_frames():
    out = []
    for y in range(2010, 2026):
        p = f"CY{y}"
        f = fetch("edgar_frames", f"diluted_{p}.json", f"https://data.sec.gov/api/xbrl/frames/us-gaap/WeightedAverageNumberOfDilutedSharesOutstanding/shares/{p}.json", ua=UA)
        for d in json.loads(f.read_text())["data"]:
            out.append({"cik": d["cik"], "end": d["end"], "shares": d["val"]})
        time.sleep(0.15)
    df = pd.DataFrame(out)
    df["end"] = pd.to_datetime(df["end"])
    return df


def assets_frames():
    out = []
    for y in list(range(2010, 2026)):
        p = f"CY{y}Q4I"
        f = fetch("edgar_frames", f"assets_{p}.json", f"https://data.sec.gov/api/xbrl/frames/us-gaap/Assets/USD/{p}.json", ua=UA)
        for d in json.loads(f.read_text())["data"]:
            out.append({"cik": d["cik"], "end": d["end"], "assets": d["val"]})
        time.sleep(0.15)
    df = pd.DataFrame(out)
    df["end"] = pd.to_datetime(df["end"])
    return df


MAX_MCAP_TO_ASSETS = 100      # plausibility bound: rejects mis-tagged share counts and unmatched reverse splits


def main():
    sic = {int(k): v for k, v in json.loads((ROOT / "data" / "staged" / "pool_sic_ciks.json").read_text()).items()}
    tm = ticker_map()
    cands = {}
    for cik, s in sic.items():
        if cik not in tm:
            continue
        tkr, name = tm[cik]
        if s == PR["reit_sic"] and not re.search(PR["reit_name_pattern"], name):
            continue
        cands[cik] = (tkr, name, s)
    amzn = [c for c, (t, n) in tm.items() if t == "AMZN"][0]
    cands[amzn] = ("AMZN", tm[amzn][1], 5961)
    F = frames()
    F = F[F["cik"].isin(cands)]
    global DIL
    DIL = diluted_frames()
    DIL = DIL[DIL["cik"].isin(cands)]
    AS = assets_frames()
    AS = AS[AS["cik"].isin(cands)].sort_values("end")
    rows = []
    for cik, (tkr, name, s) in cands.items():
        try:
            cached = ROOT / "data" / "staged" / f"px_{tkr.replace('^','IDX_').replace('=','_').lower()}.parquet"
            px = pd.read_parquet(cached)["value"] if cached.exists() else S.yahoo(tkr, "close")["value"]
        except Exception as e:
            rows.append({"cik": cik, "ticker": tkr, "name": name, "sic": s, "max_mcap": np.nan, "note": f"no price: {e}"[:80]})
            continue
        raw = json.loads((ROOT / "data" / "raw" / "yahoo" / f"{tkr.replace('^','IDX_').replace('=','_')}.json").read_text())["chart"]["result"][0]
        spl = raw.get("events", {}).get("splits", {})
        spl = pd.Series({pd.to_datetime(v["date"], unit="s"): v["numerator"] / v["denominator"] for v in spl.values()}) if spl else pd.Series(dtype=float)
        mc = []
        Fc = F[F["cik"] == cik].sort_values("end").copy()
        if len(Fc) >= 3:     # robust to single mis-tagged filings (e.g. a 1000x share count)
            Fc["shares"] = Fc["shares"].rolling(3, center=True, min_periods=1).median()
        if not len(Fc):      # multi-class filers: fall back to annual diluted weighted-average shares
            Fc = DIL[DIL["cik"] == cik]
        for _, f in Fc.iterrows():
            c = px.loc[:f["end"]]
            if not len(c) or (f["end"] - c.index[-1]).days > 10:
                continue
            fac = float(spl[spl.index > f["end"]].prod()) if len(spl) else 1.0
            m = c.iloc[-1] * f["shares"] * fac
            a = AS[(AS["cik"] == cik) & (AS["end"] <= f["end"] + pd.Timedelta(days=200))]
            if not len(a) or m / a["assets"].iloc[-1] > MAX_MCAP_TO_ASSETS:
                continue
            mc.append(m)
        rows.append({"cik": cik, "ticker": tkr, "name": name, "sic": s, "max_mcap": max(mc) if mc else np.nan,
                     "first_px": px.index.min().date(), "note": "" if mc else "no shares frame"})
    P = pd.DataFrame(rows)
    P.to_csv(ROOT / "reports" / "pool_size_screen.csv", index=False)
    print(len(P), "screened;", (P.max_mcap >= 8e9).sum(), ">= $8bn;", P.note.str.startswith("no").sum(), "without price/shares")


if __name__ == "__main__":
    main()
