import pytest
import numpy as np
import pandas as pd
from src.scoring.scorer import rank_normalize, compute_scores
from src.scoring.ranking import rank_stocks


def _universe():
    return pd.DataFrame({
        "ticker": ["A", "B", "C", "D"],
        "name": ["Alpha", "Beta", "Gamma", "Delta"],
        "country": ["US", "US", "JP", "US"],
        "sector": ["tech", "tech", "materials", "industrials"],
        "theme_purity": [5, 3, 4, 5],
    })


def _factors():
    return pd.DataFrame({
        "Ticker": ["A", "B", "C", "D"],
        "return_1m": [0.05, 0.02, -0.01, 0.10],
        "return_3m": [0.15, 0.08, -0.05, 0.20],
        "return_6m": [0.20, 0.12, -0.10, 0.30],
        "return_12m": [0.30, 0.15, -0.20, 0.40],
        "annualized_volatility": [0.30, 0.25, 0.40, 0.35],
        "max_drawdown_12m": [-0.20, -0.15, -0.40, -0.25],
        "avg_traded_value_3m": [1e8, 5e7, 2e7, 3e8],
        "sharpe_6m": [1.2, 0.8, -0.5, 1.5],
        "sharpe_12m": [1.0, 0.7, -0.3, 1.3],
        "calmar_12m": [0.8, 0.5, -0.2, 1.0],
        "available_history_days": [300, 300, 300, 300],
        "data_quality_flag": ["OK", "OK", "OK", "OK"],
    })


def _weights():
    return {"momentum": 0.25, "volatility": 0.10, "drawdown": 0.10,
            "liquidity": 0.10, "theme_purity": 0.20, "risk_adjusted_return": 0.25}


def _config():
    return {
        "momentum_weights": {"return_1m": 0.2, "return_3m": 0.5, "return_6m": 0.3},
        "risk_adjusted_return_weights": {"sharpe_6m": 0.4, "sharpe_12m": 0.4, "calmar_12m": 0.2},
    }


def test_rank_normalize_bounded():
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    z = rank_normalize(s)
    assert z.min() >= 0.0 and z.max() <= 1.0


def test_rank_normalize_inversion():
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    up = rank_normalize(s, higher_is_better=True)
    down = rank_normalize(s, higher_is_better=False)
    assert abs((up + down - 1.0).max()) < 1e-10


def test_rank_normalize_outlier_robust():
    s = pd.Series([1.0, 2.0, 3.0, 1000.0])
    z = rank_normalize(s)
    # with winsorize, outlier should not dominate
    assert z.max() <= 1.0


def test_final_score_computed():
    scores = compute_scores(_factors(), _universe(), _weights(), _config())
    assert "final_score" in scores.columns
    assert scores["final_score"].notna().all()


def test_scores_in_unit_interval():
    scores = compute_scores(_factors(), _universe(), _weights(), _config())
    for col in ["momentum_score", "volatility_score", "drawdown_score", "liquidity_score"]:
        assert scores[col].between(0, 1).all(), f"{col} out of [0,1]"


def test_ranking_order():
    scores = compute_scores(_factors(), _universe(), _weights(), _config())
    ranking = rank_stocks(scores, _universe())
    assert ranking["rank"].iloc[0] == 1
    assert ranking["final_score"].is_monotonic_decreasing


def test_scores_with_nans():
    f = _factors()
    f.loc[0, "return_3m"] = np.nan
    f.loc[1, "sharpe_12m"] = np.nan
    scores = compute_scores(f, _universe(), _weights(), _config())
    assert "final_score" in scores.columns
    assert scores["final_score"].notna().all()
