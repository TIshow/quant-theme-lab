#!/usr/bin/env python3
"""
Cross-theme comparison: "Which theme is strongest right now?"

Usage:
    python run_universe.py
    python run_universe.py --themes battery_storage semiconductor defense ai_infrastructure
    python run_universe.py --benchmark SPY
"""
import argparse
import sys
from pathlib import Path

sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:] if a != "--"]

sys.path.insert(0, str(Path(__file__).parent))

from src.config.loader import load_universe, load_theme_config, list_available_themes
from src.data.price_loader import download_price_data
from src.data.storage import save_csv
from src.analytics.theme_comparison import build_theme_returns, compute_theme_stats, compute_theme_momentum_score
from src.reports.universe_report import generate_universe_html_report
from src.utils.logger import get_logger

logger = get_logger("run_universe")


def main(themes: list[str], benchmark: str = "SPY") -> None:
    logger.info(f"=== Universe comparison: {themes} ===")

    universe_df = load_universe()
    theme_tickers = universe_df[universe_df["theme"].isin(themes)]["ticker"].unique().tolist()
    all_tickers = list(dict.fromkeys(theme_tickers + [benchmark]))

    # Use the earliest start_date among selected themes
    start_date = "2023-01-01"
    for t in themes:
        try:
            cfg = load_theme_config(t)
            sd = cfg["analysis"].get("start_date", "2023-01-01")
            if sd < start_date:
                start_date = sd
        except Exception:
            pass

    prices = download_price_data(all_tickers, start_date=start_date)

    bm_prices = prices[prices["Ticker"] == benchmark].set_index("Date")["Close"].pct_change().dropna() \
        if benchmark in prices["Ticker"].values else None

    theme_returns = build_theme_returns(prices, universe_df, themes)
    save_csv(theme_returns.reset_index(), "data/processed/theme_comparison/theme_returns.csv")

    theme_stats = compute_theme_stats(theme_returns, benchmark_returns=bm_prices)
    save_csv(theme_stats, "data/processed/theme_comparison/theme_stats.csv")

    momentum_score = compute_theme_momentum_score(theme_returns)

    generate_universe_html_report(
        theme_returns=theme_returns,
        theme_stats=theme_stats,
        momentum_score=momentum_score,
        output_path="data/reports/universe/theme_comparison_report.html",
    )

    logger.info("=== Done: data/reports/universe/theme_comparison_report.html ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--themes", nargs="+", default=None,
                        help="Themes to compare (default: all available)")
    parser.add_argument("--benchmark", default="SPY")
    args = parser.parse_args()

    themes = args.themes or list_available_themes()
    main(themes, args.benchmark)
