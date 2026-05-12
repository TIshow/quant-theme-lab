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
