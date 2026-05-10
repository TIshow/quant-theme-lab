import numpy as np
import pandas as pd


def compute_moving_average_features(prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticker, grp in prices.groupby("Ticker"):
        closes = grp.sort_values("Date")["Close"].dropna()
        n = len(closes)
        current = float(closes.iloc[-1])
        row: dict = {"Ticker": ticker}
        for w in [20, 50, 100, 200]:
            if n >= w:
                ma = float(closes.iloc[-w:].mean())
                row[f"ma_{w}"] = ma
                row[f"distance_from_ma_{w}"] = (current - ma) / ma if ma != 0 else np.nan
            else:
                row[f"ma_{w}"] = np.nan
                row[f"distance_from_ma_{w}"] = np.nan
        period = min(n, 252)
        row["high_52w"] = float(closes.iloc[-period:].max())
        row["low_52w"] = float(closes.iloc[-period:].min())
        row["distance_from_52w_high"] = (current - row["high_52w"]) / row["high_52w"] if row["high_52w"] != 0 else np.nan
        row["distance_from_52w_low"] = (current - row["low_52w"]) / row["low_52w"] if row["low_52w"] != 0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)
