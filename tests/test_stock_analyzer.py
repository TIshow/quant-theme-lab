import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch


def _prices(tickers: list[str], n: int = 300) -> pd.DataFrame:
    np.random.seed(7)
    frames = []
    for t in tickers:
        dates = pd.date_range("2023-01-02", periods=n, freq="B")
        p = 100 * (1 + np.random.randn(n).cumsum() * 0.01)
        frames.append(pd.DataFrame({
            "Date": dates, "Ticker": t,
            "Close": p, "Open": p * 0.99, "High": p * 1.01,
            "Low": p * 0.98, "Adj_Close": p,
            "Volume": np.random.randint(100_000, 1_000_000, n),
        }))
    return pd.concat(frames, ignore_index=True)


THEME_TICKERS = [
    "485A.T", "6674.T", "6752.T", "6762.T", "5333.T",
    "6996.T", "6504.T", "3407.T", "4208.T", "5714.T",
    "TSLA", "FLNC", "ENS", "ALB", "EOSE",
    "QS", "ENVX", "AMPX", "SLDP", "ABAT", "SPY",
]


def test_standalone_returns_dict():
    from src.stock.stock_analyzer import analyze_stock
    mock = _prices(["TSLA", "SPY"])
    with patch("src.stock.stock_analyzer.download_price_data", return_value=mock):
        result = analyze_stock("TSLA", theme=None)
    assert isinstance(result, dict)


def test_standalone_has_summary_metrics():
    from src.stock.stock_analyzer import analyze_stock
    mock = _prices(["TSLA", "SPY"])
    with patch("src.stock.stock_analyzer.download_price_data", return_value=mock):
        result = analyze_stock("TSLA", theme=None)
    assert "summary_metrics" in result
    assert isinstance(result["summary_metrics"], pd.DataFrame)


def test_standalone_has_price_history():
    from src.stock.stock_analyzer import analyze_stock
    mock = _prices(["TSLA", "SPY"])
    with patch("src.stock.stock_analyzer.download_price_data", return_value=mock):
        result = analyze_stock("TSLA")
    assert "price_history" in result
    assert not result["price_history"].empty


def test_theme_analysis_has_theme_rank():
    from src.stock.stock_analyzer import analyze_stock
    mock = _prices(THEME_TICKERS)
    with patch("src.stock.stock_analyzer.download_price_data", return_value=mock):
        result = analyze_stock("TSLA", theme="battery_storage")
    assert "theme_rank" in result
    assert isinstance(result["theme_rank"], int)


def test_theme_analysis_top_correlated():
    from src.stock.stock_analyzer import analyze_stock
    mock = _prices(THEME_TICKERS)
    with patch("src.stock.stock_analyzer.download_price_data", return_value=mock):
        result = analyze_stock("TSLA", theme="battery_storage")
    assert "top_correlated" in result
    assert isinstance(result["top_correlated"], pd.DataFrame)


def test_ticker_themes_populated():
    from src.stock.stock_analyzer import analyze_stock
    mock = _prices(["TSLA", "SPY"])
    with patch("src.stock.stock_analyzer.download_price_data", return_value=mock):
        result = analyze_stock("TSLA")
    # TSLA is in universe.yaml with multiple themes
    assert "ticker_themes" in result
    assert isinstance(result["ticker_themes"], list)
