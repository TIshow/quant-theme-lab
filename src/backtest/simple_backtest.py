"""
Monthly momentum top-N backtest with transaction costs and execution lag.

Logic:
  1. At each month-end, rank stocks by past `lookback_days` return.
  2. Select top-N (excluding benchmark ticker if present).
  3. Execute at open of `execution_lag_days` later (approximated as next close).
  4. Deduct `transaction_cost_bps` (one-way) on both entry and exit.
  5. Hold for one month, then repeat.
"""
import numpy as np
import pandas as pd
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run_monthly_momentum_top_n_backtest(
    prices: pd.DataFrame,
    top_n: int = 5,
    lookback_days: int = 63,
    transaction_cost_bps: float = 30.0,
    execution_lag_days: int = 1,
    benchmark_ticker: str | None = None,
) -> pd.DataFrame:
    pivot = prices.pivot_table(index="Date", columns="Ticker", values="Close").sort_index()
    monthly = pivot.resample("ME").last()
    months = monthly.index.tolist()

    # exclude benchmark from stock selection universe
    stock_cols = [c for c in pivot.columns if c != benchmark_ticker]

    results = []
    prev_tickers: list[str] = []

    for i in range(1, len(months)):
        rebal_date = months[i - 1]
        hold_date = months[i]

        hist_idx = pivot.index[pivot.index <= rebal_date]
        if len(hist_idx) < lookback_days:
            continue

        hist = pivot.loc[hist_idx].iloc[-lookback_days - 1 :]
        mom = {}
        for ticker in stock_cols:
            s = hist[ticker].dropna()
            if len(s) > 5:
                mom[ticker] = s.iloc[-1] / s.iloc[0] - 1

        if not mom:
            continue

        selected = sorted(mom, key=lambda x: mom[x], reverse=True)[:top_n]

        # execution price: next available close after lag
        all_dates = pivot.index[pivot.index > rebal_date]
        exec_date = all_dates[execution_lag_days - 1] if len(all_dates) >= execution_lag_days else rebal_date
        exit_dates = pivot.index[pivot.index > hold_date]
        exit_date = exit_dates[execution_lag_days - 1] if len(exit_dates) >= execution_lag_days else hold_date

        tc = transaction_cost_bps / 10_000  # one-way

        pf_rets = []
        for t in selected:
            p0 = pivot.loc[exec_date, t] if exec_date in pivot.index else np.nan
            p1 = pivot.loc[exit_date, t] if exit_date in pivot.index else np.nan
            if pd.notna(p0) and pd.notna(p1) and p0 > 0:
                # costs: buy on entry + sell on exit
                turnover = int(t not in prev_tickers)
                cost = tc * (1 + turnover)
                gross_ret = (p1 / p0) - 1
                pf_rets.append(gross_ret - cost)

        port_ret = float(np.mean(pf_rets)) if pf_rets else np.nan
        prev_tickers = selected

        row: dict = {
            "date": hold_date,
            "portfolio_return": port_ret,
            "selected_tickers": ",".join(selected),
            "n_holdings": len(selected),
        }

        if benchmark_ticker and benchmark_ticker in pivot.columns:
            pb0 = pivot.loc[exec_date, benchmark_ticker] if exec_date in pivot.index else np.nan
            pb1 = pivot.loc[exit_date, benchmark_ticker] if exit_date in pivot.index else np.nan
            bm_ret = float((pb1 / pb0) - 1) if pd.notna(pb0) and pd.notna(pb1) and pb0 > 0 else np.nan
            row["benchmark_return"] = bm_ret
            row["excess_return"] = (port_ret - bm_ret) if pd.notna(port_ret) and pd.notna(bm_ret) else np.nan
        else:
            row["benchmark_return"] = np.nan
            row["excess_return"] = np.nan

        results.append(row)

    df = pd.DataFrame(results)
    if df.empty:
        return df

    df["cumulative_return"] = (1 + df["portfolio_return"].fillna(0)).cumprod() - 1
    if "benchmark_return" in df.columns:
        df["benchmark_cumulative_return"] = (1 + df["benchmark_return"].fillna(0)).cumprod() - 1

    # summary stats
    ret = df["portfolio_return"].dropna()
    logger.info(
        f"Backtest: Sharpe={_sharpe(ret):.2f}  MaxDD={_max_dd(df['cumulative_return']):.1%}  "
        f"Ann.Return={((1+ret.mean())**12-1):.1%}  n={len(ret)}"
    )
    return df


def _sharpe(monthly_rets: pd.Series) -> float:
    if len(monthly_rets) < 3 or monthly_rets.std() == 0:
        return np.nan
    return float((monthly_rets.mean() / monthly_rets.std()) * np.sqrt(12))


def _max_dd(cum_ret: pd.Series) -> float:
    equity = 1 + cum_ret
    return float(((equity - equity.cummax()) / equity.cummax()).min())
