"""
Walk-forward validation: out-of-sample test to detect in-sample overfitting.

At each step:
  - Train window : compute factor ranks on historical data
  - Test window  : hold top-N, measure actual realized return
  - Slide forward by test_months

Transaction costs mirror simple_backtest.py:
  - new position  : buy + sell = 2 × tc
  - held position : sell only  = 1 × tc
"""
import numpy as np
import pandas as pd
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run_walk_forward(
    prices: pd.DataFrame,
    train_months: int = 12,
    test_months: int = 3,
    top_n: int = 5,
    lookback_days: int = 63,
    transaction_cost_bps: float = 30.0,
    benchmark_ticker: str | None = None,
) -> pd.DataFrame:
    """
    Rolling walk-forward backtest.

    Returns one row per test-period month with portfolio and benchmark returns.
    """
    pivot = prices.pivot_table(index="Date", columns="Ticker", values="Close").sort_index()
    monthly = pivot.resample("ME").last()
    months = monthly.index.tolist()
    stock_cols = [c for c in pivot.columns if c != benchmark_ticker]
    tc = transaction_cost_bps / 10_000

    results = []
    prev_tickers: list[str] = []

    for start_i in range(train_months, len(months) - test_months):
        train_end = months[start_i - 1]
        test_start = months[start_i]
        test_end = months[start_i + test_months - 1]

        train_hist = pivot[pivot.index <= train_end].iloc[-lookback_days - 1:]
        mom = {}
        for t in stock_cols:
            s = train_hist[t].dropna()
            if len(s) > 5:
                mom[t] = s.iloc[-1] / s.iloc[0] - 1

        if len(mom) < top_n:
            continue

        selected = sorted(mom, key=lambda x: mom[x], reverse=True)[:top_n]

        test_months_idx = [m for m in months if test_start <= m <= test_end]
        for j, hold_date in enumerate(test_months_idx):
            entry_date = train_end if j == 0 else test_months_idx[j - 1]

            pf_rets = []
            for t in selected:
                p0 = pivot.loc[entry_date, t] if entry_date in pivot.index else np.nan
                p1 = pivot.loc[hold_date, t] if hold_date in pivot.index else np.nan
                if pd.notna(p0) and pd.notna(p1) and p0 > 0:
                    turnover = int(t not in prev_tickers)
                    cost = tc * (1 + turnover)  # new: 2tc, held: 1tc
                    pf_rets.append((p1 / p0) - 1 - cost)

            port_ret = float(np.mean(pf_rets)) if pf_rets else np.nan
            prev_tickers = selected

            row: dict = {
                "date": hold_date,
                "train_end": train_end,
                "portfolio_return": port_ret,
                "selected_tickers": ",".join(selected),
                "fold": start_i,
            }

            if benchmark_ticker and benchmark_ticker in pivot.columns:
                pb0 = pivot.loc[entry_date, benchmark_ticker] if entry_date in pivot.index else np.nan
                pb1 = pivot.loc[hold_date, benchmark_ticker] if hold_date in pivot.index else np.nan
                bm_ret = float((pb1 / pb0) - 1) if pd.notna(pb0) and pd.notna(pb1) and pb0 > 0 else np.nan
                row["benchmark_return"] = bm_ret
                row["excess_return"] = (port_ret - bm_ret) if pd.notna(port_ret) and pd.notna(bm_ret) else np.nan
            else:
                row["benchmark_return"] = np.nan
                row["excess_return"] = np.nan

            results.append(row)

    df = pd.DataFrame(results).drop_duplicates(subset=["date"], keep="last")
    if df.empty:
        return df
    df = df.sort_values("date").reset_index(drop=True)
    df["cumulative_return"] = (1 + df["portfolio_return"].fillna(0)).cumprod() - 1
    if "benchmark_return" in df.columns:
        df["benchmark_cumulative_return"] = (1 + df["benchmark_return"].fillna(0)).cumprod() - 1

    ret = df["portfolio_return"].dropna()
    logger.info(
        f"Walk-forward: Sharpe={_sharpe(ret):.2f}  n={len(ret)} months  "
        f"({train_months}M train / {test_months}M test)"
    )
    return df


def _sharpe(monthly_rets: pd.Series, rf_annual: float = 0.0) -> float:
    if len(monthly_rets) < 3:
        return np.nan
    rf_monthly = (1 + rf_annual) ** (1 / 12) - 1
    excess = monthly_rets - rf_monthly
    std = excess.std()
    return float((excess.mean() / std) * np.sqrt(12)) if std > 0 else np.nan
