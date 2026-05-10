import pytest
import numpy as np
import pandas as pd
from src.analytics.factor_validation import compute_ic, compute_icir


def test_ic_perfect_positive():
    factor = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=list("ABCDE"))
    fwd = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05], index=list("ABCDE"))
    ic = compute_ic(factor, fwd)
    assert ic == pytest.approx(1.0, abs=0.01)


def test_ic_perfect_negative():
    factor = pd.Series([5.0, 4.0, 3.0, 2.0, 1.0], index=list("ABCDE"))
    fwd = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05], index=list("ABCDE"))
    ic = compute_ic(factor, fwd)
    assert ic == pytest.approx(-1.0, abs=0.01)


def test_ic_nan_on_too_few():
    factor = pd.Series([1.0, 2.0], index=list("AB"))
    fwd = pd.Series([0.01, 0.02], index=list("AB"))
    ic = compute_ic(factor, fwd)
    assert np.isnan(ic)


def test_icir_positive():
    ic_series = pd.Series([0.3, 0.4, 0.35, 0.28, 0.42])
    icir = compute_icir(ic_series)
    assert icir > 0


def test_icir_nan_on_few():
    ic_series = pd.Series([0.3, 0.4])
    icir = compute_icir(ic_series)
    assert np.isnan(icir)
