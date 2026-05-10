import pandas as pd
from src.factors.returns import compute_period_returns
from src.factors.volatility import compute_volatility
from src.factors.drawdown import compute_max_drawdown
from src.factors.liquidity import compute_liquidity
from src.factors.risk import compute_risk_metrics
from src.factors.moving_average import compute_moving_average_features


def _quality_flag(days: int) -> str:
    if days >= 252:
        return "OK"
    if days >= 120:
        return "LIMITED_HISTORY"
    if days > 0:
        return "VERY_SHORT_HISTORY"
    return "NO_DATA"


def build_factor_table(prices: pd.DataFrame) -> pd.DataFrame:
    history = pd.DataFrame([
        {"Ticker": t, "available_history_days": len(g), "data_quality_flag": _quality_flag(len(g))}
        for t, g in prices.groupby("Ticker")
    ])

    tables = [
        history,
        compute_period_returns(prices),
        compute_volatility(prices),
        compute_max_drawdown(prices),
        compute_liquidity(prices),
        compute_risk_metrics(prices),
        compute_moving_average_features(prices),
    ]

    result = tables[0]
    for tbl in tables[1:]:
        result = result.merge(tbl, on="Ticker", how="left")
    return result
