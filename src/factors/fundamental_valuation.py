"""
Fundamental valuation metrics derived from IRBank data + current price.

Computes PER, PBR, PSR, P/FCF, EV/EBIT, PEG, growth rates,
profitability ratios, and financial quality metrics.

All monetary inputs from IRBank are in JPY.
Ratio/margin values from IRBank are already in percent (e.g., ROE=15.3).
"""
import numpy as np
import pandas as pd


def compute_fundamental_metrics(
    fund_df: pd.DataFrame,
    current_price: float,
    currency: str = "JPY",
) -> dict:
    """
    Compute full fundamental analysis from IRBank data + latest price.

    Args:
        fund_df:       DataFrame from fetch_fundamentals() (most-recent-first).
        current_price: Latest close price (JPY).

    Returns:
        dict with keys: fiscal_year, market_cap, ev, shares_outstanding,
        valuation ratios, growth rates, profitability %, quality metrics,
        and 'history' sub-dict for chart rendering.
        Returns {} if inputs are unusable.
    """
    if fund_df.empty or not _v(current_price) or current_price <= 0:
        return {}

    actual = _actual_rows(fund_df)
    if actual.empty:
        return {}

    latest = actual.iloc[0]

    # ── derived base values ────────────────────────────────────────────
    shares = _shares(latest)
    market_cap = current_price * shares if _v(shares) else np.nan

    eps          = _g(latest, "eps")
    bps          = _g(latest, "bps")
    dps_irb      = _g(latest, "dps")
    revenue      = _g(latest, "revenue")
    op_profit    = _g(latest, "operating_profit")
    ord_profit   = _g(latest, "ordinary_profit")
    net_income   = _g(latest, "net_income")          # may be missing from cache
    free_cf      = _g(latest, "free_cf")
    op_cf        = _g(latest, "operating_cf")
    interest_dbt = _g(latest, "interest_bearing_debt")
    cash_val     = _g(latest, "cash")
    shareholders = _g(latest, "shareholders_equity")

    # Estimate net_income when not scraped directly
    if not _v(net_income) and _v(eps) and _v(shares):
        net_income = eps * shares

    # ── Enterprise Value ──────────────────────────────────────────────
    net_debt = _nz(interest_dbt) - _nz(cash_val)
    ev = market_cap + net_debt if _v(market_cap) else np.nan

    # ── Valuation ratios ─────────────────────────────────────────────
    per    = current_price / eps       if (_v(eps)       and eps > 0)       else np.nan
    pbr    = current_price / bps       if (_v(bps)       and bps > 0)       else np.nan
    psr    = market_cap / revenue      if (_v(market_cap) and _v(revenue)   and revenue > 0)   else np.nan
    p_fcf  = market_cap / free_cf      if (_v(market_cap) and _v(free_cf)   and free_cf > 0)   else np.nan
    ev_ebit = ev / op_profit           if (_v(ev)         and _v(op_profit) and op_profit > 0) else np.nan
    ev_rev  = ev / revenue             if (_v(ev)         and _v(revenue)   and revenue > 0)   else np.nan

    # ── Dividend ─────────────────────────────────────────────────────
    div_yield_calc = dps_irb / current_price * 100 if (_v(dps_irb) and dps_irb > 0) else np.nan
    div_yield_irb  = _g(latest, "dividend_yield")
    div_yield = div_yield_irb if _v(div_yield_irb) else div_yield_calc
    payout_ratio = _g(latest, "payout_ratio")

    # ── PEG ──────────────────────────────────────────────────────────
    eps_growth_1y = _yoy_growth(actual, "eps", 1)
    peg = per / eps_growth_1y if (_v(per) and _v(eps_growth_1y) and eps_growth_1y > 0) else np.nan

    # ── Growth rates (%) ─────────────────────────────────────────────
    rev_growth_1y   = _yoy_growth(actual, "revenue",          1)
    rev_cagr_3y     = _cagr(actual,       "revenue",          3)
    rev_cagr_5y     = _cagr(actual,       "revenue",          5)
    op_growth_1y    = _yoy_growth(actual, "operating_profit", 1)
    eps_cagr_3y     = _cagr(actual,       "eps",              3)
    ni_growth_1y    = _yoy_growth(actual, "net_income",       1)

    # ── Profitability (values already in %) ──────────────────────────
    roe         = _g(latest, "roe")
    roa         = _g(latest, "roa")
    op_margin   = _g(latest, "operating_margin")
    op_cf_marg  = _g(latest, "operating_cf_margin")
    fcf_margin  = _g(latest, "free_cf_margin")

    net_margin = (
        net_income / revenue * 100
        if (_v(net_income) and _v(revenue) and revenue > 0)
        else np.nan
    )

    # ── Quality / Financial health ────────────────────────────────────
    equity_ratio  = _g(latest, "equity_ratio")
    de_ratio      = (
        interest_dbt / shareholders
        if (_v(interest_dbt) and _v(shareholders) and shareholders > 0)
        else np.nan
    )
    fcf_conversion = (
        free_cf / net_income
        if (_v(free_cf) and _v(net_income) and net_income > 0)
        else np.nan
    )
    capex = _g(latest, "capex")
    capex_ratio = (
        abs(capex) / revenue * 100
        if (_v(capex) and _v(revenue) and revenue > 0)
        else np.nan
    )

    # ── Period count ─────────────────────────────────────────────────
    n_periods = len(actual)

    return {
        # Context
        "currency":          currency,
        "fiscal_year":       str(latest.get("fiscal_year", "")),
        "n_periods":         n_periods,
        "market_cap":        market_cap,
        "shares_outstanding": shares,
        "ev":                ev,
        "net_debt":          net_debt,
        # Valuation
        "per":     per,
        "pbr":     pbr,
        "psr":     psr,
        "p_fcf":   p_fcf,
        "ev_ebit": ev_ebit,
        "ev_rev":  ev_rev,
        "peg":     peg,
        # Dividend
        "dps":           dps_irb,
        "dividend_yield": div_yield,
        "payout_ratio":  payout_ratio,
        # Growth (%)
        "revenue_growth_1y":  rev_growth_1y,
        "revenue_cagr_3y":    rev_cagr_3y,
        "revenue_cagr_5y":    rev_cagr_5y,
        "op_profit_growth_1y": op_growth_1y,
        "eps_growth_1y":      eps_growth_1y,
        "eps_cagr_3y":        eps_cagr_3y,
        "net_income_growth_1y": ni_growth_1y,
        # Profitability (%)
        "roe":              roe,
        "roa":              roa,
        "operating_margin": op_margin,
        "net_margin":       net_margin,
        "operating_cf_margin": op_cf_marg,
        "fcf_margin":       fcf_margin,
        # Quality
        "equity_ratio":    equity_ratio,
        "de_ratio":        de_ratio,
        "fcf_conversion":  fcf_conversion,
        "capex_ratio":     capex_ratio,
        # Raw absolute values (JPY) for display
        "revenue":              revenue,
        "operating_profit":     op_profit,
        "ordinary_profit":      ord_profit,
        "net_income":           net_income,
        "free_cf":              free_cf,
        "operating_cf":         op_cf,
        "interest_bearing_debt": interest_dbt,
        "cash":                 cash_val,
        "eps":                  eps,
        "bps":                  bps,
        # History for Plotly charts
        "history": _build_history(actual),
    }


# ── internal helpers ─────────────────────────────────────────────────────────

def _actual_rows(df: pd.DataFrame) -> pd.DataFrame:
    return df[~df["fiscal_year"].str.contains("予", na=False)].reset_index(drop=True)


def _g(row: pd.Series, col: str) -> float:
    """Get a float value from a row; return np.nan if missing or non-finite."""
    v = row.get(col, np.nan)
    if v is None:
        return np.nan
    try:
        f = float(v)
        return f if np.isfinite(f) else np.nan
    except (TypeError, ValueError):
        return np.nan


def _v(x) -> bool:
    """True iff x is a finite real number."""
    return isinstance(x, (int, float)) and np.isfinite(x)


def _nz(x) -> float:
    """Return float(x) if finite, else 0.0 (for net-debt arithmetic)."""
    return float(x) if _v(x) else 0.0


def _shares(row: pd.Series) -> float:
    """Estimate shares outstanding: shareholders_equity / BPS."""
    bps = _g(row, "bps")
    eq  = _g(row, "shareholders_equity")
    if _v(bps) and bps > 0 and _v(eq) and eq > 0:
        return eq / bps
    return np.nan


def _yoy_growth(actual: pd.DataFrame, col: str, n: int = 1) -> float:
    """YoY growth rate (%) between most-recent actual and n periods ago."""
    if col not in actual.columns or len(actual) < n + 1:
        return np.nan
    v0 = _g(actual.iloc[0], col)
    v1 = _g(actual.iloc[n], col)
    if not _v(v0) or not _v(v1) or v1 == 0:
        return np.nan
    return (v0 / v1 - 1) * 100


def _cagr(actual: pd.DataFrame, col: str, years: int) -> float:
    """CAGR over `years` periods (%)."""
    if col not in actual.columns or len(actual) < years + 1:
        return np.nan
    v_start = _g(actual.iloc[years], col)
    v_end   = _g(actual.iloc[0],     col)
    if not _v(v_start) or not _v(v_end) or v_start <= 0 or v_end <= 0:
        return np.nan
    return ((v_end / v_start) ** (1 / years) - 1) * 100


def _build_history(actual: pd.DataFrame) -> dict:
    """Build chronological time-series for chart rendering (oldest → newest)."""
    chron = actual.iloc[::-1].reset_index(drop=True)

    def col(name: str) -> list:
        if name not in chron.columns:
            return []
        return [
            float(v) if (_v(v) or (isinstance(v, (int, float)) and np.isfinite(float(v)))) else None
            for v in chron[name]
        ]

    return {
        "fiscal_years":        chron["fiscal_year"].tolist(),
        "revenue":             col("revenue"),
        "operating_profit":    col("operating_profit"),
        "ordinary_profit":     col("ordinary_profit"),
        "net_income":          col("net_income"),
        "operating_margin":    col("operating_margin"),
        "roe":                 col("roe"),
        "roa":                 col("roa"),
        "equity_ratio":        col("equity_ratio"),
        "free_cf":             col("free_cf"),
        "operating_cf":        col("operating_cf"),
        "eps":                 col("eps"),
        "bps":                 col("bps"),
        "interest_bearing_debt": col("interest_bearing_debt"),
        "cash":                col("cash"),
        "dps":                 col("dps") if "dps" in chron.columns else [],
    }
