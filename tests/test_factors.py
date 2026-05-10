import pytest
import numpy as np
import pandas as pd
from src.factors.returns import compute_daily_returns, compute_period_returns
from src.factors.volatility import compute_volatility
from src.factors.drawdown import compute_max_drawdown
from src.factors.liquidity import compute_liquidity
from src.factors.risk import compute_risk_metrics
from src.factors.factor_table import build_factor_table


def _prices(n=300, ticker="TEST") -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    p = 100 * (1 + np.random.randn(n).cumsum() * 0.01)
    return pd.DataFrame({
        "Date": dates, "Ticker": ticker, "Close": p,
        "Open": p * 0.99, "High": p * 1.01, "Low": p * 0.98,
        "Volume": np.random.randint(100_000, 1_000_000, n),
    })


def test_daily_returns():
    df = compute_daily_returns(_prices())
    assert "daily_return" in df.columns
    assert df["daily_return"].notna().sum() > 0


def test_period_returns_full_history():
    df = compute_period_returns(_prices(300))
    assert "return_1m" in df.columns and "return_12m" in df.columns
    assert df["return_12m"].notna().any()


def test_period_returns_short_history():
    df = compute_period_returns(_prices(50))
    assert df["return_12m"].isna().all()
    assert df["return_1m"].notna().any()


def test_volatility():
    df = compute_volatility(_prices())
    assert "annualized_volatility" in df.columns
    assert df["annualized_volatility"].notna().any()
    assert (df["annualized_volatility"] >= 0).all()


def test_max_drawdown():
    df = compute_max_drawdown(_prices())
    assert "max_drawdown_12m" in df.columns
    assert (df["max_drawdown_12m"].dropna() <= 0).all()


def test_liquidity_no_none_keys():
    df = compute_liquidity(_prices())
    assert None not in df.columns
    assert "avg_traded_value_3m" in df.columns


def test_risk_metrics():
    df = compute_risk_metrics(_prices(300))
    assert "sharpe_12m" in df.columns
    assert "sortino_12m" in df.columns
    assert "calmar_12m" in df.columns


def test_factor_table_no_crash_with_nan():
    prices = _prices(200)
    prices.loc[10:20, "Close"] = np.nan
    df = build_factor_table(prices)
    assert "Ticker" in df.columns
    assert "data_quality_flag" in df.columns


def test_data_quality_flags():
    ok = build_factor_table(_prices(300))
    assert ok["data_quality_flag"].iloc[0] == "OK"
    limited = build_factor_table(_prices(150))
    assert limited["data_quality_flag"].iloc[0] == "LIMITED_HISTORY"
    short = build_factor_table(_prices(50))
    assert short["data_quality_flag"].iloc[0] == "VERY_SHORT_HISTORY"
