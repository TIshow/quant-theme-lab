import pandas as pd


def check_required_columns(df: pd.DataFrame, required: list[str], context: str = "") -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{context}: missing columns {missing}")
