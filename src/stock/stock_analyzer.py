import numpy as np
import pandas as pd
from src.config.loader import load_theme_config, get_theme_universe, get_weights, get_benchmark, get_cost_benchmarks, load_universe, get_risk_free_rate
from src.data.price_loader import download_price_data
from src.data.irbank_scraper import fetch_fundamentals
from src.data.yfinance_fundamentals import fetch_us_fundamentals
from src.factors.factor_table import build_factor_table
from src.factors.fundamental_valuation import compute_fundamental_metrics
from src.factors.technical import compute_technical_indicators
from src.scoring.scorer import compute_scores
from src.scoring.ranking import rank_stocks
from src.analytics.correlation import compute_correlation_matrix, get_top_correlated_stocks
from src.analytics.benchmark import compute_beta, compute_alpha
from src.utils.logger import get_logger

logger = get_logger(__name__)


def analyze_stock(
    ticker: str,
    theme: str | None = None,
    start_date: str = "2023-01-01",
) -> dict:
    if theme:
        return _analyze_with_theme(ticker, theme, start_date)
    return _analyze_standalone(ticker, start_date)


def _benchmark_metrics(asset_ret: pd.Series, bm_ret: pd.Series, benchmark_ticker: str) -> dict:
    aligned = pd.concat([asset_ret, bm_ret], axis=1).dropna()
    corr = float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1])) if len(aligned) > 8 else np.nan
    return {
        "beta": compute_beta(asset_ret, bm_ret),
        "alpha": compute_alpha(asset_ret, bm_ret),
        "corr": corr,
        "benchmark_ticker": benchmark_ticker,
    }


def _close_series(price_df: pd.DataFrame) -> pd.Series:
    """Date-indexed close-price series from a price-history frame."""
    return price_df.set_index("Date")["Close"].sort_index()


def _returns_at(close: pd.Series, freq: str) -> pd.Series:
    """Period-return series. freq='D' (daily) or a resample rule like 'ME'/'W'."""
    px = close if freq == "D" else close.resample(freq).last()
    return px.pct_change().dropna()


def _cost_driver_metrics(
    price_history: pd.DataFrame,
    cost_benchmarks: list[dict],
    start_date: str,
) -> list[dict]:
    """Auto-compare a stock against configured cost-driver indices.

    For margin-sensitive sectors (中食 / 物流), input costs (rice, grains,
    edible oil, fuel, FX) act on quarterly margins, so daily co-movement is
    typically weak. We report correlation at daily AND monthly horizons plus
    a monthly beta, so slow cost pass-through is visible.
    """
    if not cost_benchmarks or price_history.empty:
        return []
    driver_tickers = [c["ticker"] for c in cost_benchmarks]
    try:
        driver_prices = download_price_data(driver_tickers, start_date=start_date)
    except RuntimeError:
        logger.warning("No cost-driver price data downloaded")
        return []

    asset_close = _close_series(price_history)
    asset_d = _returns_at(asset_close, "D")
    asset_m = _returns_at(asset_close, "ME")

    out = []
    for c in cost_benchmarks:
        dt = c["ticker"]
        dp = driver_prices[driver_prices["Ticker"] == dt]
        if dp.empty:
            logger.warning(f"  cost driver missing: {dt}")
            continue
        dclose = _close_series(dp)
        d_d = _returns_at(dclose, "D")
        d_m = _returns_at(dclose, "ME")

        pair_d = pd.concat([asset_d, d_d], axis=1).dropna()
        pair_m = pd.concat([asset_m, d_m], axis=1).dropna()
        corr_d = float(pair_d.iloc[:, 0].corr(pair_d.iloc[:, 1])) if len(pair_d) > 8 else np.nan
        corr_m = float(pair_m.iloc[:, 0].corr(pair_m.iloc[:, 1])) if len(pair_m) > 6 else np.nan
        beta_m = compute_beta(asset_m, d_m) if len(pair_m) > 6 else np.nan

        out.append({
            "ticker": dt,
            "label": c.get("label", dt),
            "corr_daily": corr_d,
            "corr_monthly": corr_m,
            "beta_monthly": beta_m,
            "n_monthly": int(len(pair_m)),
        })
    return out


def _analyze_with_theme(ticker: str, theme: str, start_date: str) -> dict:
    config = load_theme_config(theme)
    universe_df = get_theme_universe(theme, config)
    weights = get_weights(config)
    start_date = config["analysis"].get("start_date", start_date)
    benchmark_ticker = get_benchmark(config, "US")

    tickers = universe_df["ticker"].tolist()
    all_tickers = list(dict.fromkeys(tickers + [benchmark_ticker]))
    prices = download_price_data(all_tickers, start_date=start_date)

    theme_prices = prices[prices["Ticker"].isin(tickers)].copy()
    factor_df = build_factor_table(theme_prices)
    scores = compute_scores(factor_df, universe_df, weights, config)
    ranking = rank_stocks(scores, universe_df)

    price_history = prices[prices["Ticker"] == ticker].sort_values("Date").copy()
    if price_history.empty:
        logger.warning(f"{ticker} not in downloaded prices")

    ticker_row = ranking[ranking["Ticker"] == ticker]
    theme_rank = int(ticker_row["rank"].values[0]) if not ticker_row.empty else None
    ranking_row = ticker_row.iloc[0] if not ticker_row.empty else pd.Series(dtype=float)

    category_rank = (
        int(ticker_row["region_rank"].values[0])
        if not ticker_row.empty and "region_rank" in ticker_row.columns
        else None
    )

    corr_matrix = compute_correlation_matrix(theme_prices)
    top_correlated = get_top_correlated_stocks(corr_matrix, ticker, top_n=5)

    benchmark_metrics: dict = {}
    if not price_history.empty and benchmark_ticker in prices["Ticker"].values:
        bm_prices = prices[prices["Ticker"] == benchmark_ticker].sort_values("Date")
        asset_ret = _returns_at(_close_series(price_history), "D")
        bm_ret = _returns_at(_close_series(bm_prices), "D")
        benchmark_metrics = _benchmark_metrics(asset_ret, bm_ret, benchmark_ticker)

    # Auto cost-driver comparison (e.g. food/logistics vs rice/grains/fuel/FX),
    # analogous to how semiconductor themes auto-compare against SOXX.
    cost_metrics = _cost_driver_metrics(price_history, get_cost_benchmarks(config), start_date)

    meta = universe_df[universe_df["ticker"] == ticker]
    name = meta["name"].values[0] if not meta.empty else ticker
    sector = meta["sector"].values[0] if not meta.empty and "sector" in meta.columns else None

    # all-theme membership for this ticker
    full_universe = load_universe()
    ticker_themes = full_universe[full_universe["ticker"] == ticker][["theme", "theme_purity"]].to_dict("records")

    factor_row = factor_df[factor_df["Ticker"] == ticker].iloc[0] if not factor_df[factor_df["Ticker"] == ticker].empty else pd.Series(dtype=float)
    summary_metrics = _build_summary_metrics(price_history, factor_row)

    data_quality = {
        "available_history_days": int(ranking_row.get("available_history_days", len(price_history))),
        "data_quality_flag": ranking_row.get("data_quality_flag", "UNKNOWN"),
    }

    fundamental_metrics = _fetch_fundamental_metrics(ticker, price_history)
    country = "JP" if ticker.endswith(".T") else "US"
    rf = config.get("backtest", {}).get("risk_free_rate_annual") or get_risk_free_rate(country)

    return {
        "ticker": ticker,
        "name": name,
        "sector": sector,
        "theme": theme,
        "ticker_themes": ticker_themes,
        "summary_metrics": summary_metrics,
        "fundamental_metrics": fundamental_metrics,
        "technical": compute_technical_indicators(price_history),
        "theme_rank": theme_rank,
        "category_rank": category_rank,
        "ranking_row": ranking_row,
        "ranking_df": ranking,
        "top_correlated": top_correlated,
        "price_history": price_history,
        "benchmark_metrics": benchmark_metrics,
        "cost_metrics": cost_metrics,
        "risk_free_rate": rf,
        "data_quality": data_quality,
    }


def _analyze_standalone(ticker: str, start_date: str) -> dict:
    country = "JP" if ticker.endswith(".T") else "US"
    benchmark_ticker = "1306.T" if country == "JP" else "SPY"
    rf = get_risk_free_rate(country)

    prices = download_price_data([ticker, benchmark_ticker], start_date=start_date)
    price_history = prices[prices["Ticker"] == ticker].sort_values("Date").copy()
    if price_history.empty:
        raise ValueError(f"No data for {ticker}")

    rf_config = {"backtest": {"risk_free_rate_annual": rf}}
    factor_df = build_factor_table(price_history, config=rf_config)
    factor_row = factor_df.iloc[0] if not factor_df.empty else pd.Series(dtype=float)
    summary_metrics = _build_summary_metrics(price_history, factor_row)

    benchmark_metrics: dict = {}
    if benchmark_ticker in prices["Ticker"].values:
        bm = prices[prices["Ticker"] == benchmark_ticker].sort_values("Date")
        ar = _returns_at(_close_series(price_history), "D")
        br = _returns_at(_close_series(bm), "D")
        benchmark_metrics = _benchmark_metrics(ar, br, benchmark_ticker)

    # check if ticker is in universe
    full_universe = load_universe()
    ticker_themes = full_universe[full_universe["ticker"] == ticker][["theme", "theme_purity"]].to_dict("records")
    n = len(price_history)

    fundamental_metrics = _fetch_fundamental_metrics(ticker, price_history)

    return {
        "ticker": ticker,
        "name": ticker,
        "sector": None,
        "theme": None,
        "ticker_themes": ticker_themes,
        "summary_metrics": summary_metrics,
        "fundamental_metrics": fundamental_metrics,
        "technical": compute_technical_indicators(price_history),
        "theme_rank": None,
        "category_rank": None,
        "ranking_row": pd.Series(dtype=float),
        "ranking_df": pd.DataFrame(),
        "top_correlated": pd.DataFrame(),
        "price_history": price_history,
        "benchmark_metrics": benchmark_metrics,
        "cost_metrics": [],
        "risk_free_rate": rf,
        "data_quality": {
            "available_history_days": n,
            "data_quality_flag": "OK" if n >= 252 else "LIMITED_HISTORY" if n >= 120 else "VERY_SHORT_HISTORY",
        },
    }


def _fetch_fundamental_metrics(ticker: str, price_history: pd.DataFrame) -> dict:
    """Fetch fundamentals and compute valuation metrics.

    JP tickers (.T): IRBank scraper
    US tickers: yfinance
    """
    if price_history.empty:
        return {}
    current_price = float(price_history.sort_values("Date")["Close"].iloc[-1])

    if ticker.endswith(".T"):
        fund_df = fetch_fundamentals(ticker, use_cache=True)
        if fund_df.empty:
            return {}
        return compute_fundamental_metrics(fund_df, current_price, currency="JPY")

    fund_df = fetch_us_fundamentals(ticker, use_cache=True)
    if fund_df.empty:
        return {}
    return compute_fundamental_metrics(fund_df, current_price, currency="USD")


def _build_summary_metrics(price_history: pd.DataFrame, factor_row: pd.Series) -> pd.DataFrame:
    fields = [
        "return_1m", "return_3m", "return_6m", "return_12m",
        "annualized_volatility", "max_drawdown_12m", "max_drawdown_full",
        "sharpe_6m", "sharpe_12m", "sortino_12m", "calmar_12m",
        "distance_from_ma_50", "distance_from_ma_200",
        "distance_from_52w_high", "distance_from_52w_low",
        "avg_traded_value_3m",
        "rvol_20_60", "price_volume_alignment",
    ]
    row = {f: factor_row.get(f, np.nan) if hasattr(factor_row, "get") else np.nan for f in fields}
    return pd.DataFrame([row])
