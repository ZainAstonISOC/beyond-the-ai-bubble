"""Source-specific downloaders and parsers.

Each parser returns a DataFrame indexed by observation date with columns
  value      : the observation
  published  : the date the observation became public (look-ahead control)
and is written to data/staged/<series_id>.parquet.

Publication rules (spec, Data inventory):
  Cboe, Yahoo closes        same day (scores are computed after the US close)
  FRED daily series          next business day
  FRED NFCI (week to Fri)    reference date + 5 calendar days (Wednesday release)
  CFTC TFF (Tuesday data)    reference date + 3 calendar days (Friday release)
  AAII (reported Thursday)   same day
"""
from __future__ import annotations

import io
import json
import urllib.parse
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay

from .fetch import RAW, ROOT, fetch, record_local

STAGED = ROOT / "data" / "staged"
STAGED.mkdir(parents=True, exist_ok=True)
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64)"


def _stage(series_id: str, s: pd.Series, published: pd.Series | pd.DatetimeIndex, meta: dict) -> pd.DataFrame:
    df = pd.DataFrame({"value": s.astype(float)})
    df["published"] = pd.DatetimeIndex(published)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.index.name = "date"
    df.attrs = meta
    df.to_parquet(STAGED / f"{series_id}.parquet")
    (STAGED / f"{series_id}.meta.json").write_text(json.dumps(meta, indent=1))
    return df


# ---------------------------------------------------------------- Cboe
CBOE = {
    "VIX": "VIX_History.csv",
    "SKEW": "SKEW_History.csv",
    "VIX3M": "VIX3M_History.csv",
    "VVIX": "VVIX_History.csv",
    "VIX9D": "VIX9D_History.csv",
}


def cboe_index(sym: str) -> pd.DataFrame:
    url = f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{CBOE[sym]}"
    p = fetch("cboe", CBOE[sym], url)
    raw = pd.read_csv(p)
    raw.columns = [c.strip().upper() for c in raw.columns]
    d = pd.to_datetime(raw["DATE"], format="%m/%d/%Y")
    col = "CLOSE" if "CLOSE" in raw.columns else raw.columns[-1]
    s = pd.Series(pd.to_numeric(raw[col], errors="coerce").values, index=d).dropna()
    s = s[s > 0]
    return _stage(sym.lower(), s, s.index, {"source": "Cboe", "url": url, "field": col, "lag": "same day"})


def cboe_equity_pc() -> pd.DataFrame:
    url = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv"
    p = fetch("cboe", "equitypc.csv", url)
    lines = p.read_text().splitlines()
    start = next(i for i, l in enumerate(lines) if l.upper().startswith("DATE"))
    raw = pd.read_csv(io.StringIO("\n".join(lines[start:])), skipinitialspace=True)
    raw.columns = [c.strip() for c in raw.columns]
    d = pd.to_datetime(raw["DATE"], format="mixed")
    s = pd.Series(pd.to_numeric(raw["P/C Ratio"], errors="coerce").values, index=d).dropna()
    return _stage("equity_pc", s, s.index, {"source": "Cboe", "url": url, "lag": "same day", "use": "validation only"})


# ---------------------------------------------------------------- FRED
def fred(series: str, weekly_lag_days: int | None = None) -> pd.DataFrame:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    p = fetch("fred", f"{series}.csv", url)
    raw = pd.read_csv(p)
    d = pd.to_datetime(raw.iloc[:, 0])
    s = pd.Series(pd.to_numeric(raw.iloc[:, 1], errors="coerce").values, index=d).dropna()
    if weekly_lag_days is None:
        pub = s.index + BDay(1)
        lag = "next business day"
    else:
        pub = s.index + pd.Timedelta(days=weekly_lag_days)
        lag = f"+{weekly_lag_days} calendar days"
    return _stage(series.lower(), s, pub, {"source": "FRED", "url": url, "lag": lag})


# ---------------------------------------------------------------- Yahoo
def yahoo(ticker: str, field: str = "adjclose") -> pd.DataFrame:
    q = urllib.parse.quote(ticker)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{q}?period1=0&period2=4102444800&interval=1d&events=div%2Csplit"
    safe = ticker.replace("^", "IDX_").replace("=", "_")
    p = fetch("yahoo", f"{safe}.json", url, ua=BROWSER_UA)
    r = json.loads(p.read_text())["chart"]["result"][0]
    # Yahoo timestamps are exchange-open instants; convert to New York calendar date
    d = pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_convert("America/New_York").normalize().tz_localize(None)
    q0 = r["indicators"]["quote"][0]
    close = np.array(q0["close"], dtype=float)
    adj = r["indicators"].get("adjclose", [{}])[0].get("adjclose")
    vals = np.array(adj, dtype=float) if (field == "adjclose" and adj is not None) else close
    s = pd.Series(vals, index=d).dropna()
    s = s[s > 0]
    s = s[~s.index.duplicated(keep="last")]
    sid = "px_" + safe.lower()
    return _stage(sid, s, s.index, {"source": "Yahoo Finance chart API", "url": url,
                                     "field": "adjclose" if (field == "adjclose" and adj is not None) else "close",
                                     "lag": "same day"})


# ---------------------------------------------------------------- CFTC
CFTC_FILES = ["fin_fut_txt_2006_2016.zip"] + [f"fut_fin_txt_{y}.zip" for y in range(2017, 2027)]
ES_CODE = "13874A"   # E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE


def cftc_es() -> pd.DataFrame:
    frames = []
    for fname in CFTC_FILES:
        url = f"https://www.cftc.gov/files/dea/history/{fname}"
        p = fetch("cftc", fname, url)
        with zipfile.ZipFile(p) as z:
            inner = z.namelist()[0]
            df = pd.read_csv(z.open(inner), low_memory=False)
        df.columns = [c.strip() for c in df.columns]
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    code = df["CFTC_Contract_Market_Code"].astype(str).str.strip()
    es = df[code == ES_CODE].copy()
    datecol = "Report_Date_as_YYYY-MM-DD" if "Report_Date_as_YYYY-MM-DD" in es else "As_of_Date_In_Form_YYMMDD"
    es["date"] = pd.to_datetime(es[datecol])
    es = es.drop_duplicates("date").set_index("date").sort_index()
    num = lambda c: pd.to_numeric(es[c], errors="coerce")
    net = (num("Asset_Mgr_Positions_Long_All") - num("Asset_Mgr_Positions_Short_All")
           + num("Lev_Money_Positions_Long_All") - num("Lev_Money_Positions_Short_All"))
    s = (100 * net / num("Open_Interest_All")).dropna()
    _stage("cftc_es_oi", num("Open_Interest_All").dropna(), num("Open_Interest_All").dropna().index + pd.Timedelta(days=3),
           {"source": "CFTC TFF", "contract": ES_CODE, "lag": "+3 calendar days"})
    return _stage("cftc_es_net_pct_oi", s, s.index + pd.Timedelta(days=3),
                  {"source": "CFTC Traders in Financial Futures", "contract": ES_CODE,
                   "definition": "(asset manager + leveraged funds net long) / open interest, %",
                   "lag": "+3 calendar days (Friday release of Tuesday data)"})


# ---------------------------------------------------------------- AAII (manual download)
def aaii() -> pd.DataFrame:
    name = "sentiment.xls"
    record_local("aaii", name, "manual download from aaii.com (provided by Howden Research, 13 Nov 2026)")
    x = pd.read_excel(RAW / "aaii" / name, header=None)
    d = pd.to_datetime(x[0], errors="coerce", format="mixed")
    ok = d.notna() & pd.to_numeric(x[1], errors="coerce").notna()
    bull = pd.to_numeric(x.loc[ok, 1]).values
    bear = pd.to_numeric(x.loc[ok, 3]).values
    s = pd.Series(100 * (bull - bear), index=d[ok]).sort_index()
    return _stage("aaii_bull_bear", s, s.index, {"source": "AAII Sentiment Survey", "definition": "bullish % minus bearish %",
                                                 "lag": "same day (reported date)", "use": "validation only"})
