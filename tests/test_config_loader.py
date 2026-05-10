import pytest
import pandas as pd
from src.config.loader import load_theme_config, get_theme_universe, get_weights, load_universe


def test_load_battery_storage():
    config = load_theme_config("battery_storage")
    assert config["theme"] == "battery_storage"


def test_universe_is_dataframe():
    config = load_theme_config("battery_storage")
    df = get_theme_universe("battery_storage", config)
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


def test_universe_has_ticker():
    config = load_theme_config("battery_storage")
    df = get_theme_universe("battery_storage", config)
    assert "ticker" in df.columns


def test_universe_has_theme_purity():
    config = load_theme_config("battery_storage")
    df = get_theme_universe("battery_storage", config)
    assert "theme_purity" in df.columns
    assert (df["theme_purity"] >= 1).all()


def test_weights_returned():
    config = load_theme_config("battery_storage")
    w = get_weights(config)
    assert isinstance(w, dict)
    assert "momentum" in w
    assert abs(sum(w.values()) - 1.0) < 0.01


def test_global_universe_multi_theme():
    df = load_universe()
    # NVDA should appear in both semiconductor and ai_infrastructure
    nvda = df[df["ticker"] == "NVDA"]
    assert len(nvda) == 2
    themes = set(nvda["theme"].tolist())
    assert "semiconductor" in themes
    assert "ai_infrastructure" in themes


def test_min_purity_filter():
    config = load_theme_config("battery_storage")
    config["analysis"]["min_theme_purity"] = 5
    df = get_theme_universe("battery_storage", config)
    assert (df["theme_purity"] >= 5).all()
