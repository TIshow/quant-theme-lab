import pytest
import numpy as np
import pandas as pd
from src.analytics.theme_comparison import build_theme_returns, compute_theme_stats, compute_theme_momentum_score


def _make_prices(tickers: list[str], n: int = 100) -> pd.DataFrame:
    np.random.seed(0)
    frames = []
    for t in tickers:
        dates = pd.date_range("2023-01-02", periods=n, freq="B")
        p = 100 * (1 + np.random.randn(n).cumsum() * 0.01)
        frames.append(pd.DataFrame({"Date": dates, "Ticker": t, "Close": p,
                                    "Open": p, "High": p, "Low": p, "Volume": 1_000_000}))
    return pd.concat(frames, ignore_index=True)


def _make_universe(tickers: list[str], themes: list[str]) -> pd.DataFrame:
    rows = []
    for t, theme in zip(tickers, themes):
        rows.append({"ticker": t, "theme": theme, "theme_purity": 4})
    return pd.DataFrame(rows)


def test_theme_returns_shape():
    prices = _make_prices(["A", "B", "C", "D"])
    universe = _make_universe(["A", "B", "C", "D"], ["th1", "th1", "th2", "th2"])
    theme_rets = build_theme_returns(prices, universe, ["th1", "th2"])
    assert "th1" in theme_rets.columns
    assert "th2" in theme_rets.columns
    assert len(theme_rets) > 0


def test_theme_stats_columns():
    prices = _make_prices(["A", "B", "C", "D"])
    universe = _make_universe(["A", "B", "C", "D"], ["th1", "th1", "th2", "th2"])
    theme_rets = build_theme_returns(prices, universe, ["th1", "th2"])
    stats = compute_theme_stats(theme_rets)
    assert "sharpe" in stats.columns
    assert "cumulative_return" in stats.columns


def test_momentum_score_ordering():
    prices = _make_prices(["A", "B"])
    universe = _make_universe(["A", "B"], ["fast", "slow"])
    theme_rets = build_theme_returns(prices, universe, ["fast", "slow"])
    score = compute_theme_momentum_score(theme_rets)
    assert isinstance(score, pd.Series)
    assert len(score) == 2
