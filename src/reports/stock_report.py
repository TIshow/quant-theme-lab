import math

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
from src.reports.format_utils import (
    fmt, pct, signed_cls,
    fmt_x, fmt_jpy, fmt_usd, pct_already, pct_signed,
)

logger = get_logger(__name__)

_CSS = """
body{font-family:'Segoe UI',sans-serif;margin:0;background:#0f0f1a;color:#e0e0e0}
.wrap{max-width:1280px;margin:0 auto;padding:24px}
h1{color:#7dd3fc;border-bottom:2px solid #334155;padding-bottom:10px}
h2{color:#93c5fd;margin-top:30px}
h3{color:#7dd3fc;margin-top:20px;font-size:1.05em;border-left:3px solid #3b82f6;padding-left:8px}
.meta{color:#94a3b8;font-size:.88em;margin-bottom:16px}
.badge{display:inline-block;padding:3px 9px;border-radius:4px;font-size:.78em;margin-right:5px}
.b-theme{background:#1d4ed8;color:#bfdbfe}.b-sector{background:#134e4a;color:#6ee7b7}
.flag-OK{color:#4ade80}.flag-LIMITED_HISTORY{color:#fbbf24}.flag-VERY_SHORT_HISTORY{color:#f87171}
.rank-box{background:#1e293b;border-radius:8px;padding:18px;margin:18px 0;display:flex;gap:40px;flex-wrap:wrap}
.rank-num{font-size:2.8em;color:#7dd3fc;font-weight:700}.rank-lbl{font-size:.78em;color:#94a3b8}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(185px,1fr));gap:12px;margin:14px 0}
.card{background:#1e293b;border-radius:8px;padding:14px;border:1px solid #334155}
.card .lbl{font-size:.74em;color:#94a3b8;margin-bottom:3px}
.card .val{font-size:1.22em;font-weight:700;color:#7dd3fc}
.val.pos{color:#4ade80}.val.neg{color:#f87171}.val.neutral{color:#fbbf24}
table{width:100%;border-collapse:collapse;font-size:.84em;margin:12px 0}
th{background:#1e3a5f;color:#93c5fd;padding:8px 10px;text-align:left}
td{padding:7px 10px;border-bottom:1px solid #1e293b}
tr:hover{background:#1e293b}
.chart{margin:18px 0;background:#1e293b;border-radius:8px;padding:10px}
.theme-list{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.theme-pill{background:#1e3a5f;border-radius:20px;padding:4px 12px;font-size:.82em}
.fund-header{background:#1e293b;border-radius:8px;padding:14px 18px;margin:14px 0;
  display:flex;flex-wrap:wrap;gap:24px;align-items:center;border:1px solid #334155}
.fund-kv .k{font-size:.72em;color:#64748b}.fund-kv .v{font-size:1.1em;font-weight:600;color:#93c5fd}
.section-note{font-size:.76em;color:#64748b;margin:4px 0 12px}
.disc{background:#1e293b;border:1px solid #374151;border-radius:8px;padding:14px;
  margin-top:28px;font-size:.78em;color:#6b7280}
.hr-dim{border:none;border-top:1px solid #1e293b;margin:24px 0}
"""

_TEMPLATE = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>{{ ticker }} — {{ name }}</title>
<style>{{ css }}</style></head>
<body><div class="wrap">
<h1>{{ ticker }} — {{ name }}</h1>
<div class="meta">
  分析日: {{ date }}
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
  {% if category_rank %}<div><div class="rank-lbl">Region Rank (JP/US内)</div><div class="rank-num">#{{ category_rank }}</div></div>{% endif %}
</div>
{% endif %}

<h2>価格チャート</h2>
<div class="chart">{{ price_chart }}</div>

<h2>出来高・売買代金</h2>
<div class="chart">{{ vol_chart }}</div>

<h2>価格系メトリクス</h2>
<div class="grid">
{% for m in metrics %}
<div class="card"><div class="lbl">{{ m.label }}</div><div class="val {{ m.cls }}">{{ m.value }}</div></div>
{% endfor %}
</div>

{% if bm %}
<h2>ベンチマーク比較 ({{ bm.ticker }})</h2>
<div class="grid">
  <div class="card"><div class="lbl">Beta</div><div class="val">{{ '%.2f'|format(bm.beta or 0) }}</div></div>
  <div class="card"><div class="lbl">Alpha (年率)</div>
    <div class="val {{ 'pos' if (bm.alpha or 0) > 0 else 'neg' }}">{{ '%.1f%%'|format((bm.alpha or 0)*100) }}</div></div>
</div>
{% endif %}

{% if top_corr %}
<h2>相関上位銘柄 (テーマ内)</h2>
<table><thead><tr><th>Ticker</th><th>相関係数</th></tr></thead><tbody>
{% for r in top_corr %}<tr><td>{{ r.ticker }}</td><td>{{ '%.3f'|format(r.correlation) }}</td></tr>{% endfor %}
</tbody></table>
{% endif %}

{% if scores %}
<h2>スコア内訳</h2>
<table><thead><tr><th>コンポーネント</th><th>スコア (0–1)</th></tr></thead><tbody>
{% for s in scores %}<tr><td>{{ s.label }}</td><td>{{ '%.4f'|format(s.value or 0) }}</td></tr>{% endfor %}
</tbody></table>
{% endif %}

{% if fund %}
<hr class="hr-dim">
<h2>ファンダメンタル分析</h2>
<div class="fund-header">
  <div class="fund-kv"><div class="k">基準期</div><div class="v">{{ fund.fiscal_year }}</div></div>
  <div class="fund-kv"><div class="k">時価総額</div><div class="v">{{ fund.market_cap_fmt }}</div></div>
  <div class="fund-kv"><div class="k">EV</div><div class="v">{{ fund.ev_fmt }}</div></div>
  <div class="fund-kv"><div class="k">純有利子負債</div><div class="v {{ fund.net_debt_cls }}">{{ fund.net_debt_fmt }}</div></div>
  <div class="fund-kv"><div class="k">発行株数(概算)</div><div class="v">{{ fund.shares_fmt }}</div></div>
  <div class="fund-kv"><div class="k">データ期間</div><div class="v">{{ fund.n_periods }}期</div></div>
</div>

<h3>バリュエーション</h3>
<div class="grid">
  <div class="card"><div class="lbl">PER</div><div class="val {{ fund.per_cls }}">{{ fund.per_fmt }}</div></div>
  <div class="card"><div class="lbl">PBR</div><div class="val {{ fund.pbr_cls }}">{{ fund.pbr_fmt }}</div></div>
  <div class="card"><div class="lbl">PSR</div><div class="val">{{ fund.psr_fmt }}</div></div>
  <div class="card"><div class="lbl">P/FCF</div><div class="val">{{ fund.p_fcf_fmt }}</div></div>
  <div class="card"><div class="lbl">EV/EBIT</div><div class="val">{{ fund.ev_ebit_fmt }}</div></div>
  <div class="card"><div class="lbl">EV/売上</div><div class="val">{{ fund.ev_rev_fmt }}</div></div>
  <div class="card"><div class="lbl">PEG</div><div class="val {{ fund.peg_cls }}">{{ fund.peg_fmt }}</div></div>
  <div class="card"><div class="lbl">配当利回り</div><div class="val pos">{{ fund.div_yield_fmt }}</div></div>
  <div class="card"><div class="lbl">配当性向</div><div class="val">{{ fund.payout_fmt }}</div></div>
</div>
<p class="section-note">EPS&lt;0のとき PER/PEG は「赤字」 | FCF≤0のとき P/FCF は「—」 | EV/EBITはEV÷営業利益（D&A除く近似値）</p>

<h3>成長性</h3>
<div class="grid">
  <div class="card"><div class="lbl">売上成長 1Y</div><div class="val {{ fund.rev_g1_cls }}">{{ fund.rev_g1_fmt }}</div></div>
  <div class="card"><div class="lbl">売上 CAGR 3Y</div><div class="val {{ fund.rev_c3_cls }}">{{ fund.rev_c3_fmt }}</div></div>
  <div class="card"><div class="lbl">売上 CAGR 5Y</div><div class="val {{ fund.rev_c5_cls }}">{{ fund.rev_c5_fmt }}</div></div>
  <div class="card"><div class="lbl">EPS成長 1Y</div><div class="val {{ fund.eps_g1_cls }}">{{ fund.eps_g1_fmt }}</div></div>
  <div class="card"><div class="lbl">EPS CAGR 3Y</div><div class="val {{ fund.eps_c3_cls }}">{{ fund.eps_c3_fmt }}</div></div>
  <div class="card"><div class="lbl">営業利益成長 1Y</div><div class="val {{ fund.op_g1_cls }}">{{ fund.op_g1_fmt }}</div></div>
  <div class="card"><div class="lbl">純利益成長 1Y</div><div class="val {{ fund.ni_g1_cls }}">{{ fund.ni_g1_fmt }}</div></div>
</div>

<h3>収益性</h3>
<div class="grid">
  <div class="card"><div class="lbl">ROE</div><div class="val {{ fund.roe_cls }}">{{ fund.roe_fmt }}</div></div>
  <div class="card"><div class="lbl">ROA</div><div class="val {{ fund.roa_cls }}">{{ fund.roa_fmt }}</div></div>
  <div class="card"><div class="lbl">営業利益率</div><div class="val {{ fund.op_margin_cls }}">{{ fund.op_margin_fmt }}</div></div>
  <div class="card"><div class="lbl">純利益率</div><div class="val {{ fund.net_margin_cls }}">{{ fund.net_margin_fmt }}</div></div>
  <div class="card"><div class="lbl">営業CF率</div><div class="val {{ fund.ocf_margin_cls }}">{{ fund.ocf_margin_fmt }}</div></div>
  <div class="card"><div class="lbl">FCF率</div><div class="val {{ fund.fcf_margin_cls }}">{{ fund.fcf_margin_fmt }}</div></div>
</div>
<p class="section-note">ROE &gt;15%: 優良 / 8–15%: 平均 / &lt;8%: 低 | 営業利益率 &gt;15%: 高収益</p>

<h3>財務健全性</h3>
<div class="grid">
  <div class="card"><div class="lbl">自己資本比率</div><div class="val {{ fund.eq_ratio_cls }}">{{ fund.eq_ratio_fmt }}</div></div>
  <div class="card"><div class="lbl">D/E レシオ</div><div class="val {{ fund.de_cls }}">{{ fund.de_fmt }}</div></div>
  <div class="card"><div class="lbl">FCF 変換率</div><div class="val">{{ fund.fcf_conv_fmt }}</div></div>
  <div class="card"><div class="lbl">設備投資率</div><div class="val">{{ fund.capex_fmt }}</div></div>
  <div class="card"><div class="lbl">有利子負債</div><div class="val">{{ fund.ibd_fmt }}</div></div>
  <div class="card"><div class="lbl">現金等</div><div class="val">{{ fund.cash_fmt }}</div></div>
</div>
<p class="section-note">自己資本比率 &gt;50%: 強固 / 30–50%: 標準 / &lt;30%: 注意 | D/E &lt;0.5: 低レバレッジ</p>

<h3>最新期 財務サマリー</h3>
<table><thead><tr><th>項目</th><th>金額</th></tr></thead><tbody>
  <tr><td>売上高</td><td>{{ fund.revenue_fmt }}</td></tr>
  <tr><td>営業利益</td><td>{{ fund.op_profit_fmt }}</td></tr>
  {% if fund.ord_profit_fmt %}<tr><td>経常利益</td><td>{{ fund.ord_profit_fmt }}</td></tr>{% endif %}
  <tr><td>純利益(推計)</td><td>{{ fund.net_income_fmt }}</td></tr>
  <tr><td>営業キャッシュフロー</td><td>{{ fund.op_cf_fmt }}</td></tr>
  <tr><td>フリーキャッシュフロー</td><td>{{ fund.free_cf_fmt }}</td></tr>
  <tr><td>EPS</td><td>{{ fund.eps_fmt }} {{ fund.per_share_unit }}</td></tr>
  <tr><td>BPS</td><td>{{ fund.bps_fmt }} {{ fund.per_share_unit }}</td></tr>
  {% if fund.dps_val %}<tr><td>DPS</td><td>{{ fund.dps_val }} {{ fund.per_share_unit }}</td></tr>{% endif %}
</tbody></table>

<h3>財務推移チャート</h3>
<div class="chart">{{ fund.revenue_chart }}</div>
{{ fund.revenue_table }}
<div class="chart">{{ fund.roe_chart }}</div>
{{ fund.roe_table }}
<div class="chart">{{ fund.cf_chart }}</div>
{{ fund.cf_table }}
<div class="chart">{{ fund.eps_chart }}</div>
{{ fund.eps_table }}
{% endif %}

<div class="disc"><strong>免責事項:</strong> 本レポートは分析・教育目的のみです。投資助言ではありません。
価格データ: Yahoo Finance / yfinance。財務データ: IRBank (JP株) / yfinance (US株)。作成日: {{ date }}。</div>
</div></body></html>"""

# Local aliases kept for backward compatibility within this file
_pct = pct
_f = fmt
_cls = signed_cls

_BG      = "#1e293b"
_BG_PLOT = "#0f172a"


# ── price / volume charts ─────────────────────────────────────────────────────

def _price_chart(dates, prices, ticker) -> str:
    if not dates:
        return "<p>No data.</p>"
    fig = go.Figure(go.Scatter(x=dates, y=prices, name=ticker, line=dict(color="#3b82f6", width=2)))
    fig.update_layout(template="plotly_dark", height=380, paper_bgcolor=_BG, plot_bgcolor=_BG_PLOT,
                      title=f"{ticker} — 終値")
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


def _vol_chart(dates, volumes, traded_values, ticker) -> str:
    if not dates:
        return "<p>No data.</p>"
    fig = make_subplots(rows=2, cols=1, subplot_titles=["出来高", "売買代金"], vertical_spacing=0.14)
    if volumes:
        fig.add_trace(go.Bar(x=dates, y=volumes, name="Volume", marker_color="#6366f1"), row=1, col=1)
    if traded_values:
        fig.add_trace(go.Bar(x=dates, y=traded_values, name="Traded Value", marker_color="#8b5cf6"), row=2, col=1)
    fig.update_layout(template="plotly_dark", height=460, paper_bgcolor=_BG, plot_bgcolor=_BG_PLOT, showlegend=False)
    return pio.to_html(fig, include_plotlyjs="cdn", full_html=False)


# ── fundamental charts (reuse existing plotlyjs from price chart) ─────────────

def _scale_money(vals: list, currency: str) -> tuple[list, str]:
    """Scale raw monetary values to chart-friendly units. Returns (scaled_list, unit_label)."""
    if currency == "USD":
        divisor, unit = 1e9, "B USD"
    else:
        divisor, unit = 1e8, "億円"
    return [x / divisor if x is not None else None for x in vals], unit


def _revenue_chart(history: dict, currency: str = "JPY") -> str:
    fy   = history.get("fiscal_years", [])
    rev_raw = history.get("revenue", [])
    op_raw  = history.get("operating_profit", [])
    marg    = history.get("operating_margin", [])

    if not fy:
        return "<p>データなし</p>"

    rev, unit = _scale_money(rev_raw, currency)
    op,  _    = _scale_money(op_raw,  currency)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=fy, y=rev, name=f"売上高({unit})", marker_color="#3b82f6", opacity=0.85),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(x=fy, y=op, name=f"営業利益({unit})", marker_color="#10b981", opacity=0.85),
        secondary_y=False,
    )
    if any(v is not None for v in marg):
        fig.add_trace(
            go.Scatter(x=fy, y=marg, name="営業利益率(%)",
                       line=dict(color="#fbbf24", width=2), mode="lines+markers"),
            secondary_y=True,
        )
    fig.update_layout(
        template="plotly_dark", height=380, paper_bgcolor=_BG, plot_bgcolor=_BG_PLOT,
        title="売上高・営業利益推移", barmode="group",
        legend=dict(orientation="h", y=-0.22),
    )
    fig.update_yaxes(title_text=f"金額({unit})", secondary_y=False)
    fig.update_yaxes(title_text="利益率(%)", secondary_y=True)
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def _roe_roa_chart(history: dict) -> str:
    fy  = history.get("fiscal_years", [])
    roe = history.get("roe", [])
    roa = history.get("roa", [])
    eq  = history.get("equity_ratio", [])

    if not fy:
        return "<p>データなし</p>"

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if any(v is not None for v in roe):
        fig.add_trace(
            go.Scatter(x=fy, y=roe, name="ROE(%)", line=dict(color="#f472b6", width=2), mode="lines+markers"),
            secondary_y=False,
        )
    if any(v is not None for v in roa):
        fig.add_trace(
            go.Scatter(x=fy, y=roa, name="ROA(%)", line=dict(color="#a78bfa", width=2), mode="lines+markers"),
            secondary_y=False,
        )
    if any(v is not None for v in eq):
        fig.add_trace(
            go.Scatter(x=fy, y=eq, name="自己資本比率(%)",
                       line=dict(color="#34d399", width=2, dash="dot"), mode="lines+markers"),
            secondary_y=True,
        )
    fig.update_layout(
        template="plotly_dark", height=340, paper_bgcolor=_BG, plot_bgcolor=_BG_PLOT,
        title="ROE / ROA / 自己資本比率推移",
        legend=dict(orientation="h", y=-0.28),
    )
    fig.update_yaxes(title_text="ROE / ROA (%)", secondary_y=False)
    fig.update_yaxes(title_text="自己資本比率(%)", secondary_y=True)
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def _cf_chart(history: dict, currency: str = "JPY") -> str:
    fy    = history.get("fiscal_years", [])
    op_cf_raw = history.get("operating_cf", [])
    fcf_raw   = history.get("free_cf", [])
    debt_raw  = history.get("interest_bearing_debt", [])
    cash_raw  = history.get("cash", [])

    if not fy:
        return "<p>データなし</p>"

    op_cf, unit = _scale_money(op_cf_raw, currency)
    fcf,   _    = _scale_money(fcf_raw,   currency)
    debt,  _    = _scale_money(debt_raw,  currency)
    cash,  _    = _scale_money(cash_raw,  currency)

    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=[f"キャッシュフロー({unit})", f"有利子負債 vs 現金({unit})"],
        vertical_spacing=0.18,
    )
    if any(v is not None for v in op_cf):
        fig.add_trace(go.Bar(x=fy, y=op_cf, name="営業CF", marker_color="#3b82f6", opacity=0.85), row=1, col=1)
    if any(v is not None for v in fcf):
        fig.add_trace(go.Bar(x=fy, y=fcf, name="FCF", marker_color="#10b981", opacity=0.85), row=1, col=1)
    if any(v is not None for v in debt):
        fig.add_trace(go.Bar(x=fy, y=debt, name="有利子負債", marker_color="#f87171", opacity=0.85), row=2, col=1)
    if any(v is not None for v in cash):
        fig.add_trace(go.Bar(x=fy, y=cash, name="現金等", marker_color="#34d399", opacity=0.85), row=2, col=1)
    fig.update_layout(
        template="plotly_dark", height=540, paper_bgcolor=_BG, plot_bgcolor=_BG_PLOT,
        title="キャッシュフロー・財務状況推移", barmode="group",
        legend=dict(orientation="h", y=-0.12),
    )
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


def _eps_bps_chart(history: dict, currency: str = "JPY") -> str:
    fy  = history.get("fiscal_years", [])
    eps = history.get("eps", [])
    bps = history.get("bps", [])
    dps = history.get("dps", [])

    if not fy:
        return "<p>データなし</p>"

    unit = "円/株" if currency == "JPY" else "USD/share"
    fig = go.Figure()
    if any(v is not None for v in eps):
        fig.add_trace(go.Bar(x=fy, y=eps, name=f"EPS({unit})", marker_color="#fbbf24", opacity=0.85))
    if any(v is not None for v in bps):
        fig.add_trace(go.Scatter(x=fy, y=bps, name=f"BPS({unit})",
                                 line=dict(color="#93c5fd", width=2), mode="lines+markers"))
    if any(v is not None for v in dps):
        fig.add_trace(go.Bar(x=fy, y=dps, name=f"DPS({unit})", marker_color="#a78bfa", opacity=0.7))
    fig.update_layout(
        template="plotly_dark", height=320, paper_bgcolor=_BG, plot_bgcolor=_BG_PLOT,
        title=f"EPS / BPS / DPS 推移 ({unit})", barmode="group",
        legend=dict(orientation="h", y=-0.28),
    )
    return pio.to_html(fig, include_plotlyjs=False, full_html=False)


# ── history table helper ─────────────────────────────────────────────────────

def _hist_table(history: dict, col_defs: list, caption: str = "") -> str:
    """Render a time-series HTML table from a history dict (oldest→newest).

    col_defs: list of (key, header_label, format_fn)
    format_fn receives a raw value (float | None) and returns a display string.
    """
    years = history.get("fiscal_years", [])
    if not years:
        return ""

    th = "".join(f"<th>{lbl}</th>" for _, lbl, _ in col_defs)
    rows_html = ""
    for i, yr in enumerate(years):
        cells = f"<td style='color:#94a3b8;white-space:nowrap'>{yr}</td>"
        for key, _, fmt_fn in col_defs:
            vals = history.get(key, [])
            raw = vals[i] if i < len(vals) else None
            cells += f"<td>{fmt_fn(raw)}</td>"
        rows_html += f"<tr>{cells}</tr>"

    cap = f"<p style='font-size:.76em;color:#64748b;margin:4px 0 2px'>{caption}</p>" if caption else ""
    return (
        cap
        + "<div style='overflow-x:auto'>"
        + "<table style='font-size:.78em;margin:6px 0 18px'>"
        + f"<thead><tr><th>期</th>{th}</tr></thead>"
        + f"<tbody>{rows_html}</tbody>"
        + "</table></div>"
    )


def _build_revenue_table(history: dict, currency: str) -> str:
    _fmt_m = fmt_jpy if currency == "JPY" else fmt_usd
    unit = "億円" if currency == "JPY" else "B USD"

    def _pct(v):
        return pct_already(v) if _v(v) else "—"

    def _mon(v):
        return _fmt_m(v) if _v(v) else "—"

    cols = [
        ("revenue",          f"売上高({unit})",   _mon),
        ("operating_profit", f"営業利益({unit})",  _mon),
        ("net_income",       f"純利益({unit})",    _mon),
        ("operating_margin", "営業利益率",         _pct),
    ]
    if currency == "JPY":
        cols.insert(2, ("ordinary_profit", f"経常利益({unit})", _mon))

    return _hist_table(history, cols)


def _build_roe_table(history: dict) -> str:
    def _pct(v):
        return pct_already(v) if _v(v) else "—"

    return _hist_table(history, [
        ("roe",          "ROE %",       _pct),
        ("roa",          "ROA %",       _pct),
        ("equity_ratio", "自己資本比率 %", _pct),
    ])


def _build_cf_table(history: dict, currency: str) -> str:
    _fmt_m = fmt_jpy if currency == "JPY" else fmt_usd
    unit = "億円" if currency == "JPY" else "B USD"

    def _mon(v):
        return _fmt_m(v) if _v(v) else "—"

    return _hist_table(history, [
        ("operating_cf",        f"営業CF({unit})",   _mon),
        ("free_cf",             f"FCF({unit})",       _mon),
        ("interest_bearing_debt", f"有利子負債({unit})", _mon),
        ("cash",                f"現金等({unit})",    _mon),
    ])


def _build_eps_table(history: dict, per_share_unit: str) -> str:
    def _ps(v):
        if v is None or not _v(v):
            return "—"
        return f"{v:.2f}" if per_share_unit != "円/株" else (f"{v:.0f}" if abs(v) >= 10 else f"{v:.2f}")

    cols = [
        ("eps", f"EPS ({per_share_unit})", _ps),
        ("bps", f"BPS ({per_share_unit})", _ps),
    ]
    if any(v is not None for v in history.get("dps", [])):
        cols.append(("dps", f"DPS ({per_share_unit})", _ps))

    return _hist_table(history, cols)


# ── valuation classification helpers ─────────────────────────────────────────

def _v(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def _per_cls(v) -> str:
    if not _v(v) or v < 0:
        return "neg"
    return "pos" if v <= 15 else "neutral" if v <= 30 else "neg"


def _pbr_cls(v) -> str:
    if not _v(v) or v < 0:
        return "neg"
    return "pos" if v <= 1.5 else "neutral" if v <= 3 else "neg"


def _peg_cls(v) -> str:
    if not _v(v) or v < 0:
        return ""
    return "pos" if v < 1 else "neutral" if v <= 2 else "neg"


def _roe_cls(v) -> str:
    if not _v(v):
        return ""
    return "pos" if v >= 15 else "neutral" if v >= 8 else "neg"


def _roa_cls(v) -> str:
    if not _v(v):
        return ""
    return "pos" if v >= 8 else "neutral" if v >= 3 else "neg"


def _margin_cls(v) -> str:
    if not _v(v):
        return ""
    return "pos" if v > 0 else "neg"


def _eq_ratio_cls(v) -> str:
    if not _v(v):
        return ""
    return "pos" if v >= 50 else "neutral" if v >= 30 else "neg"


def _de_cls(v) -> str:
    if not _v(v) or v < 0:
        return ""
    return "pos" if v <= 0.5 else "neutral" if v <= 2 else "neg"


def _growth_cls(v) -> str:
    if not _v(v):
        return ""
    return "pos" if v > 10 else "neutral" if v > 0 else "neg"


def _net_debt_cls(v) -> str:
    if not _v(v):
        return ""
    return "neg" if v > 0 else "pos"


# ── template data preparation ─────────────────────────────────────────────────

def _prep_fund(fm: dict) -> dict | None:
    if not fm:
        return None

    currency = fm.get("currency", "JPY")
    _fmt_money = fmt_jpy if currency == "JPY" else fmt_usd
    per_share_unit = "円/株" if currency == "JPY" else "USD/share"

    def _get(key):
        return fm.get(key)

    history = fm.get("history", {})

    eps_raw = _get("eps")
    bps_raw = _get("bps")
    dps_raw = _get("dps")

    def _coin(v):
        if v is None or not _v(v):
            return "—"
        if currency == "USD":
            return f"{v:.2f}"
        return f"{v:.0f}" if abs(v) >= 10 else f"{v:.2f}"

    def _loss_or_x(v):
        if v is None or not _v(v):
            return "—"
        return "赤字" if v < 0 else fmt_x(v)

    per_v     = _get("per")
    pbr_v     = _get("pbr")
    peg_v     = _get("peg")
    net_debt_v = _get("net_debt")
    shares_v  = _get("shares_outstanding")

    rev_g1_v = _get("revenue_growth_1y")
    rev_c3_v = _get("revenue_cagr_3y")
    rev_c5_v = _get("revenue_cagr_5y")
    eps_g1_v = _get("eps_growth_1y")
    eps_c3_v = _get("eps_cagr_3y")
    op_g1_v  = _get("op_profit_growth_1y")
    ni_g1_v  = _get("net_income_growth_1y")

    roe_v       = _get("roe")
    roa_v       = _get("roa")
    op_margin_v = _get("operating_margin")
    net_marg_v  = _get("net_margin")
    ocf_marg_v  = _get("operating_cf_margin")
    fcf_marg_v  = _get("fcf_margin")

    eq_ratio_v = _get("equity_ratio")
    de_v       = _get("de_ratio")

    shares_fmt = (
        f"{shares_v / 1e6:.1f}百万株" if (_v(shares_v) and currency == "JPY")
        else f"{shares_v / 1e6:.1f}M shares" if _v(shares_v)
        else "—"
    )

    return {
        "fiscal_year":    fm.get("fiscal_year", ""),
        "n_periods":      fm.get("n_periods", 0),
        "currency":       currency,
        "per_share_unit": per_share_unit,
        "market_cap_fmt": _fmt_money(_get("market_cap")),
        "ev_fmt":         _fmt_money(_get("ev")),
        "net_debt_fmt":   _fmt_money(net_debt_v),
        "net_debt_cls":   _net_debt_cls(net_debt_v),
        "shares_fmt":     shares_fmt,
        # Valuation
        "per_fmt":     _loss_or_x(per_v),
        "per_cls":     _per_cls(per_v),
        "pbr_fmt":     fmt_x(pbr_v) if _v(pbr_v) and pbr_v > 0 else "—",
        "pbr_cls":     _pbr_cls(pbr_v),
        "psr_fmt":     fmt_x(_get("psr")),
        "p_fcf_fmt":   fmt_x(_get("p_fcf")),
        "ev_ebit_fmt": _loss_or_x(_get("ev_ebit")),
        "ev_rev_fmt":  fmt_x(_get("ev_rev")),
        "peg_fmt":     fmt_x(peg_v, digits=2) if _v(peg_v) and peg_v > 0 else "—",
        "peg_cls":     _peg_cls(peg_v),
        "div_yield_fmt": pct_already(_get("dividend_yield"), digits=2) if _v(_get("dividend_yield")) else "—",
        "payout_fmt":    pct_already(_get("payout_ratio"), digits=1)   if _v(_get("payout_ratio"))   else "—",
        # Growth
        "rev_g1_fmt": pct_signed(rev_g1_v), "rev_g1_cls": _growth_cls(rev_g1_v),
        "rev_c3_fmt": pct_signed(rev_c3_v), "rev_c3_cls": _growth_cls(rev_c3_v),
        "rev_c5_fmt": pct_signed(rev_c5_v), "rev_c5_cls": _growth_cls(rev_c5_v),
        "eps_g1_fmt": pct_signed(eps_g1_v), "eps_g1_cls": _growth_cls(eps_g1_v),
        "eps_c3_fmt": pct_signed(eps_c3_v), "eps_c3_cls": _growth_cls(eps_c3_v),
        "op_g1_fmt":  pct_signed(op_g1_v),  "op_g1_cls":  _growth_cls(op_g1_v),
        "ni_g1_fmt":  pct_signed(ni_g1_v),  "ni_g1_cls":  _growth_cls(ni_g1_v),
        # Profitability
        "roe_fmt":        pct_already(roe_v),        "roe_cls":        _roe_cls(roe_v),
        "roa_fmt":        pct_already(roa_v),        "roa_cls":        _roa_cls(roa_v),
        "op_margin_fmt":  pct_already(op_margin_v),  "op_margin_cls":  _margin_cls(op_margin_v),
        "net_margin_fmt": pct_already(net_marg_v),   "net_margin_cls": _margin_cls(net_marg_v),
        "ocf_margin_fmt": pct_already(ocf_marg_v),   "ocf_margin_cls": _margin_cls(ocf_marg_v),
        "fcf_margin_fmt": pct_already(fcf_marg_v),   "fcf_margin_cls": _margin_cls(fcf_marg_v),
        # Quality
        "eq_ratio_fmt": pct_already(eq_ratio_v), "eq_ratio_cls": _eq_ratio_cls(eq_ratio_v),
        "de_fmt":       fmt_x(de_v, digits=2) if _v(de_v) else "—", "de_cls": _de_cls(de_v),
        "fcf_conv_fmt": fmt_x(_get("fcf_conversion"), digits=2) if _v(_get("fcf_conversion")) else "—",
        "capex_fmt":    pct_already(_get("capex_ratio"), digits=1) if _v(_get("capex_ratio")) else "—",
        "ibd_fmt":      _fmt_money(_get("interest_bearing_debt")),
        "cash_fmt":     _fmt_money(_get("cash")),
        # Absolute summary
        "revenue_fmt":    _fmt_money(_get("revenue")),
        "op_profit_fmt":  _fmt_money(_get("operating_profit")),
        "ord_profit_fmt": _fmt_money(_get("ordinary_profit")) if currency == "JPY" else None,
        "net_income_fmt": _fmt_money(_get("net_income")),
        "op_cf_fmt":      _fmt_money(_get("operating_cf")),
        "free_cf_fmt":    _fmt_money(_get("free_cf")),
        "eps_fmt":        _coin(eps_raw),
        "bps_fmt":        _coin(bps_raw),
        "dps_val":        f"{dps_raw:.2f}" if (_v(dps_raw) and dps_raw > 0) else None,
        # Charts
        "revenue_chart": _revenue_chart(history, currency),
        "roe_chart":     _roe_roa_chart(history),
        "cf_chart":      _cf_chart(history, currency),
        "eps_chart":     _eps_bps_chart(history, currency),
        # History tables
        "revenue_table": _build_revenue_table(history, currency),
        "roe_table":     _build_roe_table(history),
        "cf_table":      _build_cf_table(history, currency),
        "eps_table":     _build_eps_table(history, per_share_unit),
    }


# ── public entrypoint ─────────────────────────────────────────────────────────

def generate_stock_html_report(analysis_result: dict, output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    data = build_stock_report_data(analysis_result)

    ticker = data.get("ticker", "")
    m = data.get("metrics_dict", {})
    dq = data.get("data_quality", {})
    flag = dq.get("data_quality_flag", "UNKNOWN")
    quality_class_map = {
        "OK": "OK",
        "LIMITED_HISTORY": "LIMITED_HISTORY",
        "VERY_SHORT_HISTORY": "VERY_SHORT_HISTORY",
    }

    def metric(label, value, cls=""):
        return {"label": label, "value": value, "cls": cls}

    key_metrics = [
        metric("リターン 1M",    _pct(m.get("return_1m")),   _cls(m.get("return_1m"))),
        metric("リターン 3M",    _pct(m.get("return_3m")),   _cls(m.get("return_3m"))),
        metric("リターン 6M",    _pct(m.get("return_6m")),   _cls(m.get("return_6m"))),
        metric("リターン 12M",   _pct(m.get("return_12m")),  _cls(m.get("return_12m"))),
        metric("年率ボラティリティ", _pct(m.get("annualized_volatility"))),
        metric("最大DD 12M",    _pct(m.get("max_drawdown_12m"))),
        metric("Sharpe 6M",    _f(m.get("sharpe_6m"))),
        metric("Sharpe 12M",   _f(m.get("sharpe_12m"))),
        metric("Sortino 12M",  _f(m.get("sortino_12m"))),
        metric("Calmar 12M",   _f(m.get("calmar_12m"))),
        metric("52W高値比",    _pct(m.get("distance_from_52w_high")), _cls(m.get("distance_from_52w_high"))),
        metric("52W安値比",    _pct(m.get("distance_from_52w_low")),  _cls(m.get("distance_from_52w_low"))),
        metric("MA50比",      _pct(m.get("distance_from_ma_50")),    _cls(m.get("distance_from_ma_50"))),
        metric("MA200比",     _pct(m.get("distance_from_ma_200")),   _cls(m.get("distance_from_ma_200"))),
        metric("平均売買代金 3M",
               f"{m.get('avg_traded_value_3m', 0):,.0f}" if m.get("avg_traded_value_3m") else "N/A"),
    ]

    rr = data.get("ranking_row", pd.Series(dtype=float))
    score_labels = [
        ("Final Score",     "final_score"),
        ("Momentum",        "momentum_score"),
        ("Risk-Adj Return", "risk_adjusted_return_score"),
        ("Liquidity",       "liquidity_score"),
        ("Volatility",      "volatility_score"),
        ("Drawdown",        "drawdown_score"),
        ("Theme Purity",    "theme_purity_score"),
    ]
    scores = []
    if hasattr(rr, "get"):
        for label, key in score_labels:
            v = rr.get(key)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                scores.append({"label": label, "value": float(v)})

    bm_raw = data.get("benchmark_metrics", {})
    bm = (
        {"ticker": bm_raw.get("benchmark_ticker", ""),
         "beta": bm_raw.get("beta"), "alpha": bm_raw.get("alpha")}
        if bm_raw else None
    )

    corr_df = data.get("top_correlated", pd.DataFrame())
    top_corr = corr_df.to_dict("records") if not corr_df.empty else []

    fund = _prep_fund(data.get("fundamental_metrics", {}))

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
        price_chart=_price_chart(
            data.get("chart_dates", []), data.get("chart_prices", []), ticker),
        vol_chart=_vol_chart(
            data.get("chart_dates", []), data.get("chart_volumes", []),
            data.get("chart_traded_values", []), ticker),
        metrics=key_metrics,
        bm=bm,
        top_corr=top_corr,
        scores=scores if scores else None,
        fund=fund,
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Stock report: {output_path}")
