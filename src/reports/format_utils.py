"""Shared number-formatting helpers for HTML report generation."""
import math


def fmt(v, digits: int = 1, suffix: str = "") -> str:
    """Format a numeric value; return '—' for None/NaN."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:.{digits}f}{suffix}"


def pct(v, digits: int = 2) -> str:
    """Format as percentage (v is already a fraction, e.g. 0.05 → '5.00%')."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "N/A"
    return f"{v * 100:.{digits}f}%"


def signed_cls(v) -> str:
    """Return CSS class string 'pos' / 'neg' / '' for coloring."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return "pos" if v > 0 else "neg"


def fmt_x(v, digits: int = 1) -> str:
    """Format a multiple (e.g. PER): 15.2 → '15.2x'. Returns '—' for invalid."""
    if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
        return "—"
    return f"{v:.{digits}f}x"


def fmt_jpy(v) -> str:
    """Format a JPY amount: 1.5e10 → '150.0億'. Returns '—' for invalid."""
    if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
        return "—"
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e12:
        return f"{sign}¥{a / 1e12:.1f}兆"
    if a >= 1e8:
        return f"{sign}¥{a / 1e8:.1f}億"
    if a >= 1e6:
        return f"{sign}¥{a / 1e6:.0f}百万"
    return f"{sign}¥{a:.0f}"


def pct_already(v, digits: int = 1) -> str:
    """Format a value already expressed in percent: 15.3 → '15.3%'. Returns '—' for invalid."""
    if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
        return "—"
    return f"{v:.{digits}f}%"


def pct_signed(v, digits: int = 1) -> str:
    """Format a signed percent growth: 12.3 → '+12.3%', -5.4 → '-5.4%'. Returns '—' for invalid."""
    if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
        return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.{digits}f}%"


def fmt_usd(v) -> str:
    """Format a USD amount: 1.5e9 → '$1.5B'. Returns '—' for invalid."""
    if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
        return "—"
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e12:
        return f"{sign}${a / 1e12:.1f}T"
    if a >= 1e9:
        return f"{sign}${a / 1e9:.1f}B"
    if a >= 1e6:
        return f"{sign}${a / 1e6:.0f}M"
    return f"{sign}${a:.0f}"
