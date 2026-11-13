"""Phase 4: KMSI v1.0 validation suite (criteria pre-registered in the spec).

Writes reports/phase4_kmsi_validation.md and data/outputs/kmsi_v1.0_validation.json.
Results are reported as computed; nothing here feeds back into parameters.
"""
from __future__ import annotations

import copy
import json
import subprocess
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.kmsi import engine as E

warnings.simplefilter("ignore")
ROOT = E.ROOT
REPORT = ROOT / "reports" / f"phase4_kmsi_v{E.VERSION}_validation.md"


def regimes(k: pd.Series, cfg) -> pd.Series:
    return pd.Series([E.regime(x, cfg) for x in k], index=k.index)


def agreement(a: pd.Series, b: pd.Series, cfg) -> float:
    m = a.notna() & b.notna()
    return float((regimes(a[m], cfg) == regimes(b[m], cfg)).mean())


def kmsi_with(cfg, raw, transform="percentile"):
    sub = E.score(raw, cfg, transform)
    return E.aggregate(sub, cfg)[1]


def main():
    cfg, sha = E.load_cfg()
    base = E.run(write=True)
    raw, comps, res = base["raw"], base["components"], base["result"]
    k = res["kmsi"]
    out, rows = {}, []

    # 1 convergent validity
    k20 = k.rolling(20, min_periods=20).mean()
    def weekly_corr(sid, lag_pub=True):
        df = E.staged(sid)
        s = df["value"].copy()
        s.index = pd.DatetimeIndex(df["published"]) if lag_pub else df.index
        s = s[~s.index.duplicated(keep="last")]
        x = k20.reindex(s.index, method="ffill")
        m = x.notna() & s.notna()
        return float(np.corrcoef(x[m], s[m])[0, 1]), int(m.sum()), str(s[m].index.min().date()), str(s[m].index.max().date())
    c_nfci = weekly_corr("nfci")
    c_pc = weekly_corr("equity_pc")
    c_aaii = weekly_corr("aaii_bull_bear")
    signs_ok = c_nfci[0] < 0 and c_pc[0] < 0 and c_aaii[0] > 0
    p1 = signs_ok and abs(c_nfci[0]) >= 0.4
    out["convergent"] = {"nfci": c_nfci, "equity_pc": c_pc, "aaii_bull_bear": c_aaii, "pass": p1}
    rows.append(("Convergent validity",
                 f"20-day KMSI vs NFCI r = {c_nfci[0]:.2f} (n={c_nfci[1]}); vs equity put/call r = {c_pc[0]:.2f} (n={c_pc[1]}); "
                 f"vs AAII bull-bear r = {c_aaii[0]:.2f} (n={c_aaii[1]})",
                 "Expected sign on all three; abs(r) with NFCI >= 0.4", p1))

    # 2 discriminant validity
    vix_pct = E.rolling_percentile(raw["vix"], cfg["normalisation"]["window_days"], cfg["normalisation"]["min_obs"])
    spx = E.align("px_idx_gspc", k.index)
    X = pd.DataFrame({"ret21": spx / spx.shift(21) - 1, "vix_pct": vix_pct})
    d = pd.concat([k, X], axis=1).dropna()
    r2 = float(sm.OLS(d.iloc[:, 0], sm.add_constant(d[["ret21", "vix_pct"]])).fit().rsquared)
    p2 = r2 < 0.80
    out["discriminant"] = {"r2": r2, "n": len(d), "pass": p2}
    rows.append(("Discriminant validity", f"R squared of KMSI on 21-day S&P 500 return and VIX percentile = {r2:.3f} (n={len(d)})",
                 "R squared < 0.80", p2))

    # 3 effective dimension
    cc = comps.dropna()
    C = np.corrcoef(cc.T.values)
    lam = np.sort(np.linalg.eigvalsh(C))[::-1]
    eff = float(lam.sum() ** 2 / (lam ** 2).sum())
    out["effective_dimension"] = {"eff_n": eff, "pc1_share": float(lam[0] / lam.sum()), "eigen": lam.tolist(),
                                  "sample": [str(cc.index.min().date()), str(cc.index.max().date()), len(cc)],
                                  "corr": pd.DataFrame(C, index=cc.columns, columns=cc.columns).round(2).to_dict()}
    rows.append(("Effective dimension", f"Effective number of signals = {eff:.2f} of 8; first principal component explains "
                 f"{100 * lam[0] / lam.sum():.0f}% (complete cases {cc.index.min().date()} to {cc.index.max().date()})",
                 "Reported, no pass/fail. Below 2 = describe KMSI as mainly one factor", None))

    # 4 ablation
    abl = {}
    for name in cfg["components"]:
        c2 = copy.deepcopy(cfg)
        del c2["components"][name]
        kk = E.aggregate(base["sub"], c2)[1]
        m = k.notna() & kk.notna()
        abl[name] = float(np.corrcoef(k[m], kk[m])[0, 1])
    redundant = [n for n, r in abl.items() if r > 0.98]
    out["ablation"] = {"corr_without": abl, "redundant": redundant}
    rows.append(("Ablation", "Correlation with full KMSI when each is removed: " +
                 "; ".join(f"{n} {r:.3f}" for n, r in abl.items()),
                 "Flag any > 0.98 as redundant", None if not redundant else f"Redundant: {', '.join(redundant)}"))

    # 5 weight sensitivity
    names = list(cfg["components"])
    def scheme(over):
        rest = [n for n in names if n not in over]
        left = 1 - sum(over.values())
        return {**over, **{n: left / len(rest) for n in rest}}
    schemes = {"equal": {n: 1 / 8 for n in names},
               "risk_heavy": scheme({"volatility": 0.25, "credit": 0.25}),
               "behaviour_heavy": scheme({"positioning": 0.2, "options": 0.2, "breadth": 0.2})}
    ws = {}
    for nm, w in schemes.items():
        c2 = copy.deepcopy(cfg)
        for n in names:
            c2["components"][n]["weight"] = w[n]
        ws[nm] = agreement(k, E.aggregate(base["sub"], c2)[1], cfg)
    p5 = all(v >= 0.80 for v in ws.values())
    out["weights"] = {"agreement": ws, "pass": p5}
    rows.append(("Weight sensitivity", "Regime agreement with proposed weights: " + "; ".join(f"{n} {100*v:.1f}%" for n, v in ws.items()),
                 "Agreement >= 80% for every scheme", p5))

    # 6 window sensitivity
    wins = {}
    for W in (504, 2520, "expanding"):
        c2 = copy.deepcopy(cfg)
        c2["normalisation"]["window_days"] = len(raw) if W == "expanding" else W
        wins[str(W)] = agreement(k, kmsi_with(c2, raw), cfg)
    p6 = all(v >= 0.80 for v in wins.values())
    out["windows"] = {"agreement": wins, "pass": p6}
    rows.append(("Window sensitivity", "Regime agreement with 1,260-day window: " + "; ".join(f"{n} {100*v:.1f}%" for n, v in wins.items()),
                 "Agreement >= 80% for every window", p6))

    # 7 transform sensitivity
    m = k.notna() & res["kmsi_robust_z"].notna()
    rz = float(np.corrcoef(k[m], res["kmsi_robust_z"][m])[0, 1])
    p7 = rz >= 0.9
    out["transform"] = {"corr": rz, "pass": p7}
    rows.append(("Transform sensitivity", f"Correlation of percentile KMSI with robust z-score KMSI = {rz:.3f}", "r >= 0.9", p7))

    # 8 episodes
    eps = {"Dot-com peak (24 Mar 2000)": "2000-03-24", "Lehman aftermath (10 Oct 2008)": "2008-10-10",
           "Market low (20 Nov 2008)": "2008-11-20", "COVID crash (16 Mar 2020)": "2020-03-16",
           "COVID low (23 Mar 2020)": "2020-03-23", "2022 low (16 Jun 2022)": "2022-06-16",
           "2022 low (12 Oct 2022)": "2022-10-12", "Tariff shock (8 Apr 2025)": "2025-04-08",
           "5 Nov 2026 sell-off": "2026-11-05", "Latest (12 Nov 2026)": "2026-11-12"}
    ep = {lab: round(float(k.asof(pd.Timestamp(d))), 1) for lab, d in eps.items()}
    out["episodes"] = ep
    rows.append(("Episode readings", "; ".join(f"{l}: {v}" for l, v in ep.items()), "Reported as-is, never used for tuning", None))

    # 9 look-ahead audit, 10 recalculation
    t = subprocess.run(["python3", "-m", "pytest", "-q", "tests"], cwd=ROOT, capture_output=True, text=True)
    p9 = t.returncode == 0
    rows.append(("Look-ahead audit", t.stdout.strip().splitlines()[-1], "Zero violations", p9))
    r = subprocess.run(["python3", "-m", "src.kmsi.recalc_numpy"], cwd=ROOT, capture_output=True, text=True)
    p10 = r.returncode == 0
    rows.append(("Independent recalculation", r.stdout.strip().splitlines()[-1], "Match to 1e-9", p10))

    # benchmark context
    dd = spx / spx.cummax() - 1
    bench = {"corr_kmsi_vix_pct_inverted": float(pd.concat([k, 100 - vix_pct], axis=1).dropna().corr().iloc[0, 1]),
             "corr_kmsi_spx_drawdown": float(pd.concat([k, dd], axis=1).dropna().corr().iloc[0, 1])}
    out["benchmarks"] = bench

    fmt = lambda p: "" if p is None else ("Pass" if p is True else ("Fail" if p is False else p))
    md = [f"# Phase 4: KMSI v{E.VERSION} validation", "",
          f"Config {sha}. Published sample {k.first_valid_index().date()} to {k.last_valid_index().date()} "
          f"({k.notna().sum()} days). AI momentum uses the ^SOX analogue (provisional).", "",
          "| Check | Result | Criterion | Outcome |", "| --- | --- | --- | --- |"]
    md += [f"| {a} | {b} | {c} | {fmt(d)} |" for a, b, c, d in rows]
    md += ["", f"Benchmarks: correlation with inverted VIX percentile {bench['corr_kmsi_vix_pct_inverted']:.2f}; "
           f"with S&P 500 drawdown from peak {bench['corr_kmsi_spx_drawdown']:.2f}.", "",
           "Component correlation matrix (complete cases):", "",
           pd.DataFrame(C, index=cc.columns, columns=cc.columns).round(2).to_markdown()]
    REPORT.write_text("\n".join(md) + "\n")
    (E.OUT / f"kmsi_v{E.VERSION}_validation.json").write_text(json.dumps(out, indent=1, default=str))
    for a, b, c, d in rows:
        print(f"[{fmt(d) or 'info':5s}] {a}: {b}")
    print(bench)
    print(pd.DataFrame(C, index=cc.columns, columns=cc.columns).round(2))


if __name__ == "__main__":
    main()
