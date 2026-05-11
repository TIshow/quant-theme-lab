"""
IC-based weight derivation for fundamental (annual) factors.

Algorithm per metric:
  1. Build cross-sectional panel: (fiscal_year, ticker, metric_value, forward_12m_return)
     - filing lag = fiscal_year_end + 90 days
     - forward return = price(filing + 365d) / price(filing) - 1
  2. Compute Spearman IC at each fiscal year (cross-sectional)
  3. ICIR = mean(IC) / std(IC)
  4. Bootstrap 95% CI on ICIR — flag as low_sample when n_tickers/year < 20
  5. Weight ∝ abs(ICIR); fallback to equal weights if n_periods < min_periods
"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.utils.logger import get_logger

logger = get_logger(__name__)

_LOW_SAMPLE_THRESHOLD = 20  # tickers/year below which ICIR CI is wide


def _get_price_nearest(price_series: pd.Series, date: pd.Timestamp) -> float | None:
    """Return the first available price on or after date."""
    future = price_series.dropna()
    future = future[future.index >= date]
    return float(future.iloc[0]) if not future.empty else None


def _build_panel(
    prices: pd.DataFrame,
    fundamentals_data: dict[str, pd.DataFrame],
    metric: str,
    filing_lag_days: int = 90,
    forward_days: int = 365,
) -> pd.DataFrame:
    """
    Build aligned (fiscal_year, ticker, metric_value, forward_return) panel.
    Skips rows where price data is unavailable.
    """
    pivot = prices.pivot_table(index="Date", columns="Ticker", values="Close")

    records = []
    for ticker, fund_df in fundamentals_data.items():
        if fund_df.empty or metric not in fund_df.columns:
            continue
        actual = fund_df[~fund_df["fiscal_year"].str.contains("予", na=False)]

        for _, row in actual.iterrows():
            fy = row["fiscal_year"]
            val = row.get(metric)
            if pd.isna(val):
                continue

            try:
                fy_end = pd.to_datetime(fy + "/01", format="%Y/%m/%d") + pd.offsets.MonthEnd(0)
            except Exception:
                continue

            filing_date = fy_end + pd.Timedelta(days=filing_lag_days)
            fwd_date = filing_date + pd.Timedelta(days=forward_days)

            if ticker not in pivot.columns:
                continue

            ticker_prices = pivot[ticker]
            p0 = _get_price_nearest(ticker_prices, filing_date)
            p1 = _get_price_nearest(ticker_prices, fwd_date)

            if p0 is None or p1 is None or p0 == 0:
                continue

            records.append({
                "fiscal_year": fy,
                "ticker": ticker,
                "metric_value": float(val),
                "forward_return": p1 / p0 - 1,
            })

    return pd.DataFrame(records)


def _ic_series_from_panel(panel: pd.DataFrame) -> tuple[pd.Series, float]:
    """
    Cross-sectional Spearman IC per fiscal year.
    Returns (ic_series, avg_tickers_per_year).
    """
    ic_values = {}
    ticker_counts = []
    for fy, group in panel.groupby("fiscal_year"):
        if len(group) < 5:
            continue
        ticker_counts.append(len(group))
        corr, _ = spearmanr(group["metric_value"], group["forward_return"])
        if not np.isnan(corr):
            ic_values[fy] = float(corr)
    avg_n = float(np.mean(ticker_counts)) if ticker_counts else 0.0
    return pd.Series(ic_values), avg_n


def _icir(ic_series: pd.Series) -> float:
    clean = ic_series.dropna()
    if len(clean) < 3 or clean.std() == 0:
        return np.nan
    return float(clean.mean() / clean.std())


def _bootstrap_icir_ci(
    ic_series: pd.Series,
    n_boot: int = 1000,
    ci: float = 0.95,
) -> tuple[float, float]:
    """
    Bootstrap percentile confidence interval for ICIR.
    Wide CI (crossing zero) indicates the signal may be noise.
    """
    clean = ic_series.dropna().values
    if len(clean) < 3:
        return np.nan, np.nan
    rng = np.random.default_rng(42)
    boot_icirs = []
    for _ in range(n_boot):
        sample = rng.choice(clean, size=len(clean), replace=True)
        s = sample.std()
        if s > 0:
            boot_icirs.append(float(sample.mean() / s))
    if len(boot_icirs) < 10:
        return np.nan, np.nan
    alpha = (1 - ci) / 2
    return float(np.quantile(boot_icirs, alpha)), float(np.quantile(boot_icirs, 1 - alpha))


def compute_fundamental_ic_weights(
    prices: pd.DataFrame,
    fundamentals_data: dict[str, pd.DataFrame],
    yaml_weights: dict,
    min_periods: int = 6,
) -> tuple[dict, pd.DataFrame]:
    """
    Derive fundamental factor weights from annual IC/ICIR.

    Falls back to equal weights per metric when ICIR is unavailable
    (e.g., insufficient history).

    Returns:
        weights:    {metric_name: weight}  (values sum to 1.0)
        ic_summary: DataFrame for reporting (includes bootstrap CI and low_sample flag)
    """
    metric_names = list(yaml_weights.keys())
    icir_map: dict[str, tuple[float, float]] = {}
    rows = []

    for metric in metric_names:
        logger.info(f"Fundamental IC: {metric}")
        panel = _build_panel(prices, fundamentals_data, f"fundamental_{metric}")
        if panel.empty:
            panel = _build_panel(prices, fundamentals_data, metric)

        ic_s, avg_tickers = _ic_series_from_panel(panel)
        icir_val = _icir(ic_s)
        mean_ic = float(ic_s.mean()) if not ic_s.empty else np.nan
        n = len(ic_s.dropna())

        ci_lo, ci_hi = _bootstrap_icir_ci(ic_s)
        # Low-sample: avg tickers per year below threshold → CI is wide, interpret cautiously
        low_sample = avg_tickers < _LOW_SAMPLE_THRESHOLD

        abs_icir = abs(icir_val) if not np.isnan(icir_val) else 0.0
        effective = abs_icir if n >= min_periods else 0.0
        sign = float(np.sign(icir_val)) if not np.isnan(icir_val) and icir_val != 0 else 1.0
        icir_map[metric] = (effective, sign)

        # CI crosses zero → signal may be noise regardless of point estimate
        ci_crosses_zero = (
            pd.notna(ci_lo) and pd.notna(ci_hi) and ci_lo < 0 < ci_hi
        )

        rows.append({
            "metric": metric,
            "mean_ic": round(mean_ic, 4) if not np.isnan(mean_ic) else np.nan,
            "icir": round(icir_val, 4) if not np.isnan(icir_val) else np.nan,
            "abs_icir": round(abs_icir, 4),
            "ci_lower": round(ci_lo, 3) if pd.notna(ci_lo) else np.nan,
            "ci_upper": round(ci_hi, 3) if pd.notna(ci_hi) else np.nan,
            "ci_crosses_zero": ci_crosses_zero,
            "avg_tickers_per_year": round(avg_tickers, 1),
            "n_periods": n,
            "low_sample": low_sample,
            "direction": "低いほど良い" if sign < 0 else "高いほど良い",
            "usable": effective > 0.15,
        })

    ic_summary = pd.DataFrame(rows).sort_values("abs_icir", ascending=False)

    total = sum(v for v, _ in icir_map.values())
    if total == 0:
        logger.warning("All fundamental ICIRs zero — equal weights applied")
        n_m = len(metric_names)
        weights = {m: 1.0 / n_m for m in metric_names}
    else:
        weights = {m: (abs_icir / total) * sign for m, (abs_icir, sign) in icir_map.items()}

    # Warn when dominant metrics have CI crossing zero
    uncertain = [
        r["metric"] for _, r in ic_summary.iterrows()
        if r.get("ci_crosses_zero") and abs(weights.get(r["metric"], 0)) > 0.1
    ]
    if uncertain:
        logger.warning(
            f"High-weight metrics with CI crossing zero (statistically uncertain): {uncertain}"
        )

    logger.info("Fundamental IC weights (signed): " + ", ".join(f"{k}={v:+.3f}" for k, v in weights.items()))
    return weights, ic_summary
