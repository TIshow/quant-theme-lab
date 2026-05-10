import numpy as np
import pandas as pd


def _sharpe(returns: pd.Series) -> float:
    if len(returns) < 5:
        return np.nan
    std = returns.std()
    return float((returns.mean() / std) * np.sqrt(252)) if std > 0 else np.nan


def _sortino(returns: pd.Series) -> float:
    if len(returns) < 5:
        return np.nan
    downside = returns[returns < 0].std()
    return float((returns.mean() / downside) * np.sqrt(252)) if downside > 0 else np.nan


def _calmar(returns: pd.Series, prices: pd.Series) -> float:
    if len(returns) < 21 or len(prices) < 2:
        return np.nan
    ann_ret = (1 + returns.mean()) ** 252 - 1
    dd = (prices - prices.cummax()) / prices.cummax()
    max_dd = abs(float(dd.min()))
    return float(ann_ret / max_dd) if max_dd > 0 else np.nan


def compute_risk_metrics(prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticker, grp in prices.groupby("Ticker"):
        g = grp.sort_values("Date").copy()
        ret = g["Close"].pct_change().dropna()
        n = len(ret)
        row: dict = {"Ticker": ticker}
        for label, days in [("3m", 63), ("6m", 126), ("12m", 252)]:
            row[f"sharpe_{label}"] = _sharpe(ret.iloc[-days:]) if n >= days else np.nan
        row["sortino_12m"] = _sortino(ret.iloc[-252:]) if n >= 252 else np.nan
        if n >= 252:
            row["calmar_12m"] = _calmar(ret.iloc[-252:], g["Close"].iloc[-(252 + 1):].reset_index(drop=True))
        else:
            row["calmar_12m"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)
