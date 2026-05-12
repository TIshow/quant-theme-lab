import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
from pathlib import Path
from jinja2 import Template
from src.stock.stock_report_data import build_stock_report_data
from src.utils.dates import today_str
from src.utils.logger import get_logger
from src.reports.format_utils import fmt, pct, signed_cls

logger = get_logger(__name__)

_CSS = """
body{font-family:'Segoe UI',sans-serif;margin:0;background:#0f0f1a;color:#e0e0e0}
.wrap{max-width:1200px;margin:0 auto;padding:24px}
h1{color:#7dd3fc;border-bottom:2px solid #334155;padding-bottom:10px}
h2{color:#93c5fd;margin-top:30px}
.meta{color:#94a3b8;font-size:.88em;margin-bottom:16px}
.badge{display:inline-block;padding:3px 9px;border-radius:4px;font-size:.78em;margin-right:5px}
.b-theme{background:#1d4ed8;color:#bfdbfe}.b-sector{background:#134e4a;color:#6ee7b7}
.flag-OK{color:#4ade80}.flag-LIMITED_HISTORY{color:#fbbf24}.flag-VERY_SHORT_HISTORY{color:#f87171}
.rank-box{background:#1e293b;border-radius:8px;padding:18px;margin:18px 0;display:flex;gap:40px;flex-wrap:wrap}
.rank-num{font-size:2.8em;color:#7dd3fc;font-weight:700}.rank-lbl{font-size:.78em;color:#94a3b8}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:14px;margin:16px 0}
.card{background:#1e293b;border-radius:8px;padding:14px;border:1px solid #334155}
.card .lbl{font-size:.74em;color:#94a3b8;margin-bottom:3px}.card .val{font-size:1.25em;font-weight:700;color:#7dd3fc}
.val.pos{color:#4ade80}.val.neg{color:#f87171}
table{width:100%;border-collapse:collapse;font-size:.84em;margin:12px 0}
th{background:#1e3a5f;color:#93c5fd;padding:8px 10px;text-align:left}
td{padding:7px 10px;border-bottom:1px solid #1e293b}
tr:hover{background:#1e293b}
.chart{margin:18px 0;background:#1e293b;border-radius:8px;padding:10px}
.theme-list{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.theme-pill{background:#1e3a5f;border-radius:20px;padding:4px 12px;font-size:.82em}
.disc{background:#1e293b;border:1px solid #374151;border-radius:8px;padding:14px;margin-top:28px;font-size:.78em;color:#6b7280}
"""

_TEMPLATE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>{{ ticker }} — {{ name }}</title>
<style>{{ css }}</style></head>
<body><div class="wrap">
<h1>{{ ticker }} — {{ name }}</h1>
<div class="meta">
  Analysis date: {{ date }}
  {% if theme %}<span class="badge b-theme">{{ theme }}</span>{% endif %}
  {% if sector %}<span class="badge b-sector">{{ sector }}</span>{% endif %}
  <span class="flag-{{ quality_class }}">{{ data_quality_flag }} ({{ history_days }}d)</span>
</div>

{% if ticker_themes %}
<div class="theme-list">
{% for t in ticker_themes %}
  <span class="theme-pill">{{ t.theme }}: {{ '★' * t.theme_purity }}</span>
{% endfor %}
</div>
{% endif %}

{% if theme_rank %}
<div class="rank-box">
  <div><div class="rank-lbl">Theme Rank ({{ theme }})</div><div class="rank-num">#{{ theme_rank }}</div></div>
  {% if category_rank %}<div><div class="rank-lbl">Category Rank</div><div class="rank-num">#{{ category_rank }}</div></div>{% endif %}
</div>
{% endif %}

<h2>Price Chart</h2>
<div class="chart">{{ price_chart }}</div>

<h2>Volume &amp; Traded Value</h2>
<div class="chart">{{ vol_chart }}</div>

<h2>Key Metrics</h2>
<div class="grid">
{% for m in metrics %}
<div class="card"><div class="lbl">{{ m.label }}</div><div class="val {{ m.cls }}">{{ m.value }}</div></div>
{% endfor %}
</div>

{% if bm %}
<h2>Benchmark Comparison ({{ bm.ticker }})</h2>
<div class="grid">
  <div class="card"><div class="lbl">Beta</div><div class="val">{{ '%.2f'|format(bm.beta or 0) }}</div></div>
  <div class="card"><div class="lbl">Alpha (ann.)</div>
    <div class="val {{ 'pos' if (bm.alpha or 0) > 0 else 'neg' }}">{{ '%.1f%%'|format((bm.alpha or 0)*100) }}</div></div>
</div>
{% endif %}

{% if top_corr %}
<h2>Top Correlated (Theme)</h2>
<table><thead><tr><th>Ticker</th><th>Correlation</th></tr></thead><tbody>
{% for r in top_corr %}<tr><td>{{ r.ticker }}</td><td>{{ '%.3f'|format(r.correlation) }}</td></tr>{% endfor %}
</tbody></table>
{% endif %}

{% if scores %}
<h2>Score Breakdown</h2>
<table><thead><tr><th>Component</th><th>Score (0–1)</th></tr></thead><tbody>
{% for s in scores %}<tr><td>{{ s.label }}</td><td>{{ '%.4f'|format(s.value or 0) }}</td></tr>{% endfor %}
</tbody></table>
{% endif %}

<div class="disc"><strong>Disclaimer:</strong> Research and educational purposes only.
Not investment advice. Data via Yahoo Finance / yfinance. Date: {{ date }}.</div>
</div></body></html>"""


# Local aliases kept for backward compatibility within this file
_pct = pct
_f = fmt
_cls = signed_cls


def _price_chart(dates, prices, ticker) -> str:
    if not dates:
        return "<p>No data.</p>"
    fig = go.Figure(go.Scatter(x=dates, y=prices, name=ticker, line=dict(color="#3b82f6", width=2)))
    fig.update_layout(template="plotly_dark", height=380, paper_bgcolor="#1e293b", plot_bgcolor="#0f172a",
                      title=f"{ticker} — Close Price")
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


def _vol_chart(dates, volumes, traded_values, ticker) -> str:
    if not dates:
        return "<p>No data.</p>"
    fig = make_subplots(rows=2, cols=1, subplot_titles=["Volume", "Traded Value"], vertical_spacing=0.14)
    if volumes:
        fig.add_trace(go.Bar(x=dates, y=volumes, name="Volume", marker_color="#6366f1"), row=1, col=1)
    if traded_values:
        fig.add_trace(go.Bar(x=dates, y=traded_values, name="Traded Value", marker_color="#8b5cf6"), row=2, col=1)
    fig.update_layout(template="plotly_dark", height=460, paper_bgcolor="#1e293b", plot_bgcolor="#0f172a", showlegend=False)
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


def generate_stock_html_report(analysis_result: dict, output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    data = build_stock_report_data(analysis_result)

    ticker = data.get("ticker", "")
    m = data.get("metrics_dict", {})
    dq = data.get("data_quality", {})
    flag = dq.get("data_quality_flag", "UNKNOWN")
    quality_class_map = {"OK": "OK", "LIMITED_HISTORY": "LIMITED_HISTORY", "VERY_SHORT_HISTORY": "VERY_SHORT_HISTORY"}

    def metric(label, value, cls=""):
        return {"label": label, "value": value, "cls": cls}

    key_metrics = [
        metric("Return 1M", _pct(m.get("return_1m")), _cls(m.get("return_1m"))),
        metric("Return 3M", _pct(m.get("return_3m")), _cls(m.get("return_3m"))),
        metric("Return 6M", _pct(m.get("return_6m")), _cls(m.get("return_6m"))),
        metric("Return 12M", _pct(m.get("return_12m")), _cls(m.get("return_12m"))),
        metric("Ann. Volatility", _pct(m.get("annualized_volatility"))),
        metric("Max Drawdown 12M", _pct(m.get("max_drawdown_12m"))),
        metric("Sharpe 6M", _f(m.get("sharpe_6m"))),
        metric("Sharpe 12M", _f(m.get("sharpe_12m"))),
        metric("Sortino 12M", _f(m.get("sortino_12m"))),
        metric("Calmar 12M", _f(m.get("calmar_12m"))),
        metric("From 52W High", _pct(m.get("distance_from_52w_high")), _cls(m.get("distance_from_52w_high"))),
        metric("From 52W Low", _pct(m.get("distance_from_52w_low")), _cls(m.get("distance_from_52w_low"))),
        metric("From MA50", _pct(m.get("distance_from_ma_50")), _cls(m.get("distance_from_ma_50"))),
        metric("From MA200", _pct(m.get("distance_from_ma_200")), _cls(m.get("distance_from_ma_200"))),
        metric("Avg Trade Value 3M", f"{m.get('avg_traded_value_3m',0):,.0f}" if m.get("avg_traded_value_3m") else "N/A"),
    ]

    rr = data.get("ranking_row", pd.Series(dtype=float))
    score_labels = [
        ("Final Score", "final_score"),
        ("Momentum", "momentum_score"),
        ("Risk-Adj Return", "risk_adjusted_return_score"),
        ("Liquidity", "liquidity_score"),
        ("Volatility", "volatility_score"),
        ("Drawdown", "drawdown_score"),
        ("Theme Purity", "theme_purity_score"),
    ]
    scores = []
    if hasattr(rr, "get"):
        for label, key in score_labels:
            v = rr.get(key)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                scores.append({"label": label, "value": float(v)})

    bm_raw = data.get("benchmark_metrics", {})
    bm = {"ticker": bm_raw.get("benchmark_ticker", ""), "beta": bm_raw.get("beta"), "alpha": bm_raw.get("alpha")} if bm_raw else None

    corr_df = data.get("top_correlated", pd.DataFrame())
    top_corr = corr_df.to_dict("records") if not corr_df.empty else []

    html = Template(_TEMPLATE).render(
        css=_CSS,
        ticker=ticker,
        name=data.get("name", ticker),
        theme=data.get("theme"),
        sector=data.get("sector"),
        date=today_str(),
        theme_rank=data.get("theme_rank"),
        category_rank=data.get("category_rank"),
        history_days=dq.get("available_history_days", 0),
        data_quality_flag=flag,
        quality_class=quality_class_map.get(flag, "VERY_SHORT_HISTORY"),
        ticker_themes=data.get("ticker_themes", []),
        price_chart=_price_chart(data.get("chart_dates", []), data.get("chart_prices", []), ticker),
        vol_chart=_vol_chart(data.get("chart_dates", []), data.get("chart_volumes", []), data.get("chart_traded_values", []), ticker),
        metrics=key_metrics,
        bm=bm,
        top_corr=top_corr,
        scores=scores if scores else None,
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Stock report: {output_path}")
