"""
Tests for shared report formatting helpers.
"""
import math
import pytest

from src.reports.format_utils import fmt, pct, signed_cls


def test_fmt_formats_number():
    assert fmt(3.14159, digits=2) == "3.14"


def test_fmt_with_suffix():
    assert fmt(42.0, digits=1, suffix="%") == "42.0%"


def test_fmt_nan_returns_dash():
    assert fmt(float("nan")) == "—"


def test_fmt_none_returns_dash():
    assert fmt(None) == "—"


def test_fmt_zero():
    assert fmt(0.0) == "0.0"


def test_pct_formats_fraction():
    assert pct(0.05) == "5.00%"


def test_pct_negative():
    assert pct(-0.123) == "-12.30%"


def test_pct_nan_returns_na():
    assert pct(float("nan")) == "N/A"


def test_pct_none_returns_na():
    assert pct(None) == "N/A"


def test_signed_cls_positive():
    assert signed_cls(1.0) == "pos"


def test_signed_cls_negative():
    assert signed_cls(-0.5) == "neg"


def test_signed_cls_zero():
    assert signed_cls(0.0) == "neg"  # 0 is not > 0


def test_signed_cls_nan():
    assert signed_cls(float("nan")) == ""


def test_signed_cls_none():
    assert signed_cls(None) == ""
