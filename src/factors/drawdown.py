import numpy as np
import pandas as pd

from src.utils.constants import PERIOD_DAYS


def _max_drawdown(series: pd.Series) -> float:
    if len(series) < 2:
        return np.nan
    dd = (series - series.cummax()) / series.cummax()
    return float(dd.min())


def compute_max_drawdown(prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticker, grp in prices.groupby("Ticker"):
        closes = grp.sort_values("Date")["Close"].dropna()
        n = len(closes)
        row: dict = {"Ticker": ticker}
        for label, days in PERIOD_DAYS.items():
            row[f"max_drawdown_{label}"] = _max_drawdown(closes.iloc[-days:]) if n > days else np.nan
        row["max_drawdown_full"] = _max_drawdown(closes)
        rows.append(row)
    return pd.DataFrame(rows)
