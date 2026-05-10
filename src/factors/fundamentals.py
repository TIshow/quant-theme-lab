"""
Fundamental factors from IRBank (JP) / yfinance (US).

Extracts the most recent fiscal year values per ticker:
  roe, roa, operating_margin, equity_ratio, revenue_growth, free_cf_margin
"""
import numpy as np
import pandas as pd

from src.data.irbank_scraper import fetch_fundamentals
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Columns to extract (use most recent non-forecast period)
_FACTOR_COLS = [
    "roe",
    "roa",
    "operating_margin",
    "equity_ratio",
    "revenue_growth",
    "free_cf_margin",
]


def _latest_actual(df: pd.DataFrame) -> pd.Series | None:
    """Return the most recent row that is NOT a forecast (予)."""
    actual = df[~df["fiscal_year"].str.contains("予", na=False)]
    if actual.empty:
        return None
    return actual.iloc[0]


def _free_cf_margin(row: pd.Series) -> float:
    """free_cf / revenue as %"""
    if pd.isna(row.get("free_cf")) or pd.isna(row.get("revenue")) or row.get("revenue", 0) == 0:
        return np.nan
    return row["free_cf"] / row["revenue"] * 100


def compute_fundamental_factors(tickers: list[str]) -> pd.DataFrame:
    """
    Return one row per JP ticker with fundamental factor values.
    US tickers are skipped (no IRBank data).
    """
    rows = []
    for ticker in tickers:
        if not ticker.endswith(".T"):
            continue
        df = fetch_fundamentals(ticker, use_cache=True)
        if df.empty:
            rows.append({"Ticker": ticker})
            continue

        row = _latest_actual(df)
        if row is None:
            rows.append({"Ticker": ticker})
            continue

        rec: dict = {"Ticker": ticker}
        for col in ["roe", "roa", "operating_margin", "equity_ratio", "revenue_growth"]:
            rec[f"fundamental_{col}"] = row.get(col, np.nan)
        rec["fundamental_free_cf_margin"] = _free_cf_margin(row)
        rows.append(rec)

    return pd.DataFrame(rows)
