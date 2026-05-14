"""
Fundamental factors from IRBank (JP stocks only).

Which metrics to extract is driven by config['fundamental_weights'].
Theme-specific KPIs are applied via the irbank_kpi plugin system.
"""
import numpy as np
import pandas as pd

from src.data.irbank_scraper import fetch_fundamentals
from src.data.yfinance_fundamentals import fetch_us_fundamentals
from src.data.irbank_kpi import compute_theme_kpis
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _latest_actual(df: pd.DataFrame) -> pd.Series | None:
    """Return the most recent non-forecast row."""
    actual = df[~df["fiscal_year"].str.contains("予", na=False)]
    return actual.iloc[0] if not actual.empty else None


def compute_fundamental_factors(
    tickers: list[str],
    config: dict | None = None,
    theme: str | None = None,
    fundamentals_data: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """
    Return one row per JP ticker with fundamental factor values.

    Metric names are driven by config['fundamental_weights'].
    If config is None, all available metrics are returned.
    US tickers are silently skipped.

    Args:
        fundamentals_data: Pre-fetched {ticker: DataFrame} from fetch_all_fundamentals().
                           When provided, skips IRBank fetching entirely.
                           When None, fetches via fetch_fundamentals() as before.
    """
    fw = config.get("fundamental_weights", {}) if config else {}
    metric_names = list(fw.keys()) if fw else None  # None = return all

    rows = []
    for ticker in tickers:
        is_jp = ticker.endswith(".T")

        if fundamentals_data is not None:
            df = fundamentals_data.get(ticker, pd.DataFrame())
        elif is_jp:
            df = fetch_fundamentals(ticker, use_cache=True)
            if not df.empty and theme:
                df = compute_theme_kpis(theme, df)
        else:
            df = fetch_us_fundamentals(ticker, use_cache=True)

        if df.empty:
            rows.append({"Ticker": ticker})
            continue

        row = _latest_actual(df)
        if row is None:
            rows.append({"Ticker": ticker})
            continue

        rec: dict = {"Ticker": ticker}
        cols_to_extract = metric_names if metric_names else [
            c for c in df.columns if c != "fiscal_year"
        ]
        for col in cols_to_extract:
            val = row.get(col, np.nan)
            rec[f"fundamental_{col}"] = float(val) if not (isinstance(val, float) and np.isnan(val)) else np.nan

        rows.append(rec)

    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Ticker"])


def fetch_all_fundamentals(
    tickers: list[str],
    theme: str | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Fetch full historical fundamentals for all JP tickers (for IC computation).
    Returns dict: ticker -> DataFrame (all periods, KPIs applied).
    """
    results = {}
    for ticker in tickers:
        if ticker.endswith(".T"):
            df = fetch_fundamentals(ticker, use_cache=True)
            if not df.empty and theme:
                df = compute_theme_kpis(theme, df)
        else:
            df = fetch_us_fundamentals(ticker, use_cache=True)
        results[ticker] = df
    return results
