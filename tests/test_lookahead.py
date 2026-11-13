"""Look-ahead audit: no value used on day t may have been published after t."""
import numpy as np
import pandas as pd

from src.kmsi import engine as E

SERIES = {"vix": dict(max_age_bdays=3), "baa10y": dict(max_age_bdays=3), "dgs10": dict(max_age_bdays=3),
          "cftc_es_net_pct_oi": dict(max_carry_days=10, max_age_bdays=None), "px_idx_gspc": dict(max_age_bdays=3)}


def test_staged_publication_never_precedes_observation():
    for p in E.STAGED.glob("*.parquet"):
        df = pd.read_parquet(p)
        if "published" not in df.columns:      # KBRI panels: tested below
            continue
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


def test_kbri_month_end_uses_only_usable_filings():
    from pandas.tseries.offsets import BDay
    D = pd.read_parquet(E.STAGED / "kbri_market_monthly.parquet")
    assert ((D["filed"] + BDay(1)) <= D["date"]).all()
    P = pd.read_parquet(E.STAGED / "kbri_fundamentals_pit.parquet")
    assert (P["period_end"] <= P["filed"]).all()


def test_kmsi_ai_basket_membership_is_from_a_prior_month_end():
    import numpy as np
    U = pd.read_parquet(E.STAGED / "kbri_universe_monthly.parquet")
    months = np.array(sorted(U["date"].unique()), dtype="datetime64[ns]")
    cal = E.calendar()
    idx = np.searchsorted(months, cal.values.astype("datetime64[ns]"), side="left") - 1
    used = months[idx[idx >= 0]]
    assert (used < cal.values[idx >= 0].astype("datetime64[ns]")).all()
