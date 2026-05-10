import pandas as pd
import yfinance as yf
from src.utils.logger import get_logger

logger = get_logger(__name__)


def download_price_data(
    tickers: list[str],
    start_date: str,
    end_date: str | None = None,
    auto_adjust: bool = False,
) -> pd.DataFrame:
    valid = [t for t in tickers if t and isinstance(t, str)]
    if not valid:
        raise ValueError("No valid tickers provided")

    logger.info(f"Downloading {len(valid)} tickers from {start_date}")
    frames = []
    failed = []

    for ticker in valid:
        try:
            raw = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                auto_adjust=auto_adjust,
                progress=False,
                multi_level_index=False,
            )
            if raw.empty:
                logger.warning(f"  {ticker}: no data")
                failed.append(ticker)
                continue
            raw = raw.reset_index()
            raw["Ticker"] = ticker
            # normalize column names
            if "Adj Close" in raw.columns:
                raw = raw.rename(columns={"Adj Close": "Adj_Close"})
            elif "Adj_Close" not in raw.columns and "Close" in raw.columns:
                raw["Adj_Close"] = raw["Close"]
            frames.append(raw)
            logger.info(f"  {ticker}: {len(raw)} rows")
        except Exception as e:
            logger.error(f"  {ticker}: {e}")
            failed.append(ticker)

    if failed:
        logger.warning(f"Failed ({len(failed)}): {failed}")
    if not frames:
        raise RuntimeError("No price data downloaded for any ticker")

    return pd.concat(frames, ignore_index=True)
