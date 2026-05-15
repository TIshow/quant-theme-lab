import numpy as np
import pandas as pd


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def compute_technical_indicators(price_history: pd.DataFrame) -> dict:
    """Compute RSI, MACD, and Bollinger Bands from Close prices.

    Returns a dict with scalar summary values and time-series lists for charts.
    All time series are aligned to the same date index.
    """
    if price_history.empty or "Close" not in price_history.columns:
        return {}

    g = price_history.sort_values("Date").copy()
    close = g["Close"]
    dates = g["Date"].astype(str).tolist()

    # ── RSI (Wilder smoothing = EMA with alpha=1/period) ──────────────────────
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)

    # ── MACD ─────────────────────────────────────────────────────────────────
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    macd_line = ema12 - ema26
    macd_signal = _ema(macd_line, 9)
    macd_hist = macd_line - macd_signal

    # ── Bollinger Bands (20-day, ±2σ) ────────────────────────────────────────
    bb_mid = close.rolling(20, min_periods=10).mean()
    bb_std = close.rolling(20, min_periods=10).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    bb_bandwidth = (2 * bb_std / bb_mid.replace(0, np.nan)) * 100  # % of midline
    bb_pct_b = (close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)

    def _last(s: pd.Series):
        v = s.dropna()
        return float(v.iloc[-1]) if not v.empty else None

    def _tolist(s: pd.Series) -> list:
        return [None if np.isnan(x) else float(x) for x in s.tolist()]

    return {
        # Scalars (latest value)
        "rsi":          _last(rsi),
        "macd_line":    _last(macd_line),
        "macd_signal":  _last(macd_signal),
        "macd_hist":    _last(macd_hist),
        "bb_upper":     _last(bb_upper),
        "bb_middle":    _last(bb_mid),
        "bb_lower":     _last(bb_lower),
        "bb_bandwidth": _last(bb_bandwidth),
        "bb_pct_b":     _last(bb_pct_b),
        # Time series for charts
        "dates":              dates,
        "prices":             _tolist(close),
        "rsi_series":         _tolist(rsi),
        "macd_line_series":   _tolist(macd_line),
        "macd_signal_series": _tolist(macd_signal),
        "macd_hist_series":   _tolist(macd_hist),
        "bb_upper_series":    _tolist(bb_upper),
        "bb_middle_series":   _tolist(bb_mid),
        "bb_lower_series":    _tolist(bb_lower),
    }
