"""
Cross-theme comparison: "Which theme is strongest right now?"

Builds an equal-weight portfolio for each theme and compares:
- Cumulative return
- Sharpe ratio
- Momentum (recent vs longer-term)
- Drawdown
"""
import numpy as np
import pandas as pd
from src.utils.logger import get_logger

logger = get_logger(__name__)


def build_theme_returns(
    prices: pd.DataFrame,
    universe_df: pd.DataFrame,
    themes: list[str],
    purity_weighted: bool = False,
) -> pd.DataFrame:
    """
    Equal-weight (or purity-weighted) portfolio return for each theme, daily.
    universe_df must have columns: ticker, theme, theme_purity.
    """
    pivot = prices.pivot_table(index="Date", columns="Ticker", values="Close")
    daily_ret = pivot.pct_change()

    theme_rets = {}
    for theme in themes:
        members = universe_df[universe_df["theme"] == theme]
        if members.empty:
            continue
        tickers = [t for t in members["ticker"].tolist() if t in daily_ret.columns]
        if not tickers:
            continue

        if purity_weighted and "theme_purity" in members.columns:
            pmap = members.set_index("ticker")["theme_purity"]
            weights = pmap.loc[tickers].fillna(1.0)
            weights = weights / weights.sum()
            theme_rets[theme] = (daily_ret[tickers] * weights).sum(axis=1)
        else:
            theme_rets[theme] = daily_ret[tickers].mean(axis=1)

    return pd.DataFrame(theme_rets).dropna(how="all")


def compute_theme_stats(
    theme_returns: pd.DataFrame,
    benchmark_returns: pd.Series | None = None,
) -> pd.DataFrame:
    """Summary statistics per theme."""
    rows = []
    for theme in theme_returns.columns:
        ret = theme_returns[theme].dropna()
        n = len(ret)
        if n < 5:
            continue

        cum_ret = float((1 + ret).prod() - 1)
        ann_vol = float(ret.std() * np.sqrt(252))
        sharpe = float((ret.mean() / ret.std()) * np.sqrt(252)) if ret.std() > 0 else np.nan
        prices_cum = (1 + ret).cumprod()
        max_dd = float(((prices_cum - prices_cum.cummax()) / prices_cum.cummax()).min())
        calmar = float((cum_ret / abs(max_dd))) if max_dd != 0 else np.nan

        row: dict = {
            "theme": theme,
            "cumulative_return": cum_ret,
            "annualized_volatility": ann_vol,
            "sharpe": sharpe,
            "max_drawdown": max_dd,
            "calmar": calmar,
            "trading_days": n,
        }

        # momentum: 1M and 3M
        row["return_1m"] = float((1 + ret.iloc[-21:]).prod() - 1) if n >= 21 else np.nan
        row["return_3m"] = float((1 + ret.iloc[-63:]).prod() - 1) if n >= 63 else np.nan

        if benchmark_returns is not None:
            bm = benchmark_returns.reindex(ret.index).dropna()
            if len(bm) >= 10:
                excess = ret.reindex(bm.index) - bm
                row["excess_return"] = float((1 + excess.dropna()).prod() - 1)
            else:
                row["excess_return"] = np.nan

        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df["momentum_rank"] = df["return_3m"].rank(ascending=False)
        df["sharpe_rank"] = df["sharpe"].rank(ascending=False)
    return df


def compute_theme_momentum_score(
    theme_returns: pd.DataFrame,
    short_days: int = 21,
    long_days: int = 63,
) -> pd.Series:
    """Simple momentum: short-term return relative to long-term return."""
    scores = {}
    for theme in theme_returns.columns:
        ret = theme_returns[theme].dropna()
        if len(ret) < long_days:
            scores[theme] = np.nan
            continue
        short = float((1 + ret.iloc[-short_days:]).prod() - 1)
        long_ = float((1 + ret.iloc[-long_days:]).prod() - 1)
        scores[theme] = short - long_
    return pd.Series(scores, name="momentum_score").sort_values(ascending=False)
