"""
Factor validation via Information Coefficient (IC).

IC = Spearman rank correlation between a factor value at time T
     and the forward return over the next N trading days.

ICIR = mean(IC series) / std(IC series)
     → > 0.3  usable signal
     → > 0.5  strong signal
     → < 0.1  noise, remove from scoring

IC Decay measures how quickly predictive power fades with horizon.

Performance:
  compute_ic_timeseries() precomputes the full factor matrix in one
  vectorized pass (O(n)), then slices by date in the loop — O(1) per month.
  Previous approach called build_factor_table() each month → O(n²).
  Supported factors are handled natively; unsupported factors fall back
  to the legacy per-month approach.
"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Precomputed factor matrix — one vectorized pass over the full price history
# ---------------------------------------------------------------------------

def _factor_matrix_from_prices(prices: pd.DataFrame, factor_col: str) -> pd.DataFrame | None:
    """
    Return a (date × ticker) DataFrame of factor values computed via
    vectorized rolling operations.  Returns None for unsupported factors.
    """
    close = prices.pivot_table(index="Date", columns="Ticker", values="Close")
    daily_ret = close.pct_change()

    if factor_col == "return_1m":
        return close.pct_change(21)
    if factor_col == "return_3m":
        return close.pct_change(63)
    if factor_col == "return_6m":
        return close.pct_change(126)
    if factor_col == "return_12m":
        return close.pct_change(252)

    if factor_col == "annualized_volatility":
        # Use 63-day rolling window (same lookback as volatility_3m)
        return daily_ret.rolling(63, min_periods=21).std() * np.sqrt(252)

    if factor_col == "max_drawdown_12m":
        rolling_max = close.rolling(252, min_periods=21).max()
        return (close - rolling_max) / rolling_max  # always ≤ 0

    if factor_col == "avg_volume_3m":
        vol = prices.pivot_table(index="Date", columns="Ticker", values="Volume")
        return vol.rolling(63, min_periods=21).mean()

    if factor_col in ("sharpe_3m", "sharpe_6m", "sharpe_12m"):
        w = {"sharpe_3m": 63, "sharpe_6m": 126, "sharpe_12m": 252}[factor_col]
        mean = daily_ret.rolling(w, min_periods=w // 2).mean()
        std = daily_ret.rolling(w, min_periods=w // 2).std()
        return (mean / std.replace(0, np.nan)) * np.sqrt(252)

    return None  # unsupported → caller falls back to legacy method


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_ic(
    factor_values: pd.Series,
    forward_returns: pd.Series,
) -> float:
    """Spearman IC between factor and forward return (aligned by index)."""
    df = pd.concat([factor_values, forward_returns], axis=1).dropna()
    if len(df) < 5:
        return np.nan
    corr, _ = spearmanr(df.iloc[:, 0], df.iloc[:, 1])
    return float(corr)


def compute_ic_timeseries(
    prices: pd.DataFrame,
    factor_col: str,
    forward_period_days: int = 21,
    rebalance_freq: str = "ME",
) -> pd.Series:
    """
    Monthly IC time-series for a single factor column.

    At each rebalance date, computes the cross-sectional Spearman IC
    between the factor snapshot and realized forward returns.

    For supported factors the full factor matrix is precomputed once
    (vectorized rolling), making the loop O(1) per month instead of
    rebuilding the factor table from scratch each time.
    """
    close_pivot = prices.pivot_table(index="Date", columns="Ticker", values="Close")
    monthly_dates = close_pivot.resample(rebalance_freq).last().index

    factor_matrix = _factor_matrix_from_prices(prices, factor_col)

    if factor_matrix is not None:
        return _ic_timeseries_fast(close_pivot, factor_matrix, monthly_dates, factor_col)
    else:
        logger.warning(
            f"compute_ic_timeseries: no precomputed method for '{factor_col}' — "
            "falling back to legacy per-month rebuild (slow)"
        )
        return _ic_timeseries_legacy(prices, close_pivot, factor_col, monthly_dates)


def _ic_timeseries_fast(
    close_pivot: pd.DataFrame,
    factor_matrix: pd.DataFrame,
    monthly_dates: pd.DatetimeIndex,
    factor_col: str,
) -> pd.Series:
    """O(months) IC loop using precomputed factor matrix."""
    ic_values = {}
    for i, date in enumerate(monthly_dates[:-1]):
        fwd_date = monthly_dates[i + 1]

        if date not in factor_matrix.index:
            continue

        factor_snap = factor_matrix.loc[date].dropna()
        if len(factor_snap) < 5:
            continue

        if date not in close_pivot.index or fwd_date not in close_pivot.index:
            continue

        p0 = close_pivot.loc[date].dropna()
        p1 = close_pivot.loc[fwd_date].dropna()

        common = factor_snap.index.intersection(p0.index).intersection(p1.index)
        if len(common) < 5:
            continue

        fwd_ret = pd.Series(p1[common].values / p0[common].values - 1, index=common)
        ic_values[date] = compute_ic(factor_snap[common], fwd_ret)

    return pd.Series(ic_values, name=f"IC_{factor_col}")


def _ic_timeseries_legacy(
    prices: pd.DataFrame,
    close_pivot: pd.DataFrame,
    factor_col: str,
    monthly_dates: pd.DatetimeIndex,
) -> pd.Series:
    """
    Original O(n²) implementation kept as fallback for unsupported factors.
    Rebuilds the full factor table at each month-end.
    """
    from src.factors.factor_table import build_factor_table

    ic_values = {}
    for i, date in enumerate(monthly_dates[:-1]):
        hist = prices[prices["Date"] <= date]
        if hist.empty:
            continue
        try:
            factors = build_factor_table(hist)
        except Exception:
            continue

        if factor_col not in factors.columns:
            continue

        fwd_date = monthly_dates[i + 1]
        fwd_returns = {}
        for ticker in factors["Ticker"]:
            p_now = close_pivot.loc[:date, ticker].dropna()
            p_fwd = close_pivot.loc[:fwd_date, ticker].dropna()
            if p_now.empty or p_fwd.empty:
                continue
            fwd_returns[ticker] = (p_fwd.iloc[-1] / p_now.iloc[-1]) - 1

        if len(fwd_returns) < 5:
            continue

        factor_vals = factors.set_index("Ticker")[factor_col]
        fwd_series = pd.Series(fwd_returns)
        ic_values[date] = compute_ic(factor_vals, fwd_series)

    return pd.Series(ic_values, name=f"IC_{factor_col}")


def compute_icir(ic_series: pd.Series) -> float:
    """IC Information Ratio = mean(IC) / std(IC). Higher is better."""
    clean = ic_series.dropna()
    if len(clean) < 3:
        return np.nan
    return float(clean.mean() / clean.std()) if clean.std() > 0 else np.nan


def compute_ic_decay(
    prices: pd.DataFrame,
    factor_col: str,
    horizons: list[int] | None = None,
) -> pd.DataFrame:
    """
    IC at multiple forward horizons (in trading days).
    Reveals how quickly a factor's predictive power decays.
    """
    if horizons is None:
        horizons = [21, 42, 63, 126, 252]

    rows = []
    for h in horizons:
        ic_series = compute_ic_timeseries(prices, factor_col, forward_period_days=h)
        rows.append({
            "horizon_days": h,
            "mean_ic": ic_series.mean(),
            "icir": compute_icir(ic_series),
            "positive_ic_pct": (ic_series > 0).mean(),
        })
    return pd.DataFrame(rows)


def validate_all_factors(
    prices: pd.DataFrame,
    factor_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Run IC/ICIR validation for a list of factor columns."""
    if factor_cols is None:
        factor_cols = [
            "return_1m", "return_3m", "return_6m",
            "annualized_volatility", "max_drawdown_12m",
            "avg_volume_3m", "sharpe_6m", "sharpe_12m",
        ]

    rows = []
    for col in factor_cols:
        logger.info(f"Validating factor: {col}")
        ic_series = compute_ic_timeseries(prices, col)
        icir = compute_icir(ic_series)
        rows.append({
            "factor": col,
            "mean_ic": float(ic_series.mean()) if not ic_series.empty else np.nan,
            "icir": icir,
            "n_periods": len(ic_series.dropna()),
            "positive_ic_pct": float((ic_series > 0).mean()) if not ic_series.empty else np.nan,
            "usable": bool(abs(icir) > 0.3) if not np.isnan(icir) else False,
        })
    return pd.DataFrame(rows).sort_values("icir", ascending=False)
