# CLAUDE.md — Quant Theme Lab

## ⚠️ 絶対条件（違反禁止）

- **Python の実行は必ず `pnpm run` 経由**。`python`・`pip`・`pytest` を直接叩くことは一切禁止。
- **Python パッケージ管理は `uv`**。`pip install` は使わない。
- **Python バージョン管理は `asdf`**。`pyenv`・`brew install python` 等は使わない。
- パッケージ追加は `pyproject.toml` の `dependencies` に書いて `pnpm run setup`（= `uv sync`）で反映。
- `requirements.txt` は存在しない。`pyproject.toml` が唯一の依存定義ファイル。

```
# ✅ 正しい
pnpm run setup                          # uv sync
pnpm run pipeline --theme battery_storage
pnpm run test                           # uv run pytest

# ❌ 絶対にやらない
pip install xxx
uv pip install xxx   （uv sync を使う）
python run_pipeline.py
pytest tests/
```

## プロジェクト概要

蓄電池・半導体・防衛・AIインフラなど複数の投資テーマを対象とした
クオンタメンタル分析プラットフォーム。取引ツールではなく **分析ツール**。

## 必須コマンド（すべて pnpm 経由）

```bash
pnpm install          # JS依存インストール（prettier）
pnpm run setup        # Python依存インストール（uv sync）
pnpm run test         # 全テスト実行（uv run pytest tests/ -v）

pnpm run universe                                           # Layer1: テーマ横断比較
pnpm run pipeline --theme battery_storage               # Layer2: テーマ内分析
pnpm run analyze --theme battery_storage --ticker 485A.T # Layer3: 個別銘柄（テーマ内）
pnpm run analyze --ticker TSLA                          # Layer3: 個別銘柄（スタンドアロン）
```

## 3層アーキテクチャ

```
Layer 1: run_universe.py     「今どのテーマが強いか」 → テーマ横断比較レポート
Layer 2: run_pipeline.py     「そのテーマで何を買うか」 → テーマ内ランキング・バックテスト
Layer 3: analyze_stock.py    「その銘柄を深掘りする」 → 個別銘柄レポート
```

## 重要な設計思想

**テーマ = レンズ（排他的バケツではない）**
- 1銘柄が複数テーマに属せる（例：NVDA は semiconductor + ai_infrastructure）
- `config/universe.yaml` が全銘柄のマスターレジストリ
- `config/themes/*.yaml` はパラメータのみ（ユニバース定義を持たない）

**スコアリング**: z-score ではなくランク正規化 + ウィンソライズ（5%/95%）を使用
→ `src/scoring/scorer.py:rank_normalize()`

**バックテスト**: 取引コスト（片道bps）+ 実行ラグ（1日）を必ず含める
→ `src/backtest/simple_backtest.py`

## ファイル構成

```
config/
  universe.yaml          # 全銘柄マスター（multi-theme membership）
  themes/                # テーマごとのパラメータYAML

src/
  config/loader.py       # YAML読み込み、テーマフィルタリング
  data/price_loader.py   # yfinance価格取得
  factors/               # 個別ファクター計算（returns, vol, drawdown, liquidity, risk, ma）
  factors/factor_table.py # ファクターを統合して1テーブルに
  scoring/scorer.py      # rank_normalize + compute_scores
  scoring/ranking.py     # final_score でランキング生成
  analytics/
    correlation.py       # 相関行列
    clustering.py        # 階層クラスタリング（距離=1-corr）
    benchmark.py         # beta / alpha 計算
    factor_validation.py # IC / ICIR / IC Decay（ファクター有効性検証）
    theme_comparison.py  # テーマ等金額ポートフォリオ比較
    risk_model.py        # Ledoit-Wolf 共分散（N>Tのサンプル問題対策）
  backtest/
    simple_backtest.py   # 月次モメンタム top-N バックテスト（コスト込み）
    walk_forward.py      # Walk-forward アウトオブサンプル検証
  stock/stock_analyzer.py # 個別銘柄分析（テーマ有無両対応）
  reports/               # Plotly + Jinja2 HTML レポート生成（3種）
```

## テーマ追加手順

1. `config/universe.yaml` に銘柄を追加（`themes:` に新テーマ名と purity を記載）
2. `config/themes/<new_theme>.yaml` を作成（既存テーマをコピーしてパラメータ変更）
3. `pnpm run pipeline --theme <new_theme>` で実行

## データ品質フラグ

| フラグ | 条件 |
|---|---|
| OK | 252営業日以上 |
| LIMITED_HISTORY | 120〜251営業日 |
| VERY_SHORT_HISTORY | 1〜119営業日 |
| NO_DATA | データなし |

## 出力ファイル（.gitignore 対象）

```
data/processed/prices/<theme>.parquet
data/processed/factors/<theme>_factors.parquet
data/processed/rankings/<theme>_ranking.csv
data/processed/correlations/<theme>_correlation.csv
data/processed/clusters/<theme>_clusters.csv
data/processed/backtests/<theme>_backtest.csv
data/reports/themes/<theme>_report.html
data/reports/stocks/<theme>_<ticker>_report.html
data/reports/universe/theme_comparison_report.html
```

## 将来フェーズ（未実装）

- Phase 2: 財務データ（ROE, FCF, EV/EBITDA 等）
- Phase 3: テーマ固有KPI（BESS受注MWh 等）
- Phase 4: ニュース・イベント分析
- Phase 5: 機械学習（IC-weighted, LightGBM, walk-forward）
