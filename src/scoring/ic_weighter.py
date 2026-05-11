import numpy as np
import pandas as pd
from src.analytics.factor_validation import compute_ic_timeseries, compute_icir
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Representative factor for each scoring component
_COMPONENT_FACTOR = {
    "momentum": "return_3m",
    "volatility": "annualized_volatility",
    "drawdown": "max_drawdown_12m",
    "liquidity": "avg_volume_3m",
    "risk_adjusted_return": "sharpe_6m",
}


def compute_ic_weights(
    prices: pd.DataFrame,
    yaml_weights: dict,
    min_periods: int = 12,
) -> tuple[dict, pd.DataFrame]:
    """
    Derive factor weights from ICIR instead of hardcoded YAML values.

    theme_purity keeps its YAML weight (not a price factor).
    All other components are weighted proportional to abs(ICIR).
    Falls back to YAML weights if there is insufficient history.

    NOTE — In-sample bias: IC weights are computed on the full price history
    passed in. When the same history is used in simple_backtest.py, this
    introduces look-ahead bias in the weight selection. These weights are
    best interpreted as "current scoring weights", not as walk-forward-valid
    backtest inputs. See walk_forward.py for out-of-sample validation.

    Returns:
        weights:    component → weight dict (sums to 1.0)
        ic_summary: DataFrame with IC/ICIR per component for reporting
    """
    rows = []
    icir_map: dict[str, float] = {}

    for component, factor_col in _COMPONENT_FACTOR.items():
        logger.info(f"IC validation: {component} ({factor_col})")
        ic_series = compute_ic_timeseries(prices, factor_col)
        icir = compute_icir(ic_series)
        mean_ic = float(ic_series.mean()) if not ic_series.empty else np.nan
        n = len(ic_series.dropna())

        # Lower-is-better factors (volatility, drawdown) have negative IC by design — use abs
        abs_icir = abs(icir) if not np.isnan(icir) else 0.0
        # Require enough periods; otherwise treat as noise
        effective = abs_icir if n >= min_periods else 0.0

        icir_map[component] = effective
        rows.append({
            "component": component,
            "factor": factor_col,
            "mean_ic": round(mean_ic, 4) if not np.isnan(mean_ic) else np.nan,
            "icir": round(icir, 4) if not np.isnan(icir) else np.nan,
            "abs_icir": round(abs_icir, 4),
            "n_periods": n,
            "usable": effective > 0.3,
        })

    ic_summary = pd.DataFrame(rows).sort_values("abs_icir", ascending=False)

    total = sum(icir_map.values())
    if total == 0:
        logger.warning("All ICIRs zero or insufficient data — falling back to YAML weights")
        return yaml_weights, ic_summary

    purity_weight = yaml_weights.get("theme_purity", 0.20)
    remaining = 1.0 - purity_weight

    weights = {c: (v / total) * remaining for c, v in icir_map.items()}
    weights["theme_purity"] = purity_weight

    logger.info("IC weights: " + ", ".join(f"{k}={v:.3f}" for k, v in weights.items()))
    return weights, ic_summary
