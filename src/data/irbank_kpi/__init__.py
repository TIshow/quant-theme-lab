"""
Theme-specific KPI plugin system.

If src/data/irbank_kpi/<theme_name>.py exists and defines compute_kpis(df),
it will be called to add sector-specific derived metrics to the fundamentals DataFrame.
"""
import importlib
import pandas as pd
from src.utils.logger import get_logger

logger = get_logger(__name__)


def compute_theme_kpis(theme: str, fund_df: pd.DataFrame) -> pd.DataFrame:
    """
    Load and apply theme-specific KPI module if available.
    Falls back to returning fund_df unchanged if no module exists.
    """
    try:
        module = importlib.import_module(f"src.data.irbank_kpi.{theme}")
        if hasattr(module, "compute_kpis"):
            result = module.compute_kpis(fund_df)
            logger.info(f"KPI plugin applied: {theme}")
            return result
    except ModuleNotFoundError:
        pass
    return fund_df
