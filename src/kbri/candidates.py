"""Single source of the KBRI candidate pool and business-model groups.

Pool: config/kbri_pool_v1.0.csv (rule-based; see config pool_rules).
Group: SIC-based, with the hyperscaler rule applied once fundamentals exist:
a software (SIC 7370-7374) company with TTM capex >= $10bn at any filing since 2010 is a hyperscaler.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
POOL = ROOT / "config" / "kbri_pool_v1.0.csv"
PANEL = ROOT / "data" / "staged" / "kbri_fundamentals_pit.parquet"
HYPERSCALER_CAPEX = 10e9


def pool() -> pd.DataFrame:
    return pd.read_csv(POOL)


def groups() -> dict:
    p = pool().set_index("ticker")
    g = p["group"].to_dict()
    if PANEL.exists():
        P = pd.read_parquet(PANEL)
        big = P.groupby("ticker")["capex_ttm"].max()
        for t, cap in big.items():
            if g.get(t) == "software_apps" and cap >= HYPERSCALER_CAPEX:
                g[t] = "hyperscalers"
    return g


def ciks() -> dict:
    return pool().set_index("ticker")["cik"].astype(int).to_dict()
