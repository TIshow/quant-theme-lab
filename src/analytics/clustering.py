import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform


def compute_clusters(prices: pd.DataFrame, n_clusters: int = 4) -> pd.DataFrame:
    pivot = prices.pivot_table(index="Date", columns="Ticker", values="Close")
    returns = pivot.pct_change().dropna(how="all").dropna(axis=1, how="all")
    corr = returns.corr(min_periods=20).fillna(0)
    tickers = corr.columns.tolist()
    if len(tickers) < 2:
        return pd.DataFrame({"Ticker": tickers, "cluster": [1] * len(tickers)})

    dist = np.clip(1 - corr.values, 0, None)
    np.fill_diagonal(dist, 0)
    Z = linkage(squareform(dist), method="ward")
    labels = fcluster(Z, t=min(n_clusters, len(tickers)), criterion="maxclust")
    return pd.DataFrame({"Ticker": tickers, "cluster": labels})
