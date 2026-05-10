import numpy as np
import pandas as pd
from scipy.stats import rankdata
from scipy.stats.mstats import winsorize


def rank_normalize(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """
    Winsorize (5%/95%) → rank → [0, 1] normalize.
    More robust than z-score: bounded, resistant to outliers.
    Used instead of z-score to handle micro-cap / thin-volume outliers in the universe.
    """
    filled = series.fillna(float(series.median()) if not series.isna().all() else 0.0)
    arr = np.array(winsorize(filled.values, limits=[0.05, 0.05]), dtype=float)
    ranks = rankdata(arr).astype(float)
    n = len(ranks)
    normalized = (ranks - 1) / max(n - 1, 1)
    result = normalized if higher_is_better else 1.0 - normalized
    return pd.Series(result, index=series.index)


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    return df[name] if name in df.columns else pd.Series(np.nan, index=df.index)


def compute_scores(
    factor_df: pd.DataFrame,
    universe_df: pd.DataFrame,
    weights: dict,
    config: dict,
) -> pd.DataFrame:
    df = factor_df.copy()
    mw = config.get("momentum_weights", {"return_1m": 0.2, "return_3m": 0.5, "return_6m": 0.3})
    rw = config.get("risk_adjusted_return_weights", {"sharpe_6m": 0.4, "sharpe_12m": 0.4, "calmar_12m": 0.2})

    raw_mom = (
        _col(df, "return_1m").fillna(_col(df, "return_1m").median()) * mw.get("return_1m", 0.2)
        + _col(df, "return_3m").fillna(_col(df, "return_3m").median()) * mw.get("return_3m", 0.5)
        + _col(df, "return_6m").fillna(_col(df, "return_6m").median()) * mw.get("return_6m", 0.3)
    )
    df["momentum_score"] = rank_normalize(raw_mom, higher_is_better=True)

    df["volatility_score"] = rank_normalize(_col(df, "annualized_volatility"), higher_is_better=False)
    df["drawdown_score"] = rank_normalize(_col(df, "max_drawdown_12m"), higher_is_better=False)
    df["liquidity_score"] = rank_normalize(_col(df, "avg_traded_value_3m"), higher_is_better=True)

    raw_rar = (
        _col(df, "sharpe_6m").fillna(_col(df, "sharpe_6m").median()) * rw.get("sharpe_6m", 0.4)
        + _col(df, "sharpe_12m").fillna(_col(df, "sharpe_12m").median()) * rw.get("sharpe_12m", 0.4)
        + _col(df, "calmar_12m").fillna(_col(df, "calmar_12m").median()) * rw.get("calmar_12m", 0.2)
    )
    df["risk_adjusted_return_score"] = rank_normalize(raw_rar, higher_is_better=True)

    purity_map = universe_df.set_index("ticker")["theme_purity"].to_dict() if "ticker" in universe_df.columns else {}
    df["theme_purity_raw"] = df["Ticker"].map(purity_map).fillna(3.0)
    df["theme_purity_score"] = rank_normalize(df["theme_purity_raw"], higher_is_better=True)

    df["final_score"] = (
        df["momentum_score"] * weights.get("momentum", 0.25)
        + df["volatility_score"] * weights.get("volatility", 0.10)
        + df["drawdown_score"] * weights.get("drawdown", 0.10)
        + df["liquidity_score"] * weights.get("liquidity", 0.10)
        + df["theme_purity_score"] * weights.get("theme_purity", 0.20)
        + df["risk_adjusted_return_score"] * weights.get("risk_adjusted_return", 0.25)
    )
    return df
