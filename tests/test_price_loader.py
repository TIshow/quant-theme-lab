import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch


def _fake(ticker: str, n: int = 60) -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=n, freq="B")
    p = 100 * (1 + np.random.randn(n).cumsum() * 0.01)
    return pd.DataFrame({
        "Date": dates, "Open": p * 0.99, "High": p * 1.01,
        "Low": p * 0.98, "Close": p, "Adj Close": p,
        "Volume": np.random.randint(100_000, 1_000_000, n),
    })


def test_returns_dataframe():
    from src.data.price_loader import download_price_data
    with patch("yfinance.download", return_value=_fake("TSLA")):
        df = download_price_data(["TSLA"], start_date="2024-01-01")
    assert isinstance(df, pd.DataFrame)


def test_has_date_column():
    from src.data.price_loader import download_price_data
    with patch("yfinance.download", return_value=_fake("TSLA")):
        df = download_price_data(["TSLA"], start_date="2024-01-01")
    assert "Date" in df.columns


def test_has_ticker_column():
    from src.data.price_loader import download_price_data
    with patch("yfinance.download", return_value=_fake("TSLA")):
        df = download_price_data(["TSLA"], start_date="2024-01-01")
    assert "Ticker" in df.columns
    assert df["Ticker"].iloc[0] == "TSLA"


def test_has_close_column():
    from src.data.price_loader import download_price_data
    with patch("yfinance.download", return_value=_fake("TSLA")):
        df = download_price_data(["TSLA"], start_date="2024-01-01")
    assert "Close" in df.columns


def test_failed_ticker_does_not_crash():
    from src.data.price_loader import download_price_data
    def side_effect(ticker, **kwargs):
        if ticker == "GOOD":
            return _fake("GOOD")
        return pd.DataFrame()
    with patch("yfinance.download", side_effect=side_effect):
        df = download_price_data(["GOOD", "BAD"], start_date="2024-01-01")
    assert "GOOD" in df["Ticker"].values
    assert "BAD" not in df["Ticker"].values
