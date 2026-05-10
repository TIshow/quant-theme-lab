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
.wrap{max-width:1400px;margin:0 auto;padding:24px}
h1{color:#7dd3fc;border-bottom:2px solid #334155;padding-bottom:10px}
h2{color:#93c5fd;margin-top:32px}
.meta{color:#94a3b8;font-size:.88em;margin-bottom:18px}
.desc{background:#1e293b;padding:14px;border-radius:8px;border-left:4px solid #3b82f6;margin:14px 0}
table{width:100%;border-collapse:collapse;font-size:.84em;margin:12px 0}
th{background:#1e3a5f;color:#93c5fd;padding:8px 10px;text-align:left}
td{padding:7px 10px;border-bottom:1px solid #1e293b}
tr:hover{background:#1e293b}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.78em}
.b-rank{background:#1d4ed8;color:#fff}
.b-cat{background:#134e4a;color:#6ee7b7}
.flag-OK{color:#4ade80}.flag-LIMITED_HISTORY{color:#fbbf24}.flag-VERY_SHORT_HISTORY{color:#f87171}
.chart{margin:20px 0;background:#1e293b;border-radius:8px;padding:10px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px;margin:16px 0}
.card{background:#1e293b;border-radius:8px;padding:14px;border:1px solid #334155}
.card .lbl{font-size:.74em;color:#94a3b8}.card .val{font-size:1.3em;color:#7dd3fc;font-weight:700}
.disc{background:#1e293b;border:1px solid #374151;border-radius:8px;padding:14px;margin-top:28px;font-size:.78em;color:#6b7280}
.legend{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px;margin:14px 0 20px}
.leg-item{background:#1e293b;border-radius:6px;padding:10px 14px;border-left:3px solid #3b82f6}
.leg-item .leg-name{font-size:.8em;font-weight:700;color:#93c5fd;margin-bottom:4px}
.leg-item .leg-formula{font-size:.74em;color:#7dd3fc;font-family:monospace;margin-bottom:3px}
.leg-item .leg-desc{font-size:.72em;color:#94a3b8}
"""

_TEMPLATE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>{{ display_name }} — Theme Report</title>
<style>{{ css }}</style></head>
<body><div class="wrap">
<h1>{{ display_name }}</h1>
<div class="meta">Analysis date: {{ date }} &nbsp;|&nbsp; Universe: {{ n_stocks }} stocks &nbsp;|&nbsp; Theme: {{ theme }}</div>
<div class="desc">{{ description }}</div>

<div class="grid">
  <div class="card"><div class="lbl">Total Stocks</div><div class="val">{{ n_stocks }}</div></div>
  <div class="card"><div class="lbl">JP Stocks</div><div class="val">{{ n_jp }}</div></div>
  <div class="card"><div class="lbl">US Stocks</div><div class="val">{{ n_us }}</div></div>
  <div class="card"><div class="lbl">Avg Theme Purity</div><div class="val">{{ avg_purity }}</div></div>
</div>

<h2>Ranking</h2>
<div class="legend">
  <div class="leg-item">
    <div class="leg-name">Final Score</div>
    <div class="leg-formula">Momentum×0.25 + Risk-Adj×0.25 + Purity×0.20 + Vola×0.10 + DD×0.10 + Liquidity×0.10</div>
    <div class="leg-desc">各指標について「ユニバース内で何番目か」をランク付けし 0〜1 に変換したうえで重み付き合計。1.0 = ユニバース内で全指標トップ。</div>
  </div>
  <div class="leg-item">
    <div class="leg-name">Momentum</div>
    <div class="leg-formula">Return_1M×0.2 + Return_3M×0.5 + Return_6M×0.3</div>
    <div class="leg-desc">価格モメンタムの複合スコア。3ヶ月リターンを最重視。</div>
  </div>
  <div class="leg-item">
    <div class="leg-name">Risk-Adj</div>
    <div class="leg-formula">Sharpe_6M×0.4 + Sharpe_12M×0.4 + Calmar_12M×0.2</div>
    <div class="leg-desc">リスク調整後リターン。Sharpe = 超過リターン / 標準偏差（年率）、Calmar = 年率リターン / 最大DD。</div>
  </div>
  <div class="leg-item">
    <div class="leg-name">Liquidity</div>
    <div class="leg-formula">avg(Close × Volume) — 直近3M</div>
    <div class="leg-desc">平均売買代金（3ヶ月）。流動性が高いほどスコア高。</div>
  </div>
  <div class="leg-item">
    <div class="leg-name">Vola</div>
    <div class="leg-formula">std(日次リターン) × √252</div>
    <div class="leg-desc">年率ボラティリティ。低いほどスコア高（安定＝良）。</div>
  </div>
  <div class="leg-item">
    <div class="leg-name">DD</div>
    <div class="leg-formula">min((終値 − 直近高値) / 直近高値)</div>
    <div class="leg-desc">最大ドローダウン。下落幅が小さいほどスコア高。</div>
  </div>
  <div class="leg-item">
    <div class="leg-name">Purity</div>
    <div class="leg-formula">1〜5（手動設定）</div>
    <div class="leg-desc">テーマへの純度。5=主要事業（売上70%+）、3=明確な露出（20〜40%）。</div>
  </div>
  <div class="leg-item">
    <div class="leg-name">History / Quality</div>
    <div class="leg-formula">取得できた営業日数</div>
    <div class="leg-desc">OK≥252日 / LIMITED_HISTORY 120〜251日 / VERY_SHORT_HISTORY &lt;120日。日数不足だとSharpe_12M等がNaN。</div>
  </div>
</div>
<table>
<thead><tr><th>Rank</th><th>Ticker</th><th>Name</th><th>Country</th><th>Purity</th>
<th>Final Score</th><th>Momentum</th><th>Risk-Adj</th><th>Liquidity</th><th>Vola</th><th>DD</th>
<th>History</th><th>Quality</th></tr></thead>
<tbody>
{% for r in rows %}
<tr>
<td><span class="badge b-rank">{{ r.rank }}</span></td>
<td><strong>{{ r.Ticker }}</strong></td>
<td>{{ r.get('name','') }}</td>
<td>{{ r.get('country','') }}</td>
<td>{{ '★' * (r.get('theme_purity',0)|int) }}</td>
<td>{{ '%.3f'|format(r.get('final_score',0) or 0) }}</td>
<td>{{ '%.3f'|format(r.get('momentum_score',0) or 0) }}</td>
<td>{{ '%.3f'|format(r.get('risk_adjusted_return_score',0) or 0) }}</td>
<td>{{ '%.3f'|format(r.get('liquidity_score',0) or 0) }}</td>
<td>{{ '%.3f'|format(r.get('volatility_score',0) or 0) }}</td>
<td>{{ '%.3f'|format(r.get('drawdown_score',0) or 0) }}</td>
<td>{{ r.get('available_history_days','') }}</td>
<td class="flag-{{ r.get('data_quality_flag','') }}">{{ r.get('data_quality_flag','') }}</td>
</tr>
{% endfor %}
</tbody></table>

<h2>Backtest (monthly momentum top-N, with transaction costs)</h2>
<div class="chart">{{ backtest_chart }}</div>

<h2>Correlation Matrix</h2>
<div class="chart">{{ corr_chart }}</div>

<h2>Clustering</h2>
<div class="chart">{{ cluster_chart }}</div>

<div class="disc"><strong>Disclaimer:</strong> For research and educational purposes only.
Not investment advice. Data via Yahoo Finance / yfinance. Date: {{ date }}.</div>
</div></body></html>"""


def _backtest_chart(bt: pd.DataFrame) -> str:
    if bt.empty or "portfolio_return" not in bt.columns:
        return "<p style='color:#94a3b8'>No backtest data.</p>"
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bt["date"], y=bt["cumulative_return"], name="Portfolio", line=dict(color="#3b82f6", width=2)))
    if "benchmark_cumulative_return" in bt.columns:
        fig.add_trace(go.Scatter(x=bt["date"], y=bt["benchmark_cumulative_return"], name="Benchmark", line=dict(color="#94a3b8", width=2, dash="dash")))
    fig.update_layout(template="plotly_dark", height=380, paper_bgcolor="#1e293b", plot_bgcolor="#0f172a",
                      legend=dict(orientation="h", y=1.04))
    fig.update_yaxes(tickformat=".1%")
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


def _corr_chart(corr: pd.DataFrame) -> str:
    if corr.empty:
        return "<p style='color:#94a3b8'>No correlation data.</p>"
    tickers = corr.columns.tolist()
    fig = go.Figure(go.Heatmap(z=corr.values, x=tickers, y=tickers,
                               colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
                               text=corr.round(2).values, texttemplate="%{text}", textfont={"size": 8}))
    fig.update_layout(template="plotly_dark", height=max(480, len(tickers) * 28),
                      paper_bgcolor="#1e293b", plot_bgcolor="#0f172a")
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


def _cluster_chart(clusters: pd.DataFrame) -> str:
    if clusters.empty:
        return "<p style='color:#94a3b8'>No cluster data.</p>"
    fig = px.strip(clusters, x="cluster", y="Ticker", color="cluster",
                   title="Cluster Assignment", template="plotly_dark")
    fig.update_layout(paper_bgcolor="#1e293b", plot_bgcolor="#0f172a", height=340)
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


def generate_theme_html_report(
    theme: str,
    config: dict,
    universe_df: pd.DataFrame,
    ranking_df: pd.DataFrame,
    correlation_df: pd.DataFrame,
    clusters_df: pd.DataFrame,
    backtest_df: pd.DataFrame,
    output_path: str,
) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    n_jp = int((universe_df["country"] == "JP").sum()) if "country" in universe_df.columns else 0
    n_us = int((universe_df["country"] == "US").sum()) if "country" in universe_df.columns else 0
    avg_purity = f"{universe_df['theme_purity'].mean():.1f}" if "theme_purity" in universe_df.columns else "N/A"

    html = Template(_TEMPLATE).render(
        css=_CSS,
        theme=theme,
        display_name=config.get("display_name", theme),
        description=config.get("description", ""),
        date=today_str(),
        n_stocks=len(universe_df),
        n_jp=n_jp,
        n_us=n_us,
        avg_purity=avg_purity,
        rows=ranking_df.to_dict(orient="records"),
        backtest_chart=_backtest_chart(backtest_df),
        corr_chart=_corr_chart(correlation_df),
        cluster_chart=_cluster_chart(clusters_df),
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Theme report: {output_path}")
