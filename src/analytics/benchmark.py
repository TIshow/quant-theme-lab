import numpy as np
import pandas as pd
from scipy.stats import linregress

from src.utils.constants import TRADING_DAYS_PER_YEAR


def compute_benchmark_relative_returns(
    asset_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> pd.DataFrame:
    df = pd.concat([asset_returns.rename("asset"), benchmark_returns.rename("benchmark")], axis=1).dropna()
    df["excess"] = df["asset"] - df["benchmark"]
    df["cum_asset"] = (1 + df["asset"]).cumprod()
    df["cum_benchmark"] = (1 + df["benchmark"]).cumprod()
    df["cum_excess"] = (1 + df["excess"]).cumprod()
    return df


def compute_beta(asset_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    df = pd.concat([asset_returns, benchmark_returns], axis=1).dropna()
    if len(df) < 10:
        return np.nan
    slope, *_ = linregress(df.iloc[:, 1], df.iloc[:, 0])
    return float(slope)


def compute_alpha(
    asset_returns: pd.Series,
    benchmark_returns: pd.Series,
    rf_annual: float = 0.0,
) -> float:
    beta = compute_beta(asset_returns, benchmark_returns)
    if np.isnan(beta):
        return np.nan
    df = pd.concat([asset_returns, benchmark_returns], axis=1).dropna()
    rf_daily = rf_annual / TRADING_DAYS_PER_YEAR
    return float((df.iloc[:, 0].mean() - rf_daily - beta * (df.iloc[:, 1].mean() - rf_daily)) * TRADING_DAYS_PER_YEAR)
