"""
yfinance fundamental data fetcher for US (non-JP) stocks.

Returns a DataFrame with the same column schema as irbank_scraper.py,
allowing reuse of compute_fundamental_metrics() in fundamental_valuation.py.

Monetary values are in USD.
fiscal_year format: "YYYY/MM"
Cache TTL: 24 hours.
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

from src.utils.logger import get_logger

logger = get_logger(__name__)

_CACHE_DIR = Path("data/processed/fundamentals")
_CACHE_TTL_HOURS = 24


def _cache_path(ticker: str) -> Path:
    code = ticker.replace(".", "_")
    return _CACHE_DIR / f"{code}_us_fundamentals.json"


def _cache_valid(p: Path) -> bool:
    if not p.exists():
        return False
    return datetime.now() - datetime.fromtimestamp(p.stat().st_mtime) < timedelta(hours=_CACHE_TTL_HOURS)


def _load_cache(ticker: str) -> pd.DataFrame | None:
    p = _cache_path(ticker)
    if _cache_valid(p):
        try:
            return pd.read_json(p)
        except Exception as e:
            logger.warning(f"US fundamentals cache corrupt for {ticker}: {e}")
    return None


def _save_cache(ticker: str, df: pd.DataFrame) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(ticker).write_text(df.to_json(), encoding="utf-8")


def _sf(val) -> float:
    try:
        f = float(val)
        return f if np.isfinite(f) else np.nan
    except (TypeError, ValueError):
        return np.nan


def _gi(df: pd.DataFrame, date, *keys) -> float:
    """Get item from yfinance DataFrame (rows=metrics, cols=dates)."""
    if df is None or df.empty or date not in df.columns:
        return np.nan
    for k in keys:
        if k in df.index:
            return _sf(df.loc[k, date])
    return np.nan


def fetch_us_fundamentals(ticker: str, use_cache: bool = True) -> pd.DataFrame:
    """
    Fetch annual fundamental data from yfinance for a non-JP ticker.

    Returns DataFrame with same column names as irbank_scraper output.
    Monetary values are in USD (raw, not scaled).
    """
    if ticker.endswith(".T"):
        return pd.DataFrame()

    if use_cache:
        cached = _load_cache(ticker)
        if cached is not None:
            logger.info(f"US fundamentals cache hit: {ticker}")
            return cached

    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed — run: uv add yfinance")
        return pd.DataFrame()

    logger.info(f"Fetching US fundamentals via yfinance: {ticker}")
    t = yf.Ticker(ticker)

    try:
        fins = t.financials       # rows=metrics, cols=annual dates
        bs   = t.balance_sheet
        cf   = t.cashflow
        info = t.info or {}
    except Exception as e:
        logger.error(f"yfinance fetch failed for {ticker}: {e}")
        return pd.DataFrame()

    if fins is None or fins.empty:
        logger.warning(f"No financial data from yfinance: {ticker}")
        return pd.DataFrame()

    shares_info = _sf(info.get("sharesOutstanding", np.nan))
    dates = fins.columns.tolist()

    records = []
    for date in dates:
        fy = date.strftime("%Y/%m") if hasattr(date, "strftime") else str(date)[:7].replace("-", "/")
        rec: dict = {"fiscal_year": fy}

        # ── Income statement ───────────────────────────────────────────
        rec["revenue"]          = _gi(fins, date, "Total Revenue", "Operating Revenue")
        rec["operating_profit"] = _gi(fins, date, "Operating Income", "EBIT")
        rec["net_income"]       = _gi(fins, date, "Net Income", "Net Income Common Stockholders")
        rec["eps"]              = _gi(fins, date, "Basic EPS", "Diluted EPS")

        # ── Balance sheet ──────────────────────────────────────────────
        equity   = _gi(bs, date, "Stockholders Equity", "Common Stock Equity")
        ta       = _gi(bs, date, "Total Assets")
        debt     = _gi(bs, date, "Total Debt", "Long Term Debt And Capital Lease Obligation")
        cash     = _gi(bs, date, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")

        rec["shareholders_equity"]  = equity
        rec["total_assets"]         = ta
        rec["interest_bearing_debt"] = debt
        rec["cash"]                 = cash

        # BPS: equity / shares so that _shares() in fundamental_valuation.py recovers sharesOutstanding
        shares_used = shares_info if np.isfinite(shares_info) and shares_info > 0 else np.nan
        rec["bps"] = equity / shares_used if (np.isfinite(equity) and np.isfinite(shares_used)) else np.nan

        # equity ratio from balance sheet
        rec["equity_ratio"] = equity / ta * 100 if (np.isfinite(equity) and np.isfinite(ta) and ta > 0) else np.nan

        # ── Cash flow ──────────────────────────────────────────────────
        op_cf = _gi(cf, date, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
        capex = _gi(cf, date, "Capital Expenditure", "Purchase Of PPE")
        fcf   = _gi(cf, date, "Free Cash Flow")

        rec["operating_cf"] = op_cf
        rec["capex"]        = capex
        # Use reported FCF; fallback: op_cf + capex (capex is negative in yfinance)
        if np.isfinite(fcf):
            rec["free_cf"] = fcf
        elif np.isfinite(op_cf) and np.isfinite(capex):
            rec["free_cf"] = op_cf + capex
        else:
            rec["free_cf"] = np.nan

        # ── Derived ratios (computed per-year from statements) ─────────
        rev          = rec["revenue"]
        op           = rec["operating_profit"]
        ni           = rec["net_income"]
        gross_profit = _gi(fins, date, "Gross Profit")

        rec["gross_profit"]     = gross_profit
        rec["gross_margin"]     = gross_profit / rev * 100 if (np.isfinite(gross_profit) and np.isfinite(rev) and rev > 0) else np.nan
        rec["capex_ratio"]      = abs(capex) / rev * 100   if (np.isfinite(capex) and np.isfinite(rev) and rev > 0) else np.nan
        rec["operating_margin"] = op / rev * 100 if (np.isfinite(op) and np.isfinite(rev) and rev > 0) else np.nan
        rec["roe"] = ni / equity * 100 if (np.isfinite(ni) and np.isfinite(equity) and equity > 0) else np.nan
        rec["roa"] = ni / ta * 100    if (np.isfinite(ni) and np.isfinite(ta)     and ta     > 0) else np.nan

        # ── Dividend (from info for latest year only) ──────────────────
        if date == dates[0]:
            dps = _sf(info.get("lastDividendValue", np.nan))
            rec["dps"] = dps if np.isfinite(dps) and dps > 0 else np.nan

            dy = _sf(info.get("dividendYield", np.nan))
            rec["dividend_yield"] = dy * 100 if np.isfinite(dy) else np.nan

            pr = _sf(info.get("payoutRatio", np.nan))
            rec["payout_ratio"] = pr * 100 if np.isfinite(pr) else np.nan

        records.append(rec)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records).sort_values("fiscal_year", ascending=False).reset_index(drop=True)

    # FCF margin & operating CF margin
    for cf_col, out_col in [("free_cf", "free_cf_margin"), ("operating_cf", "operating_cf_margin")]:
        if cf_col in df.columns and "revenue" in df.columns:
            df[out_col] = df[cf_col] / df["revenue"].replace(0, np.nan) * 100

    # Revenue growth YoY (most-recent first → pct_change with sort ascending)
    if "revenue" in df.columns:
        rev_asc = df["revenue"].iloc[::-1]
        df["revenue_growth"] = (rev_asc.pct_change() * 100).iloc[::-1].values

    _save_cache(ticker, df)
    logger.info(f"US fundamentals fetched: {ticker} ({len(df)} periods)")
    return df
