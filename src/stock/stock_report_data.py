import pandas as pd


def build_stock_report_data(analysis_result: dict) -> dict:
    data = analysis_result.copy()
    ph = data.get("price_history", pd.DataFrame())
    if not ph.empty and "Close" in ph.columns:
        ph = ph.sort_values("Date")
        data["chart_dates"] = ph["Date"].astype(str).tolist()
        data["chart_prices"] = ph["Close"].tolist()
        data["chart_volumes"] = ph["Volume"].tolist() if "Volume" in ph.columns else []
        traded = ph["Close"] * ph["Volume"] if "Volume" in ph.columns else pd.Series(dtype=float)
        data["chart_traded_values"] = traded.tolist()

    sm = data.get("summary_metrics", pd.DataFrame())
    data["metrics_dict"] = sm.iloc[0].to_dict() if not sm.empty else {}

    # fundamental_metrics is passed through as-is (already a plain dict)
    data.setdefault("fundamental_metrics", {})
    return data
