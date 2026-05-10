#!/usr/bin/env python3
"""
Individual stock analysis.

Usage:
    python analyze_stock.py --theme battery_storage --ticker 485A.T
    python analyze_stock.py --ticker TSLA
"""
import argparse
import sys
from pathlib import Path

sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:] if a != "--"]

sys.path.insert(0, str(Path(__file__).parent))

from src.stock.stock_analyzer import analyze_stock
from src.reports.stock_report import generate_stock_html_report
from src.utils.logger import get_logger

logger = get_logger("analyze_stock")


def main(ticker: str, theme: str | None = None) -> None:
    logger.info(f"=== Analyzing {ticker} (theme={theme}) ===")

    result = analyze_stock(ticker=ticker, theme=theme)

    if theme:
        output_path = f"data/reports/stocks/{theme}_{ticker}_report.html"
    else:
        output_path = f"data/reports/stocks/{ticker}_report.html"

    generate_stock_html_report(analysis_result=result, output_path=output_path)
    logger.info(f"=== Done: {output_path} ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--theme", default=None)
    args = parser.parse_args()
    main(args.ticker, args.theme)
