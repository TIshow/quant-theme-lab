import numpy as np
import pandas as pd


def compute_liquidity(prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticker, grp in prices.groupby("Ticker"):
        g = grp.sort_values("Date").copy()
        g["traded_value"] = g["Close"] * g["Volume"]
        n = len(g)
        row: dict = {"Ticker": ticker}
        for label, days in [("1m", 21), ("3m", 63)]:
            row[f"avg_volume_{label}"] = g["Volume"].iloc[-days:].mean() if n >= days else np.nan
        for label, days in [("1m", 21), ("3m", 63), ("6m", 126)]:
            row[f"avg_traded_value_{label}"] = g["traded_value"].iloc[-days:].mean() if n >= days else np.nan
        rows.append(row)
    return pd.DataFrame(rows)
