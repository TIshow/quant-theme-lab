"""
Battery storage sector KPIs.
Derived from standard IRBank columns (no additional scraping needed).
"""
import numpy as np
import pandas as pd


def compute_kpis(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    # Capital intensity: |capex| / revenue × 100 (%)
    if "capex" in df.columns and "revenue" in df.columns:
        result["capex_ratio"] = (df["capex"].abs() / df["revenue"].replace(0, np.nan) * 100)

    # Gross margin: 100 - cost_ratio (%)
    if "cost_ratio" in df.columns:
        result["gross_margin"] = 100 - df["cost_ratio"]

    # Debt to equity: interest_bearing_debt / net_assets × 100 (%)
    if "interest_bearing_debt" in df.columns and "net_assets" in df.columns:
        result["debt_to_equity"] = (
            df["interest_bearing_debt"] / df["net_assets"].replace(0, np.nan) * 100
        )

    return result
