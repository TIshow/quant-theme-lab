from dataclasses import dataclass


@dataclass
class AnalysisConfig:
    start_date: str
    min_theme_purity: int
    top_n_backtest: int


@dataclass
class BacktestConfig:
    transaction_cost_bps: float
    execution_lag_days: int
