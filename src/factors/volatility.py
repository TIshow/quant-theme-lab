import numpy as np
import pandas as pd

from src.utils.constants import PERIOD_DAYS, TRADING_DAYS_PER_YEAR


def compute_volatility(prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticker, grp in prices.groupby("Ticker"):
        ret = grp.sort_values("Date")["Close"].pct_change().dropna()
        n = len(ret)
        row: dict = {"Ticker": ticker}
        for label, days in PERIOD_DAYS.items():
            row[f"volatility_{label}"] = ret.iloc[-days:].std() * TRADING_DAYS_PER_YEAR ** 0.5 if n >= days else np.nan
        row["annualized_volatility"] = ret.std() * TRADING_DAYS_PER_YEAR ** 0.5 if n > 1 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)
