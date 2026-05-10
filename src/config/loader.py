from pathlib import Path
import yaml
import pandas as pd


def load_theme_config(theme_name: str, config_dir: str = "config/themes") -> dict:
    path = Path(config_dir) / f"{theme_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Theme config not found: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_universe(universe_path: str = "config/universe.yaml") -> pd.DataFrame:
    """Load the master stock registry."""
    path = Path(universe_path)
    if not path.exists():
        raise FileNotFoundError(f"Universe config not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    rows = []
    for stock in data["stocks"]:
        base = {k: v for k, v in stock.items() if k != "themes"}
        for theme, purity in stock.get("themes", {}).items():
            rows.append({**base, "theme": theme, "theme_purity": purity})

    return pd.DataFrame(rows)


def get_theme_universe(
    theme_name: str,
    theme_config: dict,
    universe_path: str = "config/universe.yaml",
) -> pd.DataFrame:
    """
    Filter the master universe to stocks belonging to the given theme
    with at least min_theme_purity.
    """
    universe = load_universe(universe_path)
    min_purity = theme_config["analysis"].get("min_theme_purity", 1)
    df = universe[(universe["theme"] == theme_name) & (universe["theme_purity"] >= min_purity)].copy()
    df = df.rename(columns={"ticker": "ticker"})
    return df.reset_index(drop=True)


def get_weights(config: dict) -> dict:
    return config["weights"]


def get_benchmark(config: dict, country: str | None = None) -> str:
    benchmarks = config.get("benchmark", {})
    if country == "JP":
        return benchmarks.get("jp", "1306.T")
    return benchmarks.get("us", "SPY")


def list_available_themes(config_dir: str = "config/themes") -> list[str]:
    return [p.stem for p in Path(config_dir).glob("*.yaml")]
