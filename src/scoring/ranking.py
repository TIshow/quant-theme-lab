import pandas as pd

_ORDERED_COLS = [
    "rank", "region_rank", "Ticker", "name", "country", "sector", "theme_purity",
    "final_score", "momentum_score", "risk_adjusted_return_score",
    "liquidity_score", "volume_score", "volatility_score", "drawdown_score",
    "fundamentals_score", "theme_purity_score",
    "fundamental_roe", "fundamental_roa", "fundamental_operating_margin",
    "fundamental_revenue_growth", "fundamental_free_cf_margin",
    "available_history_days", "data_quality_flag",
]


def rank_stocks(scores: pd.DataFrame, universe_df: pd.DataFrame | None = None) -> pd.DataFrame:
    df = scores.copy()
    if universe_df is not None:
        meta_cols = [c for c in ["ticker", "name", "country", "sector", "theme_purity"] if c in universe_df.columns]
        meta = universe_df[meta_cols].rename(columns={"ticker": "Ticker"})
        df = df.merge(meta, on="Ticker", how="left", suffixes=("", "_meta"))
        # prefer meta theme_purity if both exist
        if "theme_purity_meta" in df.columns:
            df["theme_purity"] = df["theme_purity_meta"].combine_first(df.get("theme_purity", pd.Series(dtype=float)))
            df = df.drop(columns=["theme_purity_meta"])

    df = df.sort_values("final_score", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))

    # Region rank: rank within JP / US separately (requires `region` column from compute_scores_by_region)
    if "region" in df.columns:
        df["region_rank"] = (
            df.groupby("region")["final_score"]
            .rank(ascending=False, method="min")
            .astype(int)
        )

    existing = [c for c in _ORDERED_COLS if c in df.columns]
    rest = [c for c in df.columns if c not in existing]
    return df[existing + rest]
