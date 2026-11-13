"""Phase 8: pre-registered outcomes (Y1-Y4) and hypothesis tests (H1-H5).

Registered design (plan v1.0, OSF osf.io/fkude). Run once, reported whatever the result.
Basket: value-chain basket where long history is needed (logged deviation); disclosure basket
reported where its history allows. KMSI v1.1. Inference: Newey-West (lag = horizon), block /
stationary bootstrap, Holm adjustment. Writes reports/phase8_hypothesis_tests.md and
data/outputs/phase8_results.json.
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

from src.kmsi import engine as E
from src.tests_stats.basket_series import basket_returns

warnings.simplefilter("ignore")
ROOT = E.ROOT
OUT = ROOT / "data" / "outputs"
RNG = np.random.default_rng(20261113)
H_DAYS = {63: 3, 126: 6, 252: 12}          # trading-day horizon -> months (Newey-West lag at monthly sampling)
TRAIN_END, TEST_START = "2018-12-31", "2019-01-01"


# ------------------------------------------------------------------ outcomes
def fwd_max_drawdown(idx: np.ndarray, h: int) -> np.ndarray:
    out = np.full(len(idx), np.nan)
    for t in range(len(idx) - h):
        w = idx[t:t + h + 1]
        out[t] = (w / np.maximum.accumulate(w)).min() - 1
    return out


def outcomes(b: pd.DataFrame, spx: pd.Series) -> pd.DataFrame:
    idx = b["index"].to_numpy()
    s = spx.reindex(b.index).ffill().to_numpy()
    Y = pd.DataFrame(index=b.index)
    for h in H_DAYS:
        Y[f"Y1_dd{h}"] = fwd_max_drawdown(idx, h)
        r_b = np.r_[idx[h:] / idx[:-h], np.full(h, np.nan)] - 1
        r_s = np.r_[s[h:] / s[:-h], np.full(h, np.nan)] - 1
        Y[f"Y2_xs{h}"] = r_b - r_s
    return Y


# ------------------------------------------------------------------ GSADF / BSADF (Phillips, Shi and Yu), ADF(0), real time
def bsadf(y: np.ndarray) -> np.ndarray:
    T = len(y)
    w0 = int(np.floor((0.01 + 1.8 / np.sqrt(T)) * T))
    dy, x = np.diff(y), y[:-1]
    c = lambda a: np.r_[0.0, np.cumsum(a)]
    Sx, Sy, Sxx, Sxy, Syy = c(x), c(dy), c(x * x), c(x * dy), c(dy * dy)
    out = np.full(T, np.nan)
    for t in range(w0, T):              # window of observations s..t-1 in the differenced series
        best = -np.inf
        for s in range(0, t - w0 + 1):
            n = t - s
            sx, sy, sxx, sxy, syy = Sx[t] - Sx[s], Sy[t] - Sy[s], Sxx[t] - Sxx[s], Sxy[t] - Sxy[s], Syy[t] - Syy[s]
            den = n * sxx - sx * sx
            if den <= 0 or n < 4:
                continue
            b = (n * sxy - sx * sy) / den
            a = (sy - b * sx) / n
            ssr = syy - 2 * a * sy - 2 * b * sxy + n * a * a + 2 * a * b * sx + b * b * sxx
            se = np.sqrt(max(ssr, 1e-18) / (n - 2) / (sxx - sx * sx / n))
            best = max(best, b / se)
        out[t] = best
    return out


# ------------------------------------------------------------------ inference helpers
def nw_mean_t(x: np.ndarray, lag: int) -> tuple[float, float]:
    x = x[np.isfinite(x)]
    m = sm.OLS(x, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": lag})
    return float(m.params[0]), float(m.pvalues[0])


def holm(pvals: dict) -> dict:
    items = sorted(((p, k) for k, p in pvals.items() if np.isfinite(p)))
    m, out, run = len(items), {}, 0.0
    for i, (p, k) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = run
    return out


# ------------------------------------------------------------------ fundamentals of a basket
def basket_fundamentals(col="member_value_chain") -> pd.DataFrame:
    """Quarterly aggregate TTM revenue, CFO, capex, RPO of members at each quarter end, plus 2-quarter-forward
    growth for the SAME members (final, restated values: these are outcomes, not predictors)."""
    P = pd.read_parquet(ROOT / "data" / "staged" / "kbri_fundamentals_pit.parquet")
    U = pd.read_parquet(ROOT / "data" / "staged" / "kbri_universe_monthly.parquet")
    D = pd.read_parquet(ROOT / "data" / "staged" / "kbri_market_monthly.parquet")[["date", "ticker", "fx_to_usd"]]
    last = P.sort_values("filed").groupby(["ticker", "period_end"]).tail(1)       # latest-filed value per period
    qs = pd.date_range("2010-03-31", "2026-09-30", freq="QE")

    byT = {t: d.sort_values("period_end") for t, d in last.groupby("ticker")}
    fxT = {t: d.sort_values("date") for t, d in D.groupby("ticker")}

    def val(t, q, item):
        d = byT.get(t)
        if d is None:
            return np.nan
        r = d[(d.period_end > q - pd.Timedelta(days=50)) & (d.period_end <= q + pd.Timedelta(days=5))]
        if not len(r) or not np.isfinite(r.iloc[-1][item]):
            return np.nan
        f = fxT.get(t)
        fx = f[f.date <= q + pd.Timedelta(days=40)]["fx_to_usd"] if f is not None else pd.Series(dtype=float)
        fx = fx.dropna()
        return float(r.iloc[-1][item]) * (float(fx.iloc[-1]) if len(fx) else 1.0)

    rows = []
    for q in qs:
        um = U[(U.date <= q) & (U.date > q - pd.Timedelta(days=40)) & U[col]]
        mem = sorted(um.ticker.unique())
        if len(mem) < 3:
            continue
        rec = {"quarter": q, "n": len(mem)}
        for item in ("revenue_ttm", "cfo_ttm", "capex_ttm", "rpo"):
            for k, qq in (("0", q), ("2", q + pd.offsets.QuarterEnd(2))):
                v = np.array([val(t, qq, item) for t in mem])
                rec[f"{item}_{k}"] = v
        for item in ("revenue_ttm", "cfo_ttm", "capex_ttm", "rpo"):
            a, b = rec.pop(f"{item}_0"), rec.pop(f"{item}_2")
            ok = np.isfinite(a) & np.isfinite(b) & (np.abs(a) > 0)
            rec[f"g2q_{item}"] = (b[ok].sum() / a[ok].sum() - 1) if ok.sum() >= 3 else np.nan
            rec[f"n_{item}"] = int(ok.sum())
        rows.append(rec)
    return pd.DataFrame(rows).set_index("quarter")


def drawdown_episodes(idx: pd.Series, thr: float) -> list:
    """(peak, trough) pairs: from a running high, a fall of at least thr before a new high is set."""
    out, hi, pk, prev, hit = [], -np.inf, None, None, False
    for t, v in idx.items():
        if v >= hi:
            if hit:
                out.append((pk, prev))
            hi, pk, hit = v, t, False
        elif v / hi - 1 <= -thr:
            hit = True
        prev = t
    if hit:
        out.append((pk, idx.index[-1]))
    return [(p, idx.loc[p:e].idxmin()) for p, e in out]


def eta2_np(y: np.ndarray, g: np.ndarray) -> float:
    m = y.mean()
    sst = ((y - m) ** 2).sum()
    if sst <= 0:
        return np.nan
    cnt = np.bincount(g)
    sums = np.bincount(g, weights=y)
    ok = cnt > 0
    return float((cnt[ok] * (sums[ok] / cnt[ok] - m) ** 2).sum() / sst)


# ------------------------------------------------------------------ main
def main():
    res, md = {}, ["# Phase 8: pre-registered hypothesis tests", "",
                   "Registration: osf.io/fkude (13 Nov 2026). Value-chain basket unless stated. KMSI v1.1. All results reported.", ""]
    km = pd.read_parquet(OUT / "kmsi_v1.1_daily.parquet")["kmsi"]
    spx = E.staged("px_idx_gspc")["value"]
    vc = basket_returns("member_value_chain")
    dc = basket_returns("member", start="2017-01-01")
    Yvc = outcomes(vc, spx)
    Yvc.join(vc).to_parquet(OUT / "phase8_outcomes_value_chain.parquet")

    # ---------------- Y3: expectations gap (realised 4-quarter revenue growth minus g*)
    V = pd.read_parquet(OUT / "kbri_v1.0_variables.parquet")
    V = V.sort_values(["ticker", "date"])
    V["rev_fwd12"] = V.groupby("ticker")["revenue_usd"].shift(-12)
    V["Y3_gap"] = (V["rev_fwd12"] / V["revenue_usd"] - 1) - V["g_star"]
    U = pd.read_parquet(ROOT / "data" / "staged" / "kbri_universe_monthly.parquet")
    V = V.merge(U[["date", "ticker", "member", "member_value_chain"]], on=["date", "ticker"], how="left")
    y3 = V[V.member_value_chain == True].groupby("date")["Y3_gap"].median()   # noqa: E712
    res["Y3"] = {"median_gap_all": float(V.loc[V.member_value_chain == True, "Y3_gap"].median()),
                 "share_months_negative": float((y3.dropna() < 0).mean())}

    # ---------------- H1: fear without fundamental deterioration
    fear = (km < 25).astype(int)
    run = fear.groupby((fear != fear.shift()).cumsum()).cumsum() * fear
    starts = run[run == 10].index          # 10th consecutive day below 25
    ep = []
    for d in starts:
        if not ep or (d - ep[-1]).days > 90:
            ep.append(d)
    ep = [d for d in ep if d >= pd.Timestamp("2010-06-30")]
    F = basket_fundamentals("member_value_chain")
    F.to_parquet(OUT / "phase8_basket_fundamentals_vc.parquet")
    eq = sorted({(pd.Timestamp(d) + pd.offsets.QuarterEnd(0)) for d in ep})
    F["episode"] = F.index.isin(eq)
    h1 = {}
    for item in ("revenue_ttm", "cfo_ttm", "capex_ttm"):
        g = F[f"g2q_{item}"]
        e, ne = g[F.episode].dropna(), g[~F.episode].dropna()
        share_fall = float((e < 0).mean()) if len(e) else np.nan
        diff = float(e.mean() - ne.mean()) if len(e) and len(ne) else np.nan
        # moving-block bootstrap (blocks of 4 quarters) of (growth, episode) pairs; one-sided p for "episode growth lower"
        allg = g.dropna()
        lab = F.loc[allg.index, "episode"].to_numpy(bool)
        vals = allg.to_numpy()
        n, bl, stat = len(vals), 4, []
        for _ in range(10000):
            st = RNG.integers(0, n - bl + 1, size=int(np.ceil(n / bl)))
            ix = np.concatenate([np.arange(s0, s0 + bl) for s0 in st])[:n]
            l, v = lab[ix], vals[ix]
            if l.sum() == 0 or (~l).sum() == 0:
                continue
            stat.append(v[l].mean() - v[~l].mean())
        stat = np.array(stat)
        p = float(((stat - diff) <= diff).mean()) if np.isfinite(diff) else np.nan
        h1[item] = {"episodes": int(len(e)), "share_episodes_falling": share_fall, "mean_diff_vs_other": diff, "p_one_sided": p}
    against_h1 = any(v["share_episodes_falling"] >= 2 / 3 for v in h1.values()) or any(v["p_one_sided"] < 0.05 and v["mean_diff_vs_other"] < 0 for v in h1.values())
    res["H1"] = {"fear_episode_starts": [str(d.date()) for d in ep], "by_item": h1, "counts_against": bool(against_h1)}

    # ---------------- H2: heterogeneous risk
    Sa = pd.read_parquet(OUT / "kbri_v1.0_company_abs.parquet")
    Sr = pd.read_parquet(OUT / "kbri_v1.0_company_rel.parquet")
    Sm = Sa.merge(U[["date", "ticker", "member_value_chain"]], on=["date", "ticker"])
    Sm = Sm[Sm.member_value_chain & Sm.kbri.notna()]
    iqr_abs = Sm.groupby("date")["kbri"].apply(lambda s: s.quantile(.75) - s.quantile(.25) if len(s) >= 8 else np.nan).dropna()
    Rr = Sr.merge(U[["date", "ticker", "member_value_chain"]], on=["date", "ticker"])
    Rr = Rr[Rr.member_value_chain & Rr.kbri.notna()]
    iqr_rel = Rr.groupby("date")["kbri"].apply(lambda s: s.quantile(.75) - s.quantile(.25) if len(s) >= 8 else np.nan).dropna()

    gcode = {g: i for i, g in enumerate(sorted(Sm["group"].unique()))}
    months = [(d["kbri"].to_numpy(float), d["group"].map(gcode).to_numpy(int)) for _, d in Sm.groupby("date")
              if len(d) >= 8 and d["group"].nunique() >= 2]
    e_obs = float(np.nanmean([eta2_np(y, g) for y, g in months]))
    perms = np.array([np.nanmean([eta2_np(y, RNG.permutation(g)) for y, g in months]) for _ in range(1000)])
    p_eta = float((perms >= e_obs).mean())
    against_h2 = (iqr_rel.mean() < 15) and (p_eta >= 0.05)
    res["H2"] = {"mean_IQR_KBRI_rel": float(iqr_rel.mean()), "mean_IQR_KBRI_abs": float(iqr_abs.mean()),
                 "mean_eta2_group": e_obs, "perm_p": p_eta, "months": len(months), "counts_against": bool(against_h2)}

    # ---------------- H3 + Y4: drawdowns of 20% or more
    idx = vc["index"]
    dd = idx / idx.cummax() - 1
    episodes = drawdown_episodes(idx, 0.20)
    dfii = E.align("dfii10", vc.index)
    baa = E.align("baa10y", vc.index)
    fac = pd.DataFrame({"mkt": spx.reindex(vc.index).ffill().pct_change(fill_method=None),
                        "dur": dfii.diff(), "cred": baa.diff(), "y": vc["ret"]}).dropna()
    h3 = []
    for p, t in episodes:
        est = fac.loc[:p].iloc[-253:-1]
        epi = fac.loc[p:t].iloc[1:]
        if len(est) < 200 or len(epi) < 5:
            continue
        b = sm.OLS(est["y"], sm.add_constant(est[["mkt", "dur", "cred"]])).fit().params
        tot = float(np.log1p(epi["y"]).sum())
        contrib = {k: float((b[k] * epi[k]).sum()) for k in ("mkt", "dur", "cred")}
        fitted = sum(contrib.values()) + b["const"] * len(epi)
        resid = float(epi["y"].sum() - fitted)
        qp, qt = p + pd.offsets.QuarterEnd(0), t + pd.offsets.QuarterEnd(0)
        rev_same = F["g2q_revenue_ttm"].get(qp - pd.offsets.QuarterEnd(1), np.nan)
        rev_next = F["g2q_revenue_ttm"].get(qt, np.nan)
        rpo_next = F["g2q_rpo"].get(qt, np.nan)
        h3.append({"peak": str(p.date()), "trough": str(t.date()), "drawdown": float(idx[t] / idx[p] - 1),
                   "market_part": contrib["mkt"], "duration_part": contrib["dur"], "credit_part": contrib["cred"],
                   "ai_specific_residual": resid, "residual_share_of_fall": resid / epi["y"].sum() if epi["y"].sum() != 0 else np.nan,
                   "rev_growth_2q_around_peak": rev_same, "rev_growth_2q_after_trough": rev_next, "rpo_growth_2q_after_trough": rpo_next})
    neg_fund = [((e["rev_growth_2q_after_trough"] < 0) and (not np.isfinite(e["rpo_growth_2q_after_trough"]) or e["rpo_growth_2q_after_trough"] < 0)) for e in h3]
    resid_major = [e["residual_share_of_fall"] > 0.5 for e in h3]
    against_h3 = bool(len(h3) and np.mean(neg_fund) > 0.5 and np.mean(resid_major) > 0.5)
    res["H3"] = {"episodes": h3, "counts_against": against_h3}

    # ---------------- H4: framework vs price-only and GSADF, out of sample
    me = vc.resample("BME").last().index
    me = me[me >= "2012-01-31"]
    Bk = pd.read_parquet(OUT / "kbri_v1.0_basket_value_chain.parquet")["kbri_basket"]
    vixp = E.rolling_percentile(E.align("vix", E.calendar()), 1260, 504)
    lm = np.log(vc["index"].resample("BME").last())
    bs = pd.Series(bsadf(lm.to_numpy()), index=lm.index)
    X = pd.DataFrame(index=me)
    X["ret63"] = [vc["index"].asof(m) / vc["index"].asof(m - pd.Timedelta(days=91)) - 1 for m in me]
    X["dd_peak"] = [dd.asof(m) for m in me]
    X["vix_pct"] = [vixp.asof(m) for m in me]
    X["kmsi"] = [km.asof(m) for m in me]
    X["kbri"] = Bk.reindex(me)
    X["gsadf"] = bs.reindex(me)
    X["y_bin"] = [(Yvc["Y1_dd126"].asof(m) <= -0.15) if np.isfinite(Yvc["Y1_dd126"].asof(m)) else np.nan for m in me]
    X["y_xs"] = [Yvc["Y2_xs126"].asof(m) for m in me]
    X = X.dropna(subset=["ret63", "dd_peak", "vix_pct", "kmsi", "kbri", "gsadf"])
    models = {"a_price": ["ret63", "dd_peak", "vix_pct"], "b_kmsi": ["ret63", "dd_peak", "vix_pct", "kmsi"],
              "c_kmsi_kbri": ["ret63", "dd_peak", "vix_pct", "kmsi", "kbri"], "d_price_gsadf": ["ret63", "dd_peak", "vix_pct", "gsadf"]}
    test = X[(X.index >= TEST_START)].dropna(subset=["y_bin", "y_xs"])
    preds = {k: [] for k in models}
    preds_r = {k: [] for k in models}
    hist_mean = []
    for m in test.index:
        tr = X[(X.index <= m - pd.Timedelta(days=183))].dropna(subset=["y_bin", "y_xs"])   # label window closed before m
        for k, cols in models.items():
            mu, sd = tr[cols].mean(), tr[cols].std().replace(0, 1)
            Z, z = (tr[cols] - mu) / sd, (X.loc[[m], cols] - mu) / sd
            y = tr["y_bin"].astype(int)
            if y.nunique() < 2:
                preds[k].append(y.mean())
            else:
                preds[k].append(float(LogisticRegression(C=1e6, max_iter=1000).fit(Z, y).predict_proba(z)[0, 1]))
            ols = sm.OLS(tr["y_xs"], sm.add_constant(Z)).fit()
            preds_r[k].append(float(np.asarray(ols.predict(sm.add_constant(z, has_constant="add")))[0]))
        hist_mean.append(float(tr["y_xs"].mean()))
    yb, yx = test["y_bin"].astype(int).to_numpy(), test["y_xs"].to_numpy()
    h4 = {"test_months": int(len(test)), "event_rate_test": float(yb.mean()),
          "train_months_first": int(len(X[X.index <= pd.Timestamp(TEST_START) - pd.Timedelta(days=183)].dropna(subset=['y_bin'])))}
    for k in models:
        p = np.array(preds[k])
        e = yx - np.array(preds_r[k])
        e0 = yx - np.array(hist_mean)
        h4[k] = {"AUC": float(roc_auc_score(yb, p)) if len(set(yb)) > 1 else np.nan, "Brier": float(brier_score_loss(yb, p)),
                 "R2_oos_vs_hist_mean": float(1 - (e ** 2).sum() / (e0 ** 2).sum())}

    def clark_west(small, big):
        es, eb = yx - np.array(preds_r[small]), yx - np.array(preds_r[big])
        f = es ** 2 - (eb ** 2 - (np.array(preds_r[small]) - np.array(preds_r[big])) ** 2)
        m_, p2 = nw_mean_t(f, 6)
        return float(p2 / 2 if m_ > 0 else 1 - p2 / 2)

    def auc_boot(a, b, B=5000):
        pa, pb = np.array(preds[a]), np.array(preds[b])
        obs = roc_auc_score(yb, pb) - roc_auc_score(yb, pa)
        n, ge = len(yb), 0
        bl = 6
        cnt = 0
        for _ in range(B):
            st = RNG.integers(0, n - bl + 1, size=int(np.ceil(n / bl)))
            ix = np.concatenate([np.arange(s, s + bl) for s in st])[:n]
            if len(set(yb[ix])) < 2:
                continue
            cnt += 1
            ge += (roc_auc_score(yb[ix], pb[ix]) - roc_auc_score(yb[ix], pa[ix])) <= 0
        return float(obs), float(ge / max(cnt, 1))

    gain_ca, p_ca = auc_boot("a_price", "c_kmsi_kbri")
    gain_cd, p_cd = auc_boot("d_price_gsadf", "c_kmsi_kbri")
    cw_ac, cw_ab = clark_west("a_price", "c_kmsi_kbri"), clark_west("a_price", "b_kmsi")
    dm_e = (yx - np.array(preds_r["d_price_gsadf"])) ** 2 - (yx - np.array(preds_r["c_kmsi_kbri"])) ** 2
    dm_m, dm_p = nw_mean_t(dm_e, 6)
    h4.update({"AUC_gain_c_vs_a": gain_ca, "AUC_gain_c_vs_a_boot_p": p_ca, "AUC_gain_c_vs_gsadf": gain_cd,
               "AUC_gain_c_vs_gsadf_boot_p": p_cd, "ClarkWest_p_a_vs_c": cw_ac, "ClarkWest_p_a_vs_b": cw_ab,
               "DM_p_c_vs_gsadf_one_sided": float(dm_p / 2 if dm_m > 0 else 1 - dm_p / 2)})
    against_h4 = (gain_ca < 0.03) and (cw_ac > 0.10)
    h4["counts_against"] = bool(against_h4)
    h4["counts_against_vs_gsadf"] = bool((gain_cd < 0.03) and (h4["DM_p_c_vs_gsadf_one_sided"] > 0.10))
    res["H4"] = h4
    X.to_parquet(OUT / "phase8_h4_design.parquet")

    # ---------------- H5
    s2 = pd.read_csv(OUT / "kcei_v1.0_company_scope2.csv")
    sc = pd.read_csv(OUT / "kcei_v1.0_scenarios_us.csv")
    st = pd.read_csv(OUT / "kcei_v1.0_operator_stress.csv")
    opp = sc.groupby("scenario")["incremental_TWh_vs_2023"].first().to_dict()
    risk = st[st.utilisation_cut == 0.4].set_index("ticker")["ppe_idle_at_cut"].sum()
    msft = {f"{e} {p}": v for e, p, v in s2[["entity", "period", "accounting_gap_share"]].itertuples(index=False)}
    res["H5"] = {"incremental_load_TWh_by_scenario": opp, "idle_ppe_usd_at_40pct_cut_specialists": float(risk),
                 "scope2_gap_by_entity_period": msft, "counts_against": bool(min(opp.values()) <= 0 or risk <= 0)}

    # ---------------- Holm
    pv = {"H1_revenue": h1["revenue_ttm"]["p_one_sided"], "H1_cfo": h1["cfo_ttm"]["p_one_sided"], "H1_capex": h1["capex_ttm"]["p_one_sided"],
          "H2_eta2_perm": p_eta, "H4_AUC_c_vs_a": p_ca, "H4_CW_a_vs_c": cw_ac, "H4_AUC_c_vs_gsadf": p_cd,
          "H4_DM_c_vs_gsadf": h4["DM_p_c_vs_gsadf_one_sided"]}
    res["holm_adjusted"] = holm(pv)
    res["raw_p"] = pv

    # disclosure basket descriptive (2024+)
    if len(dc):
        ddc = dc["index"] / dc["index"].cummax() - 1
        res["disclosure_basket"] = {"start": str(dc.index.min().date()), "max_drawdown_since_2024": float(ddc.loc["2024":].min()),
                                    "trough_date": str(ddc.loc["2024":].idxmin().date())}
    (OUT / "phase8_results.json").write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    r = main()
    print(json.dumps(r, indent=1, default=str)[:6000])
