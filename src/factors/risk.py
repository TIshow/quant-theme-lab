import numpy as np
import pandas as pd

from src.utils.constants import TRADING_DAYS_PER_YEAR


def _sharpe(returns: pd.Series, rf_daily: float = 0.0) -> float:
    if len(returns) < 5:
        return np.nan
    excess = returns - rf_daily
    std = excess.std()
    return float((excess.mean() / std) * TRADING_DAYS_PER_YEAR ** 0.5) if std > 1e-10 else np.nan


def _sortino(returns: pd.Series, rf_daily: float = 0.0) -> float:
    if len(returns) < 5:
        return np.nan
    excess = returns - rf_daily
    downside = excess[excess < 0].std()
    return float((excess.mean() / downside) * TRADING_DAYS_PER_YEAR ** 0.5) if downside > 0 else np.nan


def _calmar(returns: pd.Series, prices: pd.Series) -> float:
    if len(returns) < 21 or len(prices) < 2:
        return np.nan
    ann_ret = (1 + returns.mean()) ** TRADING_DAYS_PER_YEAR - 1
    dd = (prices - prices.cummax()) / prices.cummax()
    max_dd = abs(float(dd.min()))
    return float(ann_ret / max_dd) if max_dd > 0 else np.nan


def compute_risk_metrics(prices: pd.DataFrame, rf_annual: float = 0.0) -> pd.DataFrame:
    rf_daily = (1 + rf_annual) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    rows = []
    for ticker, grp in prices.groupby("Ticker"):
        g = grp.sort_values("Date").copy()
        ret = g["Close"].pct_change().dropna()
        n = len(ret)
        row: dict = {"Ticker": ticker}
        for label, days in [("3m", 63), ("6m", 126), ("12m", 252)]:
            row[f"sharpe_{label}"] = _sharpe(ret.iloc[-days:], rf_daily) if n >= days else np.nan
        row["sortino_12m"] = _sortino(ret.iloc[-252:], rf_daily) if n >= 252 else np.nan
        if n >= 252:
            row["calmar_12m"] = _calmar(ret.iloc[-252:], g["Close"].iloc[-(252 + 1):].reset_index(drop=True))
        else:
            row["calmar_12m"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)
