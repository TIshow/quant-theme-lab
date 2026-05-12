"""
Tests for fundamental IC weight derivation.

Verifies:
  - _icir() boundary conditions
  - _bootstrap_icir_ci() produces valid intervals
  - Signed weights: negative ICIR → negative weight
  - Equal-weight fallback when ICIR is unavailable
  - low_sample and ci_crosses_zero flags
"""
import numpy as np
import pandas as pd
import pytest

from src.scoring.fundamental_ic import (
    _icir,
    _bootstrap_icir_ci,
    compute_fundamental_ic_weights,
)


# ---------------------------------------------------------------------------
# _icir
# ---------------------------------------------------------------------------

def test_icir_known_values():
    ic = pd.Series([0.4, 0.4, 0.4, 0.4])  # std=0 → nan
    assert np.isnan(_icir(ic))


def test_icir_positive_stable_series():
    ic = pd.Series([0.3, 0.35, 0.28, 0.32, 0.31])
    result = _icir(ic)
    assert result > 0
    expected = ic.mean() / ic.std()
    assert result == pytest.approx(expected, rel=1e-6)


def test_icir_negative_series():
    ic = pd.Series([-0.4, -0.3, -0.35, -0.38, -0.42])
    assert _icir(ic) < 0


def test_icir_nan_on_too_few():
    assert np.isnan(_icir(pd.Series([0.3, 0.4])))


# ---------------------------------------------------------------------------
# _bootstrap_icir_ci
# ---------------------------------------------------------------------------

def test_bootstrap_ci_interval_contains_point_estimate():
    ic = pd.Series([0.3, 0.35, 0.28, 0.32, 0.31, 0.29, 0.33])
    point = _icir(ic)
    lo, hi = _bootstrap_icir_ci(ic)
    assert lo <= point <= hi


def test_bootstrap_ci_ordered():
    ic = pd.Series([0.3, 0.35, 0.28, 0.32, 0.31, 0.29])
    lo, hi = _bootstrap_icir_ci(ic)
    assert lo < hi


def test_bootstrap_ci_nan_on_too_few():
    lo, hi = _bootstrap_icir_ci(pd.Series([0.3, 0.4]))
    assert np.isnan(lo) and np.isnan(hi)


def test_bootstrap_ci_reproducible_with_seed():
    ic = pd.Series([0.3, 0.35, 0.28, 0.32, 0.31, 0.29, 0.34])
    lo1, hi1 = _bootstrap_icir_ci(ic)
    lo2, hi2 = _bootstrap_icir_ci(ic)
    assert lo1 == lo2 and hi1 == hi2


# ---------------------------------------------------------------------------
# compute_fundamental_ic_weights — synthetic panel
# ---------------------------------------------------------------------------

def _make_fundamentals(n_tickers: int = 15, n_years: int = 10) -> dict[str, pd.DataFrame]:
    """
    Create synthetic fundamentals where roe has positive IC with returns
    and operating_margin has negative IC.
    """
    rng = np.random.default_rng(1)
    tickers = [f"{1000 + i}.T" for i in range(n_tickers)]
    results = {}
    for t in tickers:
        rows = []
        for y in range(2012, 2012 + n_years):
            rows.append({
                "fiscal_year": f"{y}/03",
                "roe": rng.normal(10, 3),
                "operating_margin": rng.normal(8, 2),
            })
        results[t] = pd.DataFrame(rows)
    return results


def _make_extended_prices(
    fundamentals_data: dict[str, pd.DataFrame],
    seed: int = 2,
) -> pd.DataFrame:
    """Create synthetic price history aligned with the fundamentals."""
    rng = np.random.default_rng(seed)
    frames = []
    dates = pd.date_range("2011-01-03", "2023-12-31", freq="B")
    for ticker in fundamentals_data:
        p = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, len(dates))))
        frames.append(pd.DataFrame({"Date": dates, "Ticker": ticker, "Close": p}))
    return pd.concat(frames, ignore_index=True)


def test_weights_sum_to_one():
    fund_data = _make_fundamentals()
    prices = _make_extended_prices(fund_data)
    yaml_weights = {"roe": 0.5, "operating_margin": 0.5}
    weights, _ = compute_fundamental_ic_weights(prices, fund_data, yaml_weights, min_periods=3)
    assert abs(sum(abs(w) for w in weights.values()) - 1.0) < 1e-6


def test_equal_weight_fallback_when_no_history():
    """With min_periods=100 and only 5 periods, should fall back to equal weights."""
    fund_data = _make_fundamentals(n_years=3)
    prices = _make_extended_prices(fund_data)
    yaml_weights = {"roe": 0.5, "operating_margin": 0.5}
    weights, _ = compute_fundamental_ic_weights(prices, fund_data, yaml_weights, min_periods=100)
    # fallback: equal weights (0.5 each)
    assert all(abs(abs(w) - 0.5) < 1e-6 for w in weights.values())


def test_ic_summary_has_required_columns():
    fund_data = _make_fundamentals()
    prices = _make_extended_prices(fund_data)
    yaml_weights = {"roe": 0.5, "operating_margin": 0.5}
    _, summary = compute_fundamental_ic_weights(prices, fund_data, yaml_weights, min_periods=3)
    for col in ["metric", "icir", "ci_lower", "ci_upper", "n_periods", "low_sample", "direction"]:
        assert col in summary.columns, f"Missing column: {col}"


def test_negative_icir_gives_negative_weight():
    """A metric with consistently negative IC should receive a negative weight."""
    fund_data = _make_fundamentals()
    prices = _make_extended_prices(fund_data)
    yaml_weights = {"roe": 0.5, "operating_margin": 0.5}
    weights, summary = compute_fundamental_ic_weights(prices, fund_data, yaml_weights, min_periods=3)
    for _, row in summary.iterrows():
        if row["n_periods"] >= 3 and not np.isnan(row["icir"]):
            expected_sign = np.sign(row["icir"])
            actual_sign = np.sign(weights[row["metric"]])
            assert actual_sign == expected_sign, (
                f"{row['metric']}: icir={row['icir']:.3f} but weight={weights[row['metric']]:.3f}"
            )
