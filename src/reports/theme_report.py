import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
from pathlib import Path
from jinja2 import Template
from src.utils.dates import today_str
from src.utils.logger import get_logger
from src.reports.format_utils import fmt

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
    <div class="leg-formula">Momentum×0.20 + Risk-Adj×0.23 + Fundamentals×0.15 + Purity×0.18 + Vola×0.08 + DD×0.08 + Liquidity×0.08</div>
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
    <div class="leg-formula">avg(Volume) — 直近3M</div>
    <div class="leg-desc">平均出来高（3ヶ月）。株価に依存しない純粋な取引活発度。高いほどスコア高。</div>
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
    <div class="leg-name">Fundamentals</div>
    <div class="leg-formula">ROE×0.25 + ROA×0.15 + 営利率×0.25 + 売上成長×0.20 + FCFマージン×0.15</div>
    <div class="leg-desc">JP株はIRBank、US株はyfinanceから取得。<strong>地域内（JP/US）で独立してランク正規化</strong>（ROE平均がJP 8〜10% / US 15〜20% と構造的に異なるため）。</div>
  </div>
  <div class="leg-item">
    <div class="leg-name">History / Quality</div>
    <div class="leg-formula">取得できた営業日数</div>
    <div class="leg-desc">OK≥252日 / LIMITED_HISTORY 120〜251日 / VERY_SHORT_HISTORY &lt;120日。日数不足だとSharpe_12M等がNaN。</div>
  </div>
</div>
<table>
<thead><tr><th>Rank</th><th>Ticker</th><th>Name</th><th>Country</th><th>Purity</th>
<th>Final Score</th><th>Momentum</th><th>Risk-Adj</th><th>Fundamentals</th><th>Liquidity</th><th>Vola</th><th>DD</th>
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
<td>{{ '%.3f'|format(r.get('fundamentals_score',0) or 0) }}</td>
<td>{{ '%.3f'|format(r.get('liquidity_score',0) or 0) }}</td>
<td>{{ '%.3f'|format(r.get('volatility_score',0) or 0) }}</td>
<td>{{ '%.3f'|format(r.get('drawdown_score',0) or 0) }}</td>
<td>{{ r.get('available_history_days','') }}</td>
<td class="flag-{{ r.get('data_quality_flag','') }}">{{ r.get('data_quality_flag','') }}</td>
</tr>
{% endfor %}
</tbody></table>

<h2>地域別サブランキング</h2>
<div class="desc" style="font-size:.82em">JP / US それぞれの地域内 Final Score 順。Fundamentals スコアは地域内正規化済み。</div>
{{ jp_sub_ranking }}
{{ us_sub_ranking }}

<h2>クロスマーケット バリュエーション比較</h2>
<div class="desc" style="font-size:.82em">JP株 vs US株の財務指標中央値比較。地域間の相対割安・割高を把握するための参考指標。</div>
{{ cross_market_chart }}
{{ cross_market_table }}

<h2>Quantamental Analysis</h2>
<div class="desc" style="font-size:.82em">
  価格シグナル（モメンタム・リスク調整リターン）と財務指標（ROE・ROA・営利率・売上成長・FCF）を組み合わせたクオンタメンタル分析。
  <strong>右上（高Fundamentals × 高Momentum）</strong>が最も有望なゾーン。財務データは日本株のみ（IRBank経由）。
</div>
{{ quant_scatter }}
{{ fundamental_bar }}
{{ fundamental_table }}

<h2>Fundamental Factor Weights (Annual IC-derived)</h2>
<div class="desc" style="font-size:.82em">
  各財務ファクターの重みは <strong>年次 ICIR</strong>（年率リターンとの Spearman IC の情報比）から自動計算されます。
  申告ラグ 90 日 + 12 ヶ月フォワードリターンを使用。データ不足時は等ウェイトにフォールバック。
</div>
{{ fund_ic_table }}

<h2>Factor Weights (IC-derived)</h2>
<div class="desc" style="font-size:.82em">
  各コンポーネントの重みは YAML 固定値ではなく、<strong>ICIR（IC情報比）</strong> から自動計算されます。
  ICIR = mean(IC) / std(IC)。ICIR &gt; 0.3 が実用的なシグナルの目安。theme_purity のみ YAML 固定。
</div>
{{ ic_table }}

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


# _fmt is imported as fmt from format_utils — kept as alias for callers in this file
_fmt = fmt


def _fundamental_table(ranking_df: pd.DataFrame) -> str:
    fund_cols = [
        ("fundamental_roe", "ROE %"),
        ("fundamental_roa", "ROA %"),
        ("fundamental_operating_margin", "営利率 %"),
        ("fundamental_revenue_growth", "売上成長 %"),
        ("fundamental_free_cf_margin", "FCFマージン %"),
        ("fundamentals_score", "Fund.Score"),
    ]
    rows_html = ""
    for _, r in ranking_df.iterrows():
        country = r.get("country", "")
        cells = "".join(
            f"<td>{ _fmt(r.get(col), 2 if col == 'fundamentals_score' else 1) }</td>"
            for col, _ in fund_cols
        )
        rows_html += f"<tr><td><strong>{r['Ticker']}</strong></td><td>{r.get('name','')}</td><td>{country}</td>{cells}</tr>"

    if not rows_html:
        return "<p style='color:#94a3b8'>財務データなし</p>"

    headers = "".join(f"<th>{label}</th>" for _, label in fund_cols)
    return (
        "<table><thead><tr><th>Ticker</th><th>Name</th><th>Country</th>" + headers + "</tr></thead>"
        "<tbody>" + rows_html + "</tbody></table>"
    )


def _sub_ranking_table(ranking_df: pd.DataFrame, region: str) -> str:
    col = "country" if "country" in ranking_df.columns else "region"
    sub = ranking_df[ranking_df[col] == region].copy()
    if sub.empty:
        return f"<p style='color:#94a3b8'>{region} 銘柄なし</p>"

    sub = sub.sort_values("final_score", ascending=False).reset_index(drop=True)
    sub["sub_rank"] = range(1, len(sub) + 1)

    label = "🇯🇵 Japan" if region == "JP" else "🇺🇸 United States"
    rows_html = ""
    for _, r in sub.iterrows():
        rows_html += (
            f"<tr>"
            f"<td><span class='badge b-rank'>{int(r['sub_rank'])}</span></td>"
            f"<td><strong>{r['Ticker']}</strong></td>"
            f"<td>{r.get('name', '')}</td>"
            f"<td>{'★' * int(r.get('theme_purity', 0))}</td>"
            f"<td>{_fmt(r.get('final_score'), 3)}</td>"
            f"<td>{_fmt(r.get('momentum_score'), 3)}</td>"
            f"<td>{_fmt(r.get('risk_adjusted_return_score'), 3)}</td>"
            f"<td>{_fmt(r.get('fundamentals_score'), 3)}</td>"
            f"<td>{_fmt(r.get('fundamental_roe'), 1)}</td>"
            f"<td>{_fmt(r.get('fundamental_revenue_growth'), 1)}</td>"
            f"</tr>"
        )
    return (
        f"<h3>{label} ({len(sub)} 銘柄)</h3>"
        "<table><thead><tr>"
        "<th>Rank</th><th>Ticker</th><th>Name</th><th>Purity</th>"
        "<th>Final</th><th>Mom.</th><th>Risk-Adj</th><th>Fund.</th><th>ROE%</th><th>Rev.Growth%</th>"
        "</tr></thead><tbody>" + rows_html + "</tbody></table>"
    )


def _cross_market_chart(ranking_df: pd.DataFrame) -> str:
    if "country" not in ranking_df.columns:
        return ""

    metrics = [
        ("fundamental_roe",              "ROE %"),
        ("fundamental_roa",              "ROA %"),
        ("fundamental_operating_margin", "営業利益率 %"),
        ("fundamental_revenue_growth",   "売上成長率 %"),
        ("fundamental_free_cf_margin",   "FCFマージン %"),
    ]
    available = [(col, lbl) for col, lbl in metrics if col in ranking_df.columns]
    if not available:
        return ""

    jp = ranking_df[ranking_df["country"] == "JP"]
    us = ranking_df[ranking_df["country"] == "US"]

    labels = [lbl for _, lbl in available]
    jp_vals = [jp[col].median() for col, _ in available]
    us_vals = [us[col].median() for col, _ in available]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="🇯🇵 JP 中央値", x=labels, y=jp_vals, marker_color="#3b82f6", opacity=0.85))
    fig.add_trace(go.Bar(name="🇺🇸 US 中央値", x=labels, y=us_vals, marker_color="#f59e0b", opacity=0.85))
    fig.update_layout(
        barmode="group",
        template="plotly_dark",
        height=360,
        paper_bgcolor="#1e293b",
        plot_bgcolor="#0f172a",
        title="JP vs US 財務指標中央値比較",
        legend=dict(orientation="h", y=1.08),
        yaxis_title="%",
    )
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


def _cross_market_table(ranking_df: pd.DataFrame) -> str:
    if "country" not in ranking_df.columns:
        return ""

    metrics = [
        ("fundamental_roe",              "ROE %"),
        ("fundamental_roa",              "ROA %"),
        ("fundamental_operating_margin", "営業利益率 %"),
        ("fundamental_revenue_growth",   "売上成長率 %"),
        ("fundamental_free_cf_margin",   "FCFマージン %"),
        ("fundamental_capex_ratio",      "設備投資率 %"),
        ("fundamentals_score",           "Fundamental Score"),
    ]

    jp = ranking_df[ranking_df["country"] == "JP"]
    us = ranking_df[ranking_df["country"] == "US"]

    rows_html = ""
    for col, lbl in metrics:
        if col not in ranking_df.columns:
            continue
        jp_med = jp[col].median()
        us_med = us[col].median()

        def _cell(v):
            if v is None or (isinstance(v, float) and np.isnan(v)):
                return "<td>—</td>"
            return f"<td>{v:.1f}</td>"

        # Indicate which is higher
        if not (np.isnan(float(jp_med)) if isinstance(jp_med, float) else False) and \
           not (np.isnan(float(us_med)) if isinstance(us_med, float) else False):
            arrow = "↑JP" if jp_med > us_med else "↑US"
            arrow_color = "#3b82f6" if "JP" in arrow else "#f59e0b"
            arrow_td = f"<td style='color:{arrow_color};font-weight:700'>{arrow}</td>"
        else:
            arrow_td = "<td>—</td>"

        rows_html += (
            f"<tr><td>{lbl}</td>{_cell(jp_med)}{_cell(us_med)}{arrow_td}</tr>"
        )

    if not rows_html:
        return ""

    return (
        "<table><thead><tr>"
        "<th>指標</th><th>🇯🇵 JP 中央値</th><th>🇺🇸 US 中央値</th><th>優位</th>"
        "</tr></thead><tbody>" + rows_html + "</tbody></table>"
    )


def _fundamental_bar_chart(ranking_df: pd.DataFrame) -> str:
    jp = ranking_df[ranking_df["Ticker"].str.endswith(".T", na=False)].copy()
    metrics = {
        "fundamental_roe": "ROE %",
        "fundamental_roa": "ROA %",
        "fundamental_operating_margin": "営利率 %",
    }
    available = {k: v for k, v in metrics.items() if k in jp.columns}
    if jp.empty or not available:
        return ""

    fig = go.Figure()
    colors = ["#3b82f6", "#10b981", "#f59e0b"]
    for (col, label), color in zip(available.items(), colors):
        fig.add_trace(go.Bar(
            name=label, x=jp["Ticker"], y=jp[col],
            marker_color=color, opacity=0.85,
        ))
    fig.update_layout(
        barmode="group", template="plotly_dark",
        height=360, paper_bgcolor="#1e293b", plot_bgcolor="#0f172a",
        title="財務指標比較（JP銘柄）",
        legend=dict(orientation="h", y=1.08),
        yaxis_title="%",
    )
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


def _quantamental_scatter(ranking_df: pd.DataFrame) -> str:
    df = ranking_df.dropna(subset=["fundamentals_score", "momentum_score"]).copy()
    if df.empty:
        return "<p style='color:#94a3b8'>散布図データなし</p>"

    mid_f = df["fundamentals_score"].median()
    mid_m = df["momentum_score"].median()

    colors = []
    for _, r in df.iterrows():
        f, m = r["fundamentals_score"], r["momentum_score"]
        if f >= mid_f and m >= mid_m:
            colors.append("#4ade80")   # 右上: ideal
        elif f < mid_f and m >= mid_m:
            colors.append("#fbbf24")   # 左上: momentum only
        elif f >= mid_f and m < mid_m:
            colors.append("#60a5fa")   # 右下: quality trap
        else:
            colors.append("#f87171")   # 左下: avoid

    fig = go.Figure()
    fig.add_shape(type="line", x0=mid_f, x1=mid_f, y0=0, y1=1,
                  line=dict(color="#475569", dash="dash", width=1))
    fig.add_shape(type="line", x0=0, x1=1, y0=mid_m, y1=mid_m,
                  line=dict(color="#475569", dash="dash", width=1))

    fig.add_trace(go.Scatter(
        x=df["fundamentals_score"], y=df["momentum_score"],
        mode="markers+text",
        text=df["Ticker"],
        textposition="top center",
        textfont=dict(size=10, color="#e2e8f0"),
        marker=dict(size=12, color=colors, line=dict(width=1, color="#1e293b")),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Fundamentals: %{x:.3f}<br>"
            "Momentum: %{y:.3f}<extra></extra>"
        ),
    ))

    fig.add_annotation(x=0.85, y=0.92, xref="paper", yref="paper",
                       text="★ 理想（高F×高M）", showarrow=False,
                       font=dict(color="#4ade80", size=11))
    fig.add_annotation(x=0.15, y=0.92, xref="paper", yref="paper",
                       text="モメンタム先行", showarrow=False,
                       font=dict(color="#fbbf24", size=11))
    fig.add_annotation(x=0.85, y=0.08, xref="paper", yref="paper",
                       text="財務は強いが株価弱い", showarrow=False,
                       font=dict(color="#60a5fa", size=11))
    fig.add_annotation(x=0.15, y=0.08, xref="paper", yref="paper",
                       text="回避", showarrow=False,
                       font=dict(color="#f87171", size=11))

    fig.update_layout(
        template="plotly_dark", height=480,
        paper_bgcolor="#1e293b", plot_bgcolor="#0f172a",
        title="Quantamental Quadrant: Fundamentals × Momentum",
        xaxis=dict(title="Fundamentals Score", range=[0, 1]),
        yaxis=dict(title="Momentum Score", range=[0, 1]),
    )
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


def _ic_interpretation(r: dict) -> str:
    """One-line plain-language reading of a single factor's IC result."""
    c = r.get("component", "")
    icir = r.get("icir", float("nan"))
    mean_ic = r.get("mean_ic", float("nan"))

    if pd.isna(icir):
        return "データ不足のため判定不可"

    if c == "momentum":
        if abs(icir) < 0.1:
            return "過去リターンは翌月をほぼ予測しない（ランダム）"
        return "モメンタムに予測力あり" if icir > 0 else "逆張り的（上昇後に反落しやすい）"

    if c == "volatility":
        if icir < -0.1:
            return "高ボラ銘柄の方が翌月リターンが高い傾向（平均回帰・リバウンド効果）"
        if icir > 0.1:
            return "低ボラ銘柄が翌月も優位（安定銘柄に予測力）"
        return "ボラティリティに翌月予測力なし"

    if c == "drawdown":
        if icir > 0.1:
            return "ドローダウンが小さい銘柄が翌月も優位"
        if icir < -0.1:
            return "大きく下げた銘柄がリバウンドしやすい傾向"
        return "ドローダウンに翌月予測力なし"

    if c == "liquidity":
        if icir > 0.1:
            return "出来高が多い銘柄が翌月優位（流動性プレミアム）"
        if icir < -0.1:
            return "出来高が少ない銘柄が翌月優位（小型株効果）"
        return "出来高に翌月予測力なし"

    if c == "risk_adjusted_return":
        if icir > 0.2:
            return "Sharpeが高い銘柄が翌月もアウトパフォームしやすい"
        return "リスク調整リターンの予測力は限定的"

    return ""


def _ic_table(ic_summary: pd.DataFrame, weights: dict) -> str:
    if ic_summary.empty:
        return "<p style='color:#94a3b8'>No IC data.</p>"

    # Column header explanations
    header_notes = (
        "<div style='font-size:.75em;color:#94a3b8;margin-bottom:8px'>"
        "<strong>Mean IC</strong>: 毎月の「ファクター→翌月リターン」Spearman相関の平均。"
        "　<strong>ICIR</strong>: その安定性（mean/std）。±0.3超で実用シグナル。"
        "　<strong>Weight</strong>: ICIR絶対値に比例して自動決定された重み。"
        "</div>"
        "<div style='font-size:.72em;color:#fbbf24;margin-bottom:8px;padding:5px 10px;"
        "background:#1e293b;border-left:3px solid #fbbf24;border-radius:4px'>"
        "⚠️ <strong>インサンプル注意</strong>: "
        "これらのICIRは分析対象期間の全データで計算されており、"
        "バックテスト期間と同じデータを使用しています。"
        "厳密なアウトオブサンプル検証にはWalk-forwardでのIC計算が必要です（将来実装予定）。"
        "</div>"
    )

    rows_html = ""
    for _, r in ic_summary.iterrows():
        c = r["component"]
        w = weights.get(c, 0.0)
        usable = r.get("usable", False)
        badge = "<span style='color:#4ade80'>✔ usable</span>" if usable else "<span style='color:#f87171'>✘ noise</span>"
        icir_val = f"{r['icir']:.3f}" if pd.notna(r.get("icir")) else "N/A"
        mean_ic_val = f"{r['mean_ic']:.3f}" if pd.notna(r.get("mean_ic")) else "N/A"
        interp = _ic_interpretation(dict(r))
        rows_html += (
            f"<tr>"
            f"<td>{c}</td>"
            f"<td style='color:#94a3b8'>{r['factor']}</td>"
            f"<td>{mean_ic_val}</td>"
            f"<td>{icir_val}</td>"
            f"<td>{r.get('n_periods', 0)}</td>"
            f"<td><strong style='color:#7dd3fc'>{w:.3f}</strong></td>"
            f"<td>{badge}</td>"
            f"<td style='font-size:.78em;color:#94a3b8'>{interp}</td>"
            f"</tr>"
        )

    # Overall interpretation
    all_noise = ic_summary["usable"].sum() == 0
    if all_noise:
        overall = (
            "<div style='margin-top:12px;padding:10px 14px;background:#1e293b;"
            "border-left:3px solid #f87171;border-radius:6px;font-size:.8em'>"
            "<strong style='color:#f87171'>全ファクターがノイズ水準</strong>："
            "価格データだけではこのセクターの翌月リターンを予測できない。"
            "補助金・受注・政策など<strong>価格以外の情報</strong>がリターンを支配している可能性が高い。"
            "財務データ・テーマKPIの追加が有効。"
            "</div>"
        )
    else:
        usable_names = ic_summary[ic_summary["usable"]]["component"].tolist()
        overall = (
            f"<div style='margin-top:12px;padding:10px 14px;background:#1e293b;"
            f"border-left:3px solid #4ade80;border-radius:6px;font-size:.8em'>"
            f"有効シグナル: <strong style='color:#4ade80'>{', '.join(usable_names)}</strong>"
            f"</div>"
        )

    return (
        header_notes
        + "<table><thead><tr>"
        "<th>Component</th><th>Factor</th><th>Mean IC</th><th>ICIR</th>"
        "<th>Periods</th><th>Weight</th><th>Signal</th><th>読み方</th>"
        "</tr></thead><tbody>" + rows_html + "</tbody></table>"
        + overall
    )


def _fundamental_ic_table(fund_ic_summary: pd.DataFrame) -> str:
    if fund_ic_summary.empty:
        return "<p style='color:#94a3b8'>No fundamental IC data.</p>"

    has_low_sample = fund_ic_summary.get("low_sample", pd.Series(dtype=bool)).any()
    has_ci_cross = fund_ic_summary.get("ci_crosses_zero", pd.Series(dtype=bool)).any()

    header_notes = (
        "<div style='font-size:.75em;color:#94a3b8;margin-bottom:8px'>"
        "<strong>Mean IC</strong>: 財務指標と翌年リターンの Spearman 相関の平均。"
        "　<strong>ICIR</strong>: IC の安定性（mean/std）。0.15超で有効シグナル（年次データは基準が低め）。"
        "　<strong>95% CI</strong>: Bootstrap信頼区間。ゼロをまたぐ場合はノイズの可能性。"
        "　<strong>方向性</strong>: IC が負 = 低い方が翌年リターン高（逆張り）。スコアリングに自動反映済み。"
        "</div>"
    )

    if has_low_sample:
        header_notes += (
            "<div style='font-size:.75em;color:#fbbf24;margin-bottom:8px;padding:6px 10px;"
            "background:#1e293b;border-left:3px solid #fbbf24;border-radius:4px'>"
            "⚠️ <strong>少数銘柄警告</strong>: "
            "クロスセクションの銘柄数が少ない（目安20未満）ため、ICIRの推定精度が低い。"
            "信頼区間を必ず確認し、ゼロをまたぐ場合は過信しないこと。"
            "</div>"
        )

    rows_html = ""
    for _, r in fund_ic_summary.iterrows():
        metric = r["metric"]
        usable = r.get("usable", False)
        badge = "<span style='color:#4ade80'>✔ usable</span>" if usable else "<span style='color:#f87171'>✘ noise</span>"
        icir_val = f"{r['icir']:.3f}" if pd.notna(r.get("icir")) else "N/A"
        mean_ic_val = f"{r['mean_ic']:.3f}" if pd.notna(r.get("mean_ic")) else "N/A"
        direction = r.get("direction", "—")
        dir_color = "#f87171" if "低" in str(direction) else "#4ade80"

        ci_lo = r.get("ci_lower")
        ci_hi = r.get("ci_upper")
        if pd.notna(ci_lo) and pd.notna(ci_hi):
            crosses = ci_lo < 0 < ci_hi
            ci_color = "#f87171" if crosses else "#94a3b8"
            ci_str = f"<span style='color:{ci_color}'>[{ci_lo:.2f}, {ci_hi:.2f}]</span>"
        else:
            ci_str = "—"

        low_s = r.get("low_sample", False)
        n_str = str(r.get("n_periods", 0))
        if low_s:
            n_str = f"<span style='color:#fbbf24'>{n_str} ⚠</span>"

        rows_html += (
            f"<tr>"
            f"<td>{metric}</td>"
            f"<td>{mean_ic_val}</td>"
            f"<td>{icir_val}</td>"
            f"<td>{ci_str}</td>"
            f"<td>{n_str}</td>"
            f"<td style='color:{dir_color}'>{direction}</td>"
            f"<td>{badge}</td>"
            f"</tr>"
        )

    return (
        header_notes
        + "<table><thead><tr>"
        "<th>Metric</th><th>Mean IC</th><th>ICIR</th><th>95% CI</th><th>Periods</th>"
        "<th>方向性</th><th>Signal</th>"
        "</tr></thead><tbody>" + rows_html + "</tbody></table>"
    )


def generate_theme_html_report(
    theme: str,
    config: dict,
    universe_df: pd.DataFrame,
    ranking_df: pd.DataFrame,
    correlation_df: pd.DataFrame,
    clusters_df: pd.DataFrame,
    backtest_df: pd.DataFrame,
    output_path: str,
    ic_summary: pd.DataFrame | None = None,
    ic_weights: dict | None = None,
    fund_ic_summary: pd.DataFrame | None = None,
) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    n_jp = int((universe_df["country"] == "JP").sum()) if "country" in universe_df.columns else 0
    n_us = int((universe_df["country"] == "US").sum()) if "country" in universe_df.columns else 0
    avg_purity = f"{universe_df['theme_purity'].mean():.1f}" if "theme_purity" in universe_df.columns else "N/A"

    _ic_summary = ic_summary if ic_summary is not None else pd.DataFrame()
    _ic_weights = ic_weights or {}
    _fund_ic_summary = fund_ic_summary if fund_ic_summary is not None else pd.DataFrame()

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
        jp_sub_ranking=_sub_ranking_table(ranking_df, "JP"),
        us_sub_ranking=_sub_ranking_table(ranking_df, "US"),
        cross_market_chart=_cross_market_chart(ranking_df),
        cross_market_table=_cross_market_table(ranking_df),
        quant_scatter=_quantamental_scatter(ranking_df),
        fundamental_bar=_fundamental_bar_chart(ranking_df),
        fundamental_table=_fundamental_table(ranking_df),
        fund_ic_table=_fundamental_ic_table(_fund_ic_summary),
        ic_table=_ic_table(_ic_summary, _ic_weights),
        backtest_chart=_backtest_chart(backtest_df),
        corr_chart=_corr_chart(correlation_df),
        cluster_chart=_cluster_chart(clusters_df),
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Theme report: {output_path}")
