import numpy as np
import pandas as pd

PERIOD_DAYS = {"1m": 21, "3m": 63, "6m": 126, "12m": 252}


def compute_daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for ticker, grp in prices.groupby("Ticker"):
        g = grp.sort_values("Date").copy()
        g["daily_return"] = g["Close"].pct_change()
        frames.append(g)
    return pd.concat(frames, ignore_index=True)


def compute_period_returns(prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticker, grp in prices.groupby("Ticker"):
        closes = grp.sort_values("Date")["Close"].dropna().values
        n = len(closes)
        row: dict = {"Ticker": ticker}
        for label, days in PERIOD_DAYS.items():
            row[f"return_{label}"] = (closes[-1] / closes[-days - 1]) - 1 if n > days else np.nan
        rows.append(row)
    return pd.DataFrame(rows)
