"""Look-ahead audit: no value used on day t may have been published after t."""
import numpy as np
import pandas as pd

from src.kmsi import engine as E

SERIES = {"vix": dict(max_age_bdays=3), "baa10y": dict(max_age_bdays=3), "dgs10": dict(max_age_bdays=3),
          "cftc_es_net_pct_oi": dict(max_carry_days=10, max_age_bdays=None), "px_idx_gspc": dict(max_age_bdays=3)}


def test_staged_publication_never_precedes_observation():
    for p in E.STAGED.glob("*.parquet"):
        df = pd.read_parquet(p)
        assert (df["published"] >= df.index).all(), p.stem


def test_aligned_values_were_public_on_use_date():
    cal = E.calendar()
    rng = np.random.default_rng(7)
    for sid, kw in SERIES.items():
        s = E.align(sid, cal, **kw)
        df = E.staged(sid).dropna(subset=["value"])
        for t in rng.choice(cal[s.notna().to_numpy()], 300, replace=False):
            t = pd.Timestamp(t)
            known = df[df["published"] <= t]
            assert len(known), (sid, t)
            latest = known.sort_values(["published"]).iloc[-1]["value"]
            assert s.loc[t] == latest, (sid, t)


def test_fred_daily_lags_one_business_day():
    cal = E.calendar()
    s = E.align("baa10y", cal)
    raw = E.staged("baa10y")["value"]
    t = pd.Timestamp("2020-03-18")
    assert s.loc[t] == raw.loc[:pd.Timestamp("2020-03-17")].iloc[-1]
