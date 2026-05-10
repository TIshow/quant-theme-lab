"""
IC-based weight derivation for fundamental (annual) factors.

Algorithm per metric:
  1. Build cross-sectional panel: (fiscal_year, ticker, metric_value, forward_12m_return)
     - filing lag = fiscal_year_end + 90 days
     - forward return = price(filing + 365d) / price(filing) - 1
  2. Compute Spearman IC at each fiscal year (cross-sectional)
  3. ICIR = mean(IC) / std(IC)
  4. Weight ∝ abs(ICIR); fallback to equal weights if n_periods < min_periods
"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.utils.logger import get_logger

logger = get_logger(__name__)


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


def _ic_series_from_panel(panel: pd.DataFrame) -> pd.Series:
    """Cross-sectional Spearman IC per fiscal year."""
    ic_values = {}
    for fy, group in panel.groupby("fiscal_year"):
        if len(group) < 5:
            continue
        corr, _ = spearmanr(group["metric_value"], group["forward_return"])
        if not np.isnan(corr):
            ic_values[fy] = float(corr)
    return pd.Series(ic_values)


def _icir(ic_series: pd.Series) -> float:
    clean = ic_series.dropna()
    if len(clean) < 3 or clean.std() == 0:
        return np.nan
    return float(clean.mean() / clean.std())


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
        ic_summary: DataFrame for reporting
    """
    metric_names = list(yaml_weights.keys())
    icir_map: dict[str, float] = {}
    rows = []

    for metric in metric_names:
        logger.info(f"Fundamental IC: {metric}")
        panel = _build_panel(prices, fundamentals_data, f"fundamental_{metric}")
        if panel.empty:
            # Try without prefix (KPI columns added by theme plugin)
            panel = _build_panel(prices, fundamentals_data, metric)

        ic_s = _ic_series_from_panel(panel)
        icir_val = _icir(ic_s)
        mean_ic = float(ic_s.mean()) if not ic_s.empty else np.nan
        n = len(ic_s.dropna())

        abs_icir = abs(icir_val) if not np.isnan(icir_val) else 0.0
        effective = abs_icir if n >= min_periods else 0.0
        icir_map[metric] = effective

        rows.append({
            "metric": metric,
            "mean_ic": round(mean_ic, 4) if not np.isnan(mean_ic) else np.nan,
            "icir": round(icir_val, 4) if not np.isnan(icir_val) else np.nan,
            "abs_icir": round(abs_icir, 4),
            "n_periods": n,
            "usable": effective > 0.15,  # lower threshold for annual data
        })

    ic_summary = pd.DataFrame(rows).sort_values("abs_icir", ascending=False)

    total = sum(icir_map.values())
    if total == 0:
        logger.warning("All fundamental ICIRs zero — equal weights applied")
        n = len(metric_names)
        weights = {m: 1.0 / n for m in metric_names}
    else:
        weights = {m: v / total for m, v in icir_map.items()}

    logger.info("Fundamental IC weights: " + ", ".join(f"{k}={v:.3f}" for k, v in weights.items()))
    return weights, ic_summary
