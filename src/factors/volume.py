import numpy as np
import pandas as pd


def compute_volume_factors(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Volume-based signals — generic across all sectors/markets:
    - rvol_20_60: 20D avg volume / 60D avg volume
      > 1.0 = recent activity above baseline (increased market interest)
    - price_volume_alignment: corr(daily_return, volume_pct_change) over last 20D
      Positive = volume rises with price (accumulation / conviction buying)
      Negative = volume rises against price (distribution / exhaustion)
    """
    rows = []
    for ticker, grp in prices.groupby("Ticker"):
        g = grp.sort_values("Date").copy()
        n = len(g)
        row: dict = {"Ticker": ticker}

        vol_20 = g["Volume"].iloc[-20:].mean() if n >= 20 else np.nan
        vol_60 = g["Volume"].iloc[-60:].mean() if n >= 60 else np.nan
        if pd.notna(vol_20) and pd.notna(vol_60) and vol_60 > 0:
            row["rvol_20_60"] = vol_20 / vol_60
        else:
            row["rvol_20_60"] = np.nan

        if n >= 22:
            recent = g.iloc[-22:].copy()
            recent["daily_return"] = recent["Close"].pct_change()
            recent["volume_change"] = recent["Volume"].pct_change()
            recent = recent.dropna(subset=["daily_return", "volume_change"])
            if len(recent) >= 10:
                row["price_volume_alignment"] = recent["daily_return"].corr(recent["volume_change"])
            else:
                row["price_volume_alignment"] = np.nan
        else:
            row["price_volume_alignment"] = np.nan

        rows.append(row)
    return pd.DataFrame(rows)
