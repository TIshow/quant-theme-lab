"""
Risk model using Ledoit-Wolf shrinkage covariance estimator.

When N (stocks) > T (observations) the sample covariance is unstable.
Ledoit-Wolf applies optimal linear shrinkage toward a structured target,
producing a better-conditioned matrix for VaR / CVaR estimation.
"""
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf
from scipy.stats import norm


def compute_covariance_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    pivot = prices.pivot_table(index="Date", columns="Ticker", values="Close")
    returns = pivot.pct_change().dropna(how="all").dropna(axis=1)
    lw = LedoitWolf()
    cov = lw.fit(returns.values).covariance_
    return pd.DataFrame(cov, index=returns.columns, columns=returns.columns)


def compute_portfolio_var(
    weights: pd.Series,
    cov_matrix: pd.DataFrame,
    confidence: float = 0.95,
    horizon_days: int = 1,
) -> float:
    """Parametric (Gaussian) VaR. Returns loss as a positive number."""
    tickers = weights.index.intersection(cov_matrix.index)
    w = weights.loc[tickers].values
    C = cov_matrix.loc[tickers, tickers].values
    portfolio_variance = float(w @ C @ w)
    portfolio_vol = np.sqrt(portfolio_variance * horizon_days)
    return float(norm.ppf(confidence) * portfolio_vol)


def compute_portfolio_cvar(
    weights: pd.Series,
    cov_matrix: pd.DataFrame,
    confidence: float = 0.95,
    horizon_days: int = 1,
) -> float:
    """Parametric CVaR (Expected Shortfall)."""
    tickers = weights.index.intersection(cov_matrix.index)
    w = weights.loc[tickers].values
    C = cov_matrix.loc[tickers, tickers].values
    portfolio_variance = float(w @ C @ w)
    portfolio_vol = np.sqrt(portfolio_variance * horizon_days)
    z = norm.ppf(confidence)
    return float(portfolio_vol * norm.pdf(z) / (1 - confidence))
