"""Exploratory (not registered): univariate AUC and sign stability of H4 predictors, training vs test period."""
import json

import pandas as pd
from sklearn.metrics import roc_auc_score

from src.kmsi import engine as E

X = pd.read_parquet(E.ROOT / "data" / "outputs" / "phase8_h4_design.parquet").dropna(subset=["y_bin"])
out = {}
for name, d in [("train_2012_2018", X[X.index <= "2018-06-30"]), ("test_2019_2026", X[X.index >= "2019-01-01"]), ("all", X)]:
    y = d["y_bin"].astype(int)
    out[name] = {"months": len(d), "event_rate": float(y.mean()),
                 "auc_univariate": {c: float(roc_auc_score(y, d[c])) for c in ["ret63", "dd_peak", "vix_pct", "kmsi", "kbri", "gsadf"]}}
(E.ROOT / "data" / "outputs" / "phase8_h4_diagnostics.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
