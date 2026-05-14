#!/usr/bin/env python3
"""
Theme-level analysis pipeline.

Usage:
    python run_pipeline.py --theme battery_storage
    python run_pipeline.py --theme semiconductor
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from src.config.loader import load_theme_config, get_theme_universe, get_weights, get_benchmark
from src.data.price_loader import download_price_data
from src.data.storage import save_parquet, save_csv
from src.factors.factor_table import build_factor_table
from src.factors.fundamentals import fetch_all_fundamentals
from src.scoring.scorer import compute_scores_by_region
from src.scoring.ranking import rank_stocks
from src.scoring.ic_weighter import compute_ic_weights
from src.scoring.fundamental_ic import compute_fundamental_ic_weights
from src.analytics.correlation import compute_correlation_matrix
from src.analytics.clustering import compute_clusters
from src.backtest.simple_backtest import run_monthly_momentum_top_n_backtest
from src.reports.theme_report import generate_theme_html_report
from src.utils.logger import get_logger

logger = get_logger("run_pipeline")


def main(theme: str) -> None:
    logger.info(f"=== Pipeline: {theme} ===")

    config = load_theme_config(theme)
    universe_df = get_theme_universe(theme, config)
    weights = get_weights(config)

    start_date = config["analysis"]["start_date"]
    top_n = config["analysis"]["top_n_backtest"]
    tx_bps = config.get("backtest", {}).get("transaction_cost_bps", 30.0)
    lag = config.get("backtest", {}).get("execution_lag_days", 1)
    benchmark_ticker = get_benchmark(config, "US")

    tickers = universe_df["ticker"].tolist()
    all_tickers = list(dict.fromkeys(tickers + [benchmark_ticker]))

    prices = download_price_data(all_tickers, start_date=start_date)
    save_parquet(prices, f"data/processed/prices/{theme}.parquet")

    theme_prices = prices[prices["Ticker"].isin(tickers)].copy()

    # Fetch fundamentals once; reused by factor_table AND fundamental IC
    fund_yaml_weights = config.get("fundamental_weights", {})
    fundamentals_data = fetch_all_fundamentals(tickers, theme=theme) if fund_yaml_weights else {}

    factor_df = build_factor_table(theme_prices, theme=theme, config=config, fundamentals_data=fundamentals_data or None)
    save_parquet(factor_df, f"data/processed/factors/{theme}_factors.parquet")

    ic_weights, ic_summary = compute_ic_weights(theme_prices, weights)
    save_csv(ic_summary, f"data/processed/ic_weights/{theme}_ic_weights.csv")

    # Fundamental IC weights (annual)
    # Requires long price history (10yr) — separate from theme start_date
    if fund_yaml_weights:
        jp_tickers = [t for t in tickers if t.endswith(".T")]
        fund_price_cache = Path(f"data/processed/prices/{theme}_fund_ic_prices.parquet")
        if fund_price_cache.exists():
            extended_prices = pd.read_parquet(fund_price_cache)
            logger.info("Loaded extended prices from cache for fundamental IC")
        else:
            extended_prices = download_price_data(jp_tickers, start_date="2010-01-01")
            save_parquet(extended_prices, str(fund_price_cache))
        fund_ic_weights, fund_ic_summary = compute_fundamental_ic_weights(
            extended_prices, fundamentals_data, fund_yaml_weights
        )
        save_csv(fund_ic_summary, f"data/processed/ic_weights/{theme}_fundamental_ic.csv")
        config = {**config, "fundamental_weights": fund_ic_weights}
    else:
        fund_ic_summary = pd.DataFrame()
        fundamentals_data = {}

    scores = compute_scores_by_region(factor_df, universe_df, ic_weights, config)
    ranking = rank_stocks(scores, universe_df)
    save_csv(ranking, f"data/processed/rankings/{theme}_ranking.csv")

    correlation = compute_correlation_matrix(theme_prices)
    save_csv(correlation, f"data/processed/correlations/{theme}_correlation.csv")

    clusters = compute_clusters(theme_prices)
    save_csv(clusters, f"data/processed/clusters/{theme}_clusters.csv")

    bm = benchmark_ticker if benchmark_ticker in prices["Ticker"].values else None
    backtest = run_monthly_momentum_top_n_backtest(
        theme_prices,
        top_n=top_n,
        transaction_cost_bps=tx_bps,
        execution_lag_days=lag,
        benchmark_ticker=bm,
        score_df=ranking,
    )
    save_csv(backtest, f"data/processed/backtests/{theme}_backtest.csv")

    generate_theme_html_report(
        theme=theme,
        config=config,
        universe_df=universe_df,
        ranking_df=ranking,
        correlation_df=correlation,
        clusters_df=clusters,
        backtest_df=backtest,
        output_path=f"data/reports/themes/{theme}_report.html",
        ic_summary=ic_summary,
        ic_weights=ic_weights,
        fund_ic_summary=fund_ic_summary,
    )

    logger.info(f"=== Done: data/reports/themes/{theme}_report.html ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--theme", required=True, help="Theme name (e.g. battery_storage)")
    args = parser.parse_args()
    main(args.theme)
