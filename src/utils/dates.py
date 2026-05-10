from datetime import date
import pandas as pd


def today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


def business_days_between(start: str, end: str) -> int:
    return len(pd.bdate_range(start=start, end=end))
