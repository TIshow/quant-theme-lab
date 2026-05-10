"""
Cross-theme comparison report.
Answers: "Which theme is strongest right now?"
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
from pathlib import Path
from jinja2 import Template
from src.utils.dates import today_str
from src.utils.logger import get_logger

logger = get_logger(__name__)

_CSS = """
body{font-family:'Segoe UI',sans-serif;margin:0;background:#0f0f1a;color:#e0e0e0}
.wrap{max-width:1300px;margin:0 auto;padding:24px}
h1{color:#7dd3fc;border-bottom:2px solid #334155;padding-bottom:10px}
h2{color:#93c5fd;margin-top:30px}
.meta{color:#94a3b8;font-size:.88em;margin-bottom:16px}
table{width:100%;border-collapse:collapse;font-size:.84em;margin:12px 0}
th{background:#1e3a5f;color:#93c5fd;padding:8px 10px;text-align:left}
td{padding:7px 10px;border-bottom:1px solid #1e293b}
tr:hover{background:#1e293b}
.pos{color:#4ade80}.neg{color:#f87171}
.chart{margin:18px 0;background:#1e293b;border-radius:8px;padding:10px}
.disc{background:#1e293b;border:1px solid #374151;border-radius:8px;padding:14px;margin-top:28px;font-size:.78em;color:#6b7280}
"""

_TEMPLATE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>Theme Universe Comparison</title>
<style>{{ css }}</style></head>
<body><div class="wrap">
<h1>Cross-Theme Comparison</h1>
<div class="meta">Analysis date: {{ date }} &nbsp;|&nbsp; Themes: {{ themes|join(', ') }}</div>

<h2>Cumulative Returns by Theme</h2>
<div class="chart">{{ cum_chart }}</div>

<h2>Theme Statistics</h2>
<table>
<thead><tr>
  <th>Theme</th><th>Cumul. Return</th><th>Return 1M</th><th>Return 3M</th>
  <th>Ann. Vol</th><th>Sharpe</th><th>Max DD</th><th>Calmar</th><th>Excess vs BM</th>
</tr></thead>
<tbody>
{% for r in stats %}
<tr>
  <td><strong>{{ r.theme }}</strong></td>
  <td class="{{ 'pos' if (r.cumulative_return or 0) > 0 else 'neg' }}">{{ '%.1f%%'|format((r.cumulative_return or 0)*100) }}</td>
  <td class="{{ 'pos' if (r.return_1m or 0) > 0 else 'neg' }}">{{ '%.1f%%'|format((r.return_1m or 0)*100) if r.return_1m == r.return_1m else 'N/A' }}</td>
  <td class="{{ 'pos' if (r.return_3m or 0) > 0 else 'neg' }}">{{ '%.1f%%'|format((r.return_3m or 0)*100) if r.return_3m == r.return_3m else 'N/A' }}</td>
  <td>{{ '%.1f%%'|format((r.annualized_volatility or 0)*100) }}</td>
  <td>{{ '%.2f'|format(r.sharpe or 0) }}</td>
  <td class="neg">{{ '%.1f%%'|format((r.max_drawdown or 0)*100) }}</td>
  <td>{{ '%.2f'|format(r.calmar or 0) if r.calmar == r.calmar else 'N/A' }}</td>
  <td class="{{ 'pos' if (r.get('excess_return',0) or 0) > 0 else 'neg' }}">{{ '%.1f%%'|format((r.get('excess_return',0) or 0)*100) if r.get('excess_return') == r.get('excess_return') else 'N/A' }}</td>
</tr>
{% endfor %}
</tbody></table>

<h2>Theme Momentum Score (short vs long momentum spread)</h2>
<div class="chart">{{ momentum_chart }}</div>

<div class="disc"><strong>Disclaimer:</strong> Research and educational purposes only.
Not investment advice. Equal-weight portfolios, data via Yahoo Finance. Date: {{ date }}.</div>
</div></body></html>"""


def _cum_chart(theme_returns: pd.DataFrame) -> str:
    if theme_returns.empty:
        return "<p>No data.</p>"
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    for i, col in enumerate(theme_returns.columns):
        cum = (1 + theme_returns[col].fillna(0)).cumprod() - 1
        fig.add_trace(go.Scatter(x=cum.index, y=cum.values, name=col,
                                 line=dict(color=colors[i % len(colors)], width=2)))
    fig.update_layout(template="plotly_dark", height=420, paper_bgcolor="#1e293b", plot_bgcolor="#0f172a",
                      legend=dict(orientation="h", y=1.04), title="Equal-Weight Theme Portfolio Cumulative Returns")
    fig.update_yaxes(tickformat=".1%")
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


def _momentum_chart(mom_score: pd.Series) -> str:
    if mom_score.empty:
        return "<p>No data.</p>"
    colors = ["#4ade80" if v >= 0 else "#f87171" for v in mom_score.values]
    fig = go.Figure(go.Bar(x=mom_score.index, y=mom_score.values, marker_color=colors, name="Momentum Score"))
    fig.update_layout(template="plotly_dark", height=320, paper_bgcolor="#1e293b", plot_bgcolor="#0f172a",
                      title="Theme Momentum (1M vs 3M spread)")
    fig.update_yaxes(tickformat=".1%")
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


def generate_universe_html_report(
    theme_returns: pd.DataFrame,
    theme_stats: pd.DataFrame,
    momentum_score: pd.Series,
    output_path: str,
) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    html = Template(_TEMPLATE).render(
        css=_CSS,
        date=today_str(),
        themes=theme_returns.columns.tolist(),
        cum_chart=_cum_chart(theme_returns),
        stats=theme_stats.to_dict("records"),
        momentum_chart=_momentum_chart(momentum_score),
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Universe report: {output_path}")
