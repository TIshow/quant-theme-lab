import pandas as pd


def compute_correlation_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    pivot = prices.pivot_table(index="Date", columns="Ticker", values="Close")
    return pivot.pct_change().dropna(how="all").corr()


def get_top_correlated_stocks(
    corr: pd.DataFrame,
    ticker: str,
    top_n: int = 5,
) -> pd.DataFrame:
    if ticker not in corr.columns:
        return pd.DataFrame(columns=["ticker", "correlation"])
    col = corr[ticker].drop(ticker, errors="ignore").sort_values(ascending=False)
    top = col.head(top_n).reset_index()
    top.columns = ["ticker", "correlation"]
    return top
