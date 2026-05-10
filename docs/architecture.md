# Architecture

## システム全体図

```
┌─────────────────────────────────────────────────────┐
│                   Entry Points                       │
│                                                      │
│  run_universe.py    run_pipeline.py   analyze_stock.py│
│  （テーマ横断）    （テーマ内）      （個別銘柄）   │
└──────────┬──────────────┬───────────────┬────────────┘
           │              │               │
           ▼              ▼               ▼
┌──────────────────────────────────────────────────────┐
│                  Config Layer                         │
│  config/universe.yaml ←── 全銘柄マスター            │
│  config/themes/*.yaml  ←── テーマパラメータ         │
│  src/config/loader.py  ←── 読み込み・フィルタリング │
└──────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│                   Data Layer                          │
│  src/data/price_loader.py  ←── yfinance 価格取得    │
│  src/data/storage.py       ←── Parquet/CSV 保存     │
└──────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│                  Factor Layer                         │
│  returns.py   volatility.py   drawdown.py            │
│  liquidity.py   risk.py   moving_average.py          │
│  factor_table.py  ←── 全ファクターを統合             │
└──────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│                  Scoring Layer                        │
│  scorer.py   ←── rank_normalize + compute_scores    │
│  ranking.py  ←── final_score でランキング           │
└──────────────────────────────────────────────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
┌─────────┐  ┌──────────────────────────────────────┐
│Backtest │  │         Analytics Layer              │
│simple_  │  │  correlation.py   clustering.py      │
│backtest │  │  benchmark.py                        │
│walk_    │  │  factor_validation.py (IC/ICIR)      │
│forward  │  │  theme_comparison.py                 │
└────┬────┘  │  risk_model.py (Ledoit-Wolf)         │
     │       └──────────────────┬───────────────────┘
     │                          │
     └──────────┬───────────────┘
                ▼
┌──────────────────────────────────────────────────────┐
│                  Reports Layer                        │
│  theme_report.py    ←── Plotly + Jinja2 HTML        │
│  stock_report.py    ←── 個別銘柄 HTML               │
│  universe_report.py ←── テーマ横断 HTML             │
└──────────────────────────────────────────────────────┘
```

---

## データフロー詳細

### run_pipeline.py（Layer 2）

```
universe.yaml + themes/*.yaml
        │
        ├── 対象テーマ銘柄 + ベンチマークティッカー
        │
        ▼
yfinance.download() → prices DataFrame
  columns: Date, Ticker, Open, High, Low, Close, Adj_Close, Volume
        │
        ▼
build_factor_table(theme_prices)
  → returns × volatility × drawdown × liquidity × risk × moving_average
  → 1行 / 銘柄のファクターテーブル
        │
        ▼
compute_scores(factor_df, universe_df, weights, config)
  → rank_normalize() × 6スコア
  → final_score（加重平均）
        │
        ▼
rank_stocks() → ランキングDataFrame
        │
        ├── correlation_matrix()
        ├── compute_clusters()
        └── run_monthly_momentum_top_n_backtest()
                │
                ▼
        generate_theme_html_report()
        → data/reports/themes/<theme>_report.html
```

---

## ストレージ設計

```
data/
  raw/prices/              # 未使用（将来：生データキャッシュ）
  processed/
    prices/<theme>.parquet        # 日次OHLCV（全テーマ銘柄+ベンチマーク）
    factors/<theme>_factors.parquet  # 銘柄×ファクター値
    rankings/<theme>_ranking.csv     # スコア・ランキング
    correlations/<theme>_correlation.csv
    clusters/<theme>_clusters.csv
    backtests/<theme>_backtest.csv
    validation/                   # IC/ICIR検証結果（run時に生成）
    theme_comparison/             # テーマ横断比較データ
  reports/
    themes/<theme>_report.html
    stocks/<theme>_<ticker>_report.html
    universe/theme_comparison_report.html
```

**processed/ と reports/ は .gitignore 対象。**  
再現性はコードと設定ファイルで担保する。

---

## 依存関係グラフ（主要モジュール）

```
config/loader.py
  └── (no src deps)

data/price_loader.py
  └── utils/logger.py

factors/factor_table.py
  ├── factors/returns.py
  ├── factors/volatility.py
  ├── factors/drawdown.py
  ├── factors/liquidity.py
  ├── factors/risk.py
  └── factors/moving_average.py

scoring/scorer.py
  └── (no src deps, uses scipy.stats)

analytics/factor_validation.py
  └── factors/factor_table.py

stock/stock_analyzer.py
  ├── config/loader.py
  ├── data/price_loader.py
  ├── factors/factor_table.py
  ├── scoring/scorer.py
  ├── scoring/ranking.py
  ├── analytics/correlation.py
  └── analytics/benchmark.py
```

---

## 技術スタック

| 用途 | ライブラリ |
|---|---|
| データ取得 | yfinance |
| データ処理 | pandas, numpy |
| 統計・最適化 | scipy, scikit-learn |
| 可視化 | plotly |
| レポート | jinja2 |
| ストレージ | pyarrow（Parquet）, duckdb |
| テスト | pytest |
| コード整形 | prettier（HTMLレポート用） |
| バージョン管理 | asdf, pnpm |
