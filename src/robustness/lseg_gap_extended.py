"""Exploratory (not registered): how far does the price-analyst gap go?

Extends src/robustness/lseg_consensus.py with the checks a referee would ask for:
  1. Fama-MacBeth regressions of 12-month and 1-month returns on the gap, with controls
     (size, momentum, beta, EV/Sales, consensus growth itself, long-term growth).
  2. Non-overlapping monthly quintile portfolios on the gap.
  3. The basket-median gap as a time-series predictor of drawdowns, inside the H4 design,
     plus block-bootstrap confidence intervals for every H4 AUC.
Vendor values stay in data/licensed/; only derived statistics are written to data/outputs/.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from src.kmsi import engine as E
from src.robustness.lseg_consensus import consensus_panel

ROOT = E.ROOT
LIC = ROOT / "data" / "licensed" / "lseg"
OUT = ROOT / "data" / "outputs"
RNG = np.random.default_rng(20261113)
TEST_START = "2019-01-01"


def nw_t(x: np.ndarray, lag: int) -> tuple[float, float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    r = sm.OLS(x, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": lag})
    return float(r.params[0]), float(r.tvalues[0])


def panel() -> pd.DataFrame:
    V = pd.read_parquet(OUT / "kbri_v1.0_variables.parquet")[["date", "ticker", "g_star", "mcap_usd", "beta", "ev_sales", "revenue_usd"]]
    V["date"] = pd.to_datetime(V["date"]) + pd.offsets.MonthEnd(0)
    U = pd.read_parquet(ROOT / "data" / "staged" / "kbri_universe_monthly.parquet")[["date", "ticker", "member_value_chain"]]
    U["date"] = pd.to_datetime(U["date"]) + pd.offsets.MonthEnd(0)
    M = pd.read_parquet(ROOT / "data" / "staged" / "kbri_market_monthly.parquet")[["date", "ticker", "close"]]
    M["date"] = pd.to_datetime(M["date"]) + pd.offsets.MonthEnd(0)
    P = V.merge(U, on=["date", "ticker"], how="left").merge(consensus_panel(), on=["ticker", "date"], how="left")
    P = P.merge(M, on=["date", "ticker"], how="left").sort_values(["ticker", "date"])
    g = P.groupby("ticker")["close"]
    P["ret_fwd12"] = g.shift(-12) / P["close"] - 1
    P["ret_fwd1"] = g.shift(-1) / P["close"] - 1
    P["mom"] = g.shift(1) / g.shift(12) - 1                    # 12-1 momentum, known at t
    P["gap_fwd"] = P["g_star"] - P["cg_fwd"]
    P["log_mcap"] = np.log(P["mcap_usd"])
    vc = P[(P.member_value_chain == True) & P.g_star.notna() & P.cg_fwd.notna()].copy()  # noqa: E712
    return vc[(vc.cg_fwd.abs() < 2) & (vc.g_star.abs() < 2)]   # same screen as lseg_consensus.py


def zrank(s: pd.Series) -> pd.Series:
    r = s.rank()
    return (r - r.mean()) / r.std(ddof=0)


def fama_macbeth(df: pd.DataFrame, y: str, xs: list[str], lag: int, min_n: int = 15) -> dict:
    coefs = []
    for d, c in df.dropna(subset=[y] + xs).groupby("date"):
        if len(c) < min_n:
            continue
        lo, hi = c[y].quantile([0.01, 0.99])
        Y = c[y].clip(lo, hi)
        X = sm.add_constant(c[xs].apply(zrank))
        coefs.append(sm.OLS(Y, X).fit().params.rename(d))
    C = pd.DataFrame(coefs)
    out = {"months": int(len(C)), "avg_firms": float(df.dropna(subset=[y] + xs).groupby("date").size().loc[C.index].mean())}
    for x in xs:
        m, t = nw_t(C[x].to_numpy(), lag)
        out[x] = {"coef": round(m, 4), "t": round(t, 2)}
    return out


def quintiles_1m(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=["gap_fwd", "ret_fwd1"]).copy()
    d["q"] = d.groupby("date")["gap_fwd"].transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) if len(s) >= 15 else np.nan)
    q = d.groupby(["date", "q"])["ret_fwd1"].mean().unstack().dropna()
    ew = d.groupby("date")["ret_fwd1"].mean().reindex(q.index)
    spread = q[0] - q[4]                                        # low gap minus high gap
    m, t = nw_t(spread.to_numpy(), 3)
    a = sm.OLS(spread, sm.add_constant(ew)).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    res = {"months": int(len(q)), "mean_monthly_return_by_quintile": {f"Q{int(k)+1}": round(float(v), 4) for k, v in q.mean().items()},
           "low_minus_high_monthly": round(m, 4), "low_minus_high_t": round(t, 2),
           "low_minus_high_annualised": round(float((1 + m) ** 12 - 1), 4),
           "low_minus_high_sharpe_annual": round(float(spread.mean() / spread.std() * np.sqrt(12)), 2),
           "alpha_vs_basket_ew_monthly": round(float(a.params["const"]), 4), "alpha_t": round(float(a.tvalues["const"]), 2),
           "beta_vs_basket_ew": round(float(a.params.iloc[1]), 2)}
    for lab, lo, hi in (("2010_2018", "2010-01-01", "2018-12-31"), ("2019_2026", "2019-01-01", "2026-12-31")):
        s = spread[(spread.index >= lo) & (spread.index <= hi)]
        mm, tt = nw_t(s.to_numpy(), 3)
        res[f"low_minus_high_{lab}"] = {"monthly": round(mm, 4), "t": round(tt, 2), "months": int(len(s))}
    return res


def h4_with_gap() -> dict:
    X = pd.read_parquet(OUT / "phase8_h4_design.parquet")
    b = pd.read_csv(LIC / "robustness_lseg_basket_medians.csv", parse_dates=["date"]).set_index("date")["gap_fwd"]
    b.index = b.index + pd.offsets.MonthEnd(0)
    X["gap"] = [b.get(m + pd.offsets.MonthEnd(0), np.nan) for m in X.index]
    models = {"a_price": ["ret63", "dd_peak", "vix_pct"], "b_kmsi": ["ret63", "dd_peak", "vix_pct", "kmsi"],
              "c_kmsi_kbri": ["ret63", "dd_peak", "vix_pct", "kmsi", "kbri"], "d_price_gsadf": ["ret63", "dd_peak", "vix_pct", "gsadf"],
              "e_price_gap": ["ret63", "dd_peak", "vix_pct", "gap"], "f_price_gsadf_gap": ["ret63", "dd_peak", "vix_pct", "gsadf", "gap"]}
    X = X.dropna(subset=["gap"])
    test = X[X.index >= TEST_START].dropna(subset=["y_bin", "y_xs"])
    preds = {k: [] for k in models}
    for m in test.index:
        tr = X[X.index <= m - pd.Timedelta(days=183)].dropna(subset=["y_bin", "y_xs"])
        for k, cols in models.items():
            mu, sd = tr[cols].mean(), tr[cols].std().replace(0, 1)
            y = tr["y_bin"].astype(int)
            preds[k].append(float(LogisticRegression(C=1e6, max_iter=1000).fit((tr[cols] - mu) / sd, y)
                                  .predict_proba((X.loc[[m], cols] - mu) / sd)[0, 1]) if y.nunique() > 1 else y.mean())
    yb = test["y_bin"].astype(int).to_numpy()
    n, bl, B = len(yb), 6, 5000
    idx = []
    while len(idx) < B:
        st = RNG.integers(0, n - bl + 1, size=int(np.ceil(n / bl)))
        ix = np.concatenate([np.arange(s, s + bl) for s in st])[:n]
        if len(set(yb[ix])) == 2:
            idx.append(ix)
    out = {"test_months": int(n), "event_rate_test": round(float(yb.mean()), 3),
           "note": "Same expanding-window design and 183-day label gap as registered H4; months where the LSEG gap exists."}
    P = {k: np.array(v) for k, v in preds.items()}
    for k in models:
        boots = [roc_auc_score(yb[ix], P[k][ix]) for ix in idx]
        out[k] = {"AUC": round(float(roc_auc_score(yb, P[k])), 3),
                  "AUC_95ci_block_bootstrap": [round(float(np.percentile(boots, 2.5)), 3), round(float(np.percentile(boots, 97.5)), 3)]}
    for big, small in (("e_price_gap", "a_price"), ("f_price_gsadf_gap", "d_price_gsadf"), ("e_price_gap", "c_kmsi_kbri")):
        diffs = np.array([roc_auc_score(yb[ix], P[big][ix]) - roc_auc_score(yb[ix], P[small][ix]) for ix in idx])
        out[f"gain_{big}_vs_{small}"] = {"AUC_gain": round(float(roc_auc_score(yb, P[big]) - roc_auc_score(yb, P[small])), 3),
                                         "boot_p_no_gain": round(float((diffs <= 0).mean()), 3)}
    uni = {}
    for lab, d in (("train_2012_2018", X[X.index <= "2018-06-30"]), ("test_2019_2026", X[X.index >= TEST_START])):
        d = d.dropna(subset=["y_bin"])
        uni[lab] = {c: round(float(roc_auc_score(d["y_bin"].astype(int), d[c])), 3) for c in ["gap", "gsadf", "kbri", "kmsi"]}
    out["univariate_auc"] = uni
    out["corr_gap_gsadf"] = round(float(X[["gap", "gsadf"]].corr().iloc[0, 1]), 3)
    out["corr_gap_kbri"] = round(float(X[["gap", "kbri"]].corr().iloc[0, 1]), 3)
    return out


def main() -> dict:
    vc = panel()
    ctrl = ["log_mcap", "mom", "beta", "ev_sales"]
    res = {"note": "Exploratory, not registered, run after the registered tests. Returns are price returns from month-end closes; "
                   "regressors are within-month standardised ranks; dependent variable winsorised 1/99 within month; "
                   "Newey-West lags 11 (12-month, overlapping) and 3 (1-month).",
           "firm_months": int(len(vc)), "firms": int(vc.ticker.nunique())}
    fm12 = {"gap_only": fama_macbeth(vc, "ret_fwd12", ["gap_fwd"], 11),
            "gap_controls": fama_macbeth(vc, "ret_fwd12", ["gap_fwd"] + ctrl, 11),
            "split_gstar_consensus": fama_macbeth(vc, "ret_fwd12", ["g_star", "cg_fwd"], 11),
            "split_controls": fama_macbeth(vc, "ret_fwd12", ["g_star", "cg_fwd"] + ctrl, 11),
            "gap_plus_consensus_controls": fama_macbeth(vc, "ret_fwd12", ["gap_fwd", "cg_fwd"] + ctrl, 11),
            "gap_plus_ltg_controls": fama_macbeth(vc[vc.ltg.abs() < 1], "ret_fwd12", ["gap_fwd", "ltg"] + ctrl, 11)}
    fm1 = {"gap_only": fama_macbeth(vc, "ret_fwd1", ["gap_fwd"], 3),
           "gap_controls": fama_macbeth(vc, "ret_fwd1", ["gap_fwd"] + ctrl, 3),
           "split_controls": fama_macbeth(vc, "ret_fwd1", ["g_star", "cg_fwd"] + ctrl, 3)}
    res["fama_macbeth_12m"] = fm12
    res["fama_macbeth_1m"] = fm1
    res["quintiles_1m"] = quintiles_1m(vc)
    res["h4_with_gap"] = h4_with_gap()
    (OUT / "robustness_lseg_gap_extended.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
