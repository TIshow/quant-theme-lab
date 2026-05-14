import numpy as np
import pandas as pd
from src.config.loader import load_theme_config, get_theme_universe, get_weights, get_benchmark, load_universe
from src.data.price_loader import download_price_data
from src.data.irbank_scraper import fetch_fundamentals
from src.data.yfinance_fundamentals import fetch_us_fundamentals
from src.factors.factor_table import build_factor_table
from src.factors.fundamental_valuation import compute_fundamental_metrics
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
        asset_ret = price_history.set_index("Date")["Close"].pct_change().dropna()
        bm_ret = bm_prices.set_index("Date")["Close"].pct_change().dropna()
        benchmark_metrics = {
            "beta": compute_beta(asset_ret, bm_ret),
            "alpha": compute_alpha(asset_ret, bm_ret),
            "benchmark_ticker": benchmark_ticker,
        }

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

    return {
        "ticker": ticker,
        "name": name,
        "sector": sector,
        "theme": theme,
        "ticker_themes": ticker_themes,
        "summary_metrics": summary_metrics,
        "fundamental_metrics": fundamental_metrics,
        "theme_rank": theme_rank,
        "category_rank": category_rank,
        "ranking_row": ranking_row,
        "ranking_df": ranking,
        "top_correlated": top_correlated,
        "price_history": price_history,
        "benchmark_metrics": benchmark_metrics,
        "data_quality": data_quality,
    }


def _analyze_standalone(ticker: str, start_date: str) -> dict:
    benchmark_ticker = "SPY"
    prices = download_price_data([ticker, benchmark_ticker], start_date=start_date)
    price_history = prices[prices["Ticker"] == ticker].sort_values("Date").copy()
    if price_history.empty:
        raise ValueError(f"No data for {ticker}")

    factor_df = build_factor_table(price_history)
    factor_row = factor_df.iloc[0] if not factor_df.empty else pd.Series(dtype=float)
    summary_metrics = _build_summary_metrics(price_history, factor_row)

    benchmark_metrics: dict = {}
    if benchmark_ticker in prices["Ticker"].values:
        bm = prices[prices["Ticker"] == benchmark_ticker].sort_values("Date")
        ar = price_history.set_index("Date")["Close"].pct_change().dropna()
        br = bm.set_index("Date")["Close"].pct_change().dropna()
        benchmark_metrics = {
            "beta": compute_beta(ar, br),
            "alpha": compute_alpha(ar, br),
            "benchmark_ticker": benchmark_ticker,
        }

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
        "theme_rank": None,
        "category_rank": None,
        "ranking_row": pd.Series(dtype=float),
        "ranking_df": pd.DataFrame(),
        "top_correlated": pd.DataFrame(),
        "price_history": price_history,
        "benchmark_metrics": benchmark_metrics,
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
    ]
    row = {f: factor_row.get(f, np.nan) if hasattr(factor_row, "get") else np.nan for f in fields}
    return pd.DataFrame([row])
