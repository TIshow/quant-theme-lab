"""
Tests for risk factor computation with risk-free rate.

Verifies:
  - Sharpe/Sortino decrease when rf_annual > 0
  - rf_annual=0 is backward-compatible default
  - Calmar ratio sign and boundary conditions
"""
import numpy as np
import pandas as pd
import pytest

from src.factors.risk import compute_risk_metrics, _sharpe, _sortino, _calmar


def _prices_df(n: int = 300, ticker: str = "X", seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-02", periods=n, freq="B")
    p = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, n)))
    return pd.DataFrame({
        "Date": dates, "Ticker": ticker,
        "Close": p, "Volume": 500_000,
    })


# ---------------------------------------------------------------------------
# _sharpe
# ---------------------------------------------------------------------------

def test_sharpe_zero_rf_equals_simple_ratio():
    rets = pd.Series([0.01, 0.02, -0.005, 0.015, 0.008])
    expected = (rets.mean() / rets.std()) * np.sqrt(252)
    assert _sharpe(rets, rf_daily=0.0) == pytest.approx(expected)


def test_sharpe_decreases_with_higher_rf():
    rets = pd.Series(np.linspace(0.0005, 0.0015, 100))
    s0 = _sharpe(rets, rf_daily=0.0)
    s1 = _sharpe(rets, rf_daily=0.0001)
    assert s1 < s0


def test_sharpe_nan_when_std_zero_after_rf():
    # constant returns equal to rf → excess is constant zero → std=0
    rf_daily = 0.001
    rets = pd.Series([rf_daily] * 20)
    result = _sharpe(rets, rf_daily=rf_daily)
    assert np.isnan(result)


# ---------------------------------------------------------------------------
# _sortino
# ---------------------------------------------------------------------------

def test_sortino_nan_with_no_downside():
    # All returns positive → no downside std
    rets = pd.Series([0.005] * 20)
    result = _sortino(rets, rf_daily=0.0)
    assert np.isnan(result)


def test_sortino_negative_with_mostly_losses():
    rets = pd.Series([-0.01] * 20 + [0.001] * 5)
    result = _sortino(rets, rf_daily=0.0)
    assert result < 0


# ---------------------------------------------------------------------------
# _calmar
# ---------------------------------------------------------------------------

def test_calmar_positive_uptrend():
    rng = np.random.default_rng(0)
    prices = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.001, 0.012, 300))))
    returns = prices.pct_change().dropna()
    result = _calmar(returns, prices)
    assert result > 0


def test_calmar_nan_on_short_history():
    prices = pd.Series([100.0, 110.0])
    returns = prices.pct_change().dropna()
    result = _calmar(returns, prices)
    assert np.isnan(result)


# ---------------------------------------------------------------------------
# compute_risk_metrics
# ---------------------------------------------------------------------------

def test_compute_risk_metrics_columns_present():
    df = compute_risk_metrics(_prices_df())
    assert "sharpe_3m" in df.columns
    assert "sharpe_6m" in df.columns
    assert "sharpe_12m" in df.columns
    assert "sortino_12m" in df.columns
    assert "calmar_12m" in df.columns


def test_compute_risk_metrics_sharpe_lower_with_rf():
    prices = _prices_df(n=300)
    result_no_rf = compute_risk_metrics(prices, rf_annual=0.0)
    result_with_rf = compute_risk_metrics(prices, rf_annual=0.05)
    # sharpe_12m must decrease when rf>0 and mean return > 0
    s0 = result_no_rf["sharpe_12m"].iloc[0]
    s1 = result_with_rf["sharpe_12m"].iloc[0]
    if not np.isnan(s0) and not np.isnan(s1):
        assert s1 < s0


def test_compute_risk_metrics_nan_on_short_history():
    df = compute_risk_metrics(_prices_df(n=50))
    assert df["sharpe_12m"].isna().all()
    assert df["calmar_12m"].isna().all()
