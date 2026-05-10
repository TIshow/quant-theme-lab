"""
IRBank scraper for Japanese stock fundamental data.

Source: https://irbank.net/{4digit_code}/results
Covers: PL / BS / CF / Dividend tables (決算短信ベース、四半期対応)

Usage:
    from src.data.irbank_scraper import fetch_fundamentals
    df = fetch_fundamentals("6996.T")   # 最新期が先頭
"""
import re
import time
import json
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.utils.logger import get_logger

logger = get_logger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
_CACHE_DIR = Path("data/processed/fundamentals")
_REQUEST_INTERVAL = 1.5  # seconds between requests


# ---------- number parsing ----------

def _parse_value(s: str) -> float:
    """'1196億' → 1.196e11, '77.24' → 77.24, '-' / '赤字' → NaN"""
    s = str(s).strip()
    if s in ("-", "–", "—", "", "赤字", "N/A", "nan"):
        return np.nan
    s = s.replace(",", "")
    multiplier = 1.0
    if "億" in s:
        multiplier = 1e8
        s = s.replace("億", "")
    elif "百万" in s:
        multiplier = 1e6
        s = s.replace("百万", "")
    elif "千万" in s:
        multiplier = 1e7
        s = s.replace("千万", "")
    try:
        return float(s) * multiplier
    except ValueError:
        return np.nan


# ---------- table parsing ----------

_TABLE_COLUMNS = {
    0: {  # PL
        "売上":   "revenue",
        "営利":   "operating_profit",
        "経常":   "ordinary_profit",
        "当期利益": "net_income",
        "EPS":    "eps",
        "ROE":    "roe",
        "ROA":    "roa",
        "営利率":  "operating_margin",
    },
    1: {  # BS
        "総資産":     "total_assets",
        "純資産":     "net_assets",
        "自己資本比率": "equity_ratio",
        "利益剰余金":  "retained_earnings",
        "有利子負債":  "interest_bearing_debt",
        "BPS":       "bps",
    },
    2: {  # CF
        "営業CF":      "operating_cf",
        "投資CF":      "investing_cf",
        "フリーCF":    "free_cf",
        "設備投資":     "capex",
        "現金等":      "cash",
        "営業CFマージン": "operating_cf_margin",
    },
}

# Columns that are already in percent / ratio (do NOT multiply by 億)
_RATIO_COLS = {
    "ROE", "ROA", "営利率", "原価率", "販管費率",
    "自己資本比率", "有利子負債比率", "営業CFマージン",
    "EPS", "BPS",
}


def _parse_table(soup_table, col_map: dict) -> pd.DataFrame:
    rows = soup_table.find_all("tr")
    if not rows:
        return pd.DataFrame()

    headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]

    records = []
    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
        if not cells or not re.match(r"\d{4}/\d{2}", cells[0]):
            continue
        rec = {"fiscal_year": cells[0]}
        for i, h in enumerate(headers[1:], 1):
            if h in col_map and i < len(cells):
                raw = cells[i]
                val = _parse_value(raw) if h not in _RATIO_COLS else _parse_ratio(raw)
                rec[col_map[h]] = val
        records.append(rec)

    return pd.DataFrame(records)


def _parse_ratio(s: str) -> float:
    """Percent / ratio columns: '77.24' → 77.24, '-' → NaN"""
    s = str(s).strip()
    if s in ("-", "–", "—", "", "赤字", "N/A", "nan"):
        return np.nan
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return np.nan


# ---------- derived metrics ----------

def _add_derived(df: pd.DataFrame) -> pd.DataFrame:
    if "revenue" in df.columns:
        df = df.sort_values("fiscal_year")
        df["revenue_growth"] = df["revenue"].pct_change() * 100
        df = df.sort_values("fiscal_year", ascending=False)

    if "operating_cf" in df.columns and "capex" in df.columns:
        df["fcf_check"] = df["operating_cf"] + df["capex"]

    return df


# ---------- cache ----------

def _cache_path(ticker: str) -> Path:
    code = ticker.replace(".T", "").replace(".T", "")
    return _CACHE_DIR / f"{code}_fundamentals.json"


def _load_cache(ticker: str) -> pd.DataFrame | None:
    p = _cache_path(ticker)
    if p.exists():
        try:
            return pd.read_json(p)
        except Exception:
            pass
    return None


def _save_cache(ticker: str, df: pd.DataFrame) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(ticker).write_text(df.to_json(), encoding="utf-8")


# ---------- public API ----------

def fetch_fundamentals(ticker: str, use_cache: bool = True) -> pd.DataFrame:
    """
    Fetch annual fundamental data from IRBank for a JP ticker.

    Args:
        ticker:    e.g. "6996.T"
        use_cache: use local JSON cache if available

    Returns:
        DataFrame indexed by fiscal_year (降順), columns: revenue, operating_profit,
        net_income, roe, roa, operating_margin, total_assets, equity_ratio,
        interest_bearing_debt, operating_cf, free_cf, capex, cash, revenue_growth, ...
    """
    if not ticker.endswith(".T"):
        logger.warning(f"fetch_fundamentals: {ticker} is not a JP ticker, skipping")
        return pd.DataFrame()

    if use_cache:
        cached = _load_cache(ticker)
        if cached is not None:
            logger.info(f"Fundamentals cache hit: {ticker}")
            return cached

    code = ticker.replace(".T", "")
    url = f"https://irbank.net/{code}/results"
    logger.info(f"Fetching fundamentals: {url}")

    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"IRBank fetch failed for {ticker}: {e}")
        return pd.DataFrame()

    time.sleep(_REQUEST_INTERVAL)

    soup = BeautifulSoup(r.text, "html5lib")
    tables = soup.find_all("table")

    if len(tables) < 3:
        logger.warning(f"Unexpected table count ({len(tables)}) for {ticker}")
        return pd.DataFrame()

    frames = []
    for idx, col_map in _TABLE_COLUMNS.items():
        if idx < len(tables):
            df_t = _parse_table(tables[idx], col_map)
            if not df_t.empty:
                frames.append(df_t)

    if not frames:
        return pd.DataFrame()

    result = frames[0]
    for f in frames[1:]:
        result = result.merge(f, on="fiscal_year", how="outer")

    result = result.sort_values("fiscal_year", ascending=False).reset_index(drop=True)
    result = _add_derived(result)

    _save_cache(ticker, result)
    logger.info(f"Fundamentals fetched: {ticker} ({len(result)} periods)")
    return result


def fetch_fundamentals_batch(tickers: list[str], use_cache: bool = True) -> dict[str, pd.DataFrame]:
    """Fetch fundamentals for multiple JP tickers with rate limiting."""
    results = {}
    jp_tickers = [t for t in tickers if t.endswith(".T")]
    for t in jp_tickers:
        results[t] = fetch_fundamentals(t, use_cache=use_cache)
    return results
