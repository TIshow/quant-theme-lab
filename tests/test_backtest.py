"""
Tests for backtest modules.

Verifies:
  - Transaction cost model (new position = 2×tc, held = 1×tc)
  - Score-based vs momentum-based selection
  - Sharpe calculation with/without risk-free rate
  - _lag_date helper
  - Cumulative return computation
"""
import numpy as np
import pandas as pd
import pytest

from src.backtest.simple_backtest import (
    run_monthly_momentum_top_n_backtest,
    _lag_date,
    _sharpe,
    _max_dd,
)


def _make_prices(n_tickers: int = 5, n_days: int = 500, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames = []
    tickers = [f"T{i}" for i in range(n_tickers)]
    dates = pd.date_range("2021-01-04", periods=n_days, freq="B")
    for t in tickers:
        p = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, n_days)))
        frames.append(pd.DataFrame({
            "Date": dates, "Ticker": t,
            "Close": p, "Volume": rng.integers(100_000, 1_000_000, n_days),
        }))
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# _lag_date
# ---------------------------------------------------------------------------

def test_lag_date_returns_correct_offset():
    idx = pd.date_range("2024-01-01", periods=10, freq="B")
    after = idx[2]  # 3rd date
    result = _lag_date(idx, after, lag=1)
    assert result == idx[3]


def test_lag_date_returns_correct_offset_lag2():
    idx = pd.date_range("2024-01-01", periods=10, freq="B")
    after = idx[0]
    result = _lag_date(idx, after, lag=2)
    assert result == idx[2]


def test_lag_date_fallback_when_no_future_dates():
    idx = pd.date_range("2024-01-01", periods=5, freq="B")
    after = idx[-1]  # last date — no future dates
    result = _lag_date(idx, after, lag=1)
    assert result == after


# ---------------------------------------------------------------------------
# _sharpe
# ---------------------------------------------------------------------------

def test_sharpe_positive_for_positive_returns():
    rng = np.random.default_rng(0)
    rets = pd.Series(rng.normal(0.02, 0.005, 24))
    assert _sharpe(rets) > 0


def test_sharpe_lower_with_risk_free_rate():
    rng = np.random.default_rng(0)
    rets = pd.Series(rng.normal(0.02, 0.005, 24))
    s_no_rf = _sharpe(rets, rf_annual=0.0)
    s_with_rf = _sharpe(rets, rf_annual=0.05)
    assert s_with_rf < s_no_rf


def test_sharpe_nan_on_too_few_periods():
    assert np.isnan(_sharpe(pd.Series([0.01, 0.02])))


def test_sharpe_nan_on_zero_std():
    rets = pd.Series([0.01] * 12)  # constant returns → std of excess = 0
    assert np.isnan(_sharpe(rets))


# ---------------------------------------------------------------------------
# _max_dd
# ---------------------------------------------------------------------------

def test_max_dd_negative():
    cum = pd.Series([0.0, 0.1, 0.2, 0.05, 0.3])
    assert _max_dd(cum) < 0


def test_max_dd_monotonic_increase():
    cum = pd.Series([0.0, 0.1, 0.2, 0.3, 0.4])
    # No drawdown in a monotonically increasing series
    assert _max_dd(cum) == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# run_monthly_momentum_top_n_backtest
# ---------------------------------------------------------------------------

def test_backtest_returns_dataframe():
    prices = _make_prices()
    result = run_monthly_momentum_top_n_backtest(prices, top_n=2)
    assert isinstance(result, pd.DataFrame)
    assert "portfolio_return" in result.columns
    assert "cumulative_return" in result.columns


def test_backtest_selection_mode_momentum():
    prices = _make_prices()
    result = run_monthly_momentum_top_n_backtest(prices, top_n=2, score_df=None)
    assert (result["selection_mode"] == "momentum").all()


def test_backtest_selection_mode_score():
    prices = _make_prices(n_tickers=5)
    tickers = prices["Ticker"].unique().tolist()
    score_df = pd.DataFrame({
        "Ticker": tickers,
        "final_score": [0.9, 0.7, 0.5, 0.3, 0.1],
    })
    result = run_monthly_momentum_top_n_backtest(prices, top_n=2, score_df=score_df)
    assert (result["selection_mode"] == "score").all()


def test_backtest_top_n_respected():
    prices = _make_prices(n_tickers=5)
    result = run_monthly_momentum_top_n_backtest(prices, top_n=2)
    assert (result["n_holdings"] <= 2).all()


def test_backtest_cumulative_return_starts_near_zero():
    prices = _make_prices()
    result = run_monthly_momentum_top_n_backtest(prices, top_n=2)
    # First cumulative return equals first monthly return
    first_port = result["portfolio_return"].iloc[0]
    first_cum = result["cumulative_return"].iloc[0]
    assert first_cum == pytest.approx(first_port, abs=1e-10)


def test_backtest_transaction_cost_reduces_return():
    """Higher transaction costs should reduce total return."""
    prices = _make_prices(seed=42)
    result_low = run_monthly_momentum_top_n_backtest(prices, top_n=3, transaction_cost_bps=0)
    result_high = run_monthly_momentum_top_n_backtest(prices, top_n=3, transaction_cost_bps=100)
    cum_low = result_low["cumulative_return"].iloc[-1]
    cum_high = result_high["cumulative_return"].iloc[-1]
    assert cum_low > cum_high


def test_backtest_excludes_benchmark_from_selection():
    prices = _make_prices(n_tickers=4)
    bm = "T0"
    result = run_monthly_momentum_top_n_backtest(prices, top_n=2, benchmark_ticker=bm)
    for tickers_str in result["selected_tickers"]:
        assert bm not in tickers_str.split(",")
