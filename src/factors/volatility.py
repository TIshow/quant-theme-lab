import numpy as np
import pandas as pd


def compute_volatility(prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticker, grp in prices.groupby("Ticker"):
        ret = grp.sort_values("Date")["Close"].pct_change().dropna()
        n = len(ret)
        row: dict = {"Ticker": ticker}
        for label, days in [("1m", 21), ("3m", 63), ("6m", 126), ("12m", 252)]:
            row[f"volatility_{label}"] = ret.iloc[-days:].std() * np.sqrt(252) if n >= days else np.nan
        row["annualized_volatility"] = ret.std() * np.sqrt(252) if n > 1 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)
