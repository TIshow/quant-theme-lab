from pathlib import Path
import pandas as pd
from src.utils.logger import get_logger

logger = get_logger(__name__)


def ensure_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def save_parquet(df: pd.DataFrame, path: str) -> None:
    ensure_dir(path)
    df.to_parquet(path, index=False)
    logger.info(f"Saved: {path} ({len(df)} rows)")


def load_parquet(path: str) -> pd.DataFrame:
    return pd.read_parquet(path)


def save_csv(df: pd.DataFrame, path: str) -> None:
    ensure_dir(path)
    df.to_csv(path, index=False)
    logger.info(f"Saved: {path} ({len(df)} rows)")


def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)
