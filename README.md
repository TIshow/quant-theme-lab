# Quant Theme Lab

テーマ横断型クオンタメンタル分析プラットフォーム。

蓄電池・半導体・防衛・AIインフラなど複数の投資テーマについて、
**「どのテーマが強いか」→「そのテーマで何を買うか」→「個別銘柄の深掘り」**
という3層分析を、再利用可能な共通基盤の上で実行する。

---

## アーキテクチャ

```
Layer 1  run_universe.py    テーマ横断比較（今どのテーマが強いか）
Layer 2  run_pipeline.py    テーマ内分析（ランキング・バックテスト）
Layer 3  analyze_stock.py   個別銘柄深掘り（全テーマでの位置づけ）
```

### 設計思想

- **テーマ = レンズ**（排他的バケツではない）。1銘柄が複数テーマに属せる。
- **config/universe.yaml** が全銘柄のマスターレジストリ。
- **config/themes/*.yaml** はパラメータのみ（ユニバース定義を持たない）。
- スコアリングは **ランク正規化 + ウィンソライズ**（z-scoreより外れ値に頑健）。
- バックテストは **取引コスト（片道bps）+ 実行ラグ** を含む。

---

## インストール

```bash
# asdf でPythonバージョンを設定（.tool-versionsを参照）
asdf install

# 依存ライブラリをインストール
pip install -r requirements.txt

# pnpm（HTML整形ツール）
pnpm install
```

---

## 使い方

### Layer 1: テーマ横断比較

```bash
pnpm run universe
pnpm run universe --themes battery_storage semiconductor defense ai_infrastructure
```

出力: `data/reports/universe/theme_comparison_report.html`

### Layer 2: テーマ内分析

```bash
pnpm run pipeline --theme battery_storage
pnpm run pipeline --theme semiconductor
pnpm run pipeline --theme defense
pnpm run pipeline --theme ai_infrastructure
```

出力:
```
data/processed/prices/battery_storage.parquet
data/processed/factors/battery_storage_factors.parquet
data/processed/rankings/battery_storage_ranking.csv
data/processed/correlations/battery_storage_correlation.csv
data/processed/clusters/battery_storage_clusters.csv
data/processed/backtests/battery_storage_backtest.csv
data/reports/themes/battery_storage_report.html
```

### Layer 3: 個別銘柄分析

```bash
# テーマ内での位置づけ付き（ランキングでの相対位置も表示）
pnpm run analyze --theme battery_storage --ticker 485A.T
pnpm run analyze --theme semiconductor --ticker NVDA

# スタンドアロン（テーマ指定なし）
pnpm run analyze --ticker TSLA
```

出力:
```
data/reports/stocks/battery_storage_485A.T_report.html
data/reports/stocks/TSLA_report.html
```

### ファクター検証（IC / ICIR）

```python
from src.data.price_loader import download_price_data
from src.analytics.factor_validation import validate_all_factors

prices = download_price_data(["NVDA","TSLA","LMT"], start_date="2022-01-01")
result = validate_all_factors(prices)
print(result)
# factor  | mean_ic | icir  | usable
# --------|---------|-------|-------
# sharpe  |  0.18   | 0.45  | True
# return_3m| 0.12   | 0.31  | True
# ...
```

---

## テーマ追加方法

1. `config/universe.yaml` に銘柄を追加し、新テーマ名で `theme_purity` を設定する:

```yaml
- ticker: "6501.T"
  name: "Hitachi"
  country: "JP"
  sector: "industrials"
  themes:
    robotics: 4
    ai_infrastructure: 3
```

2. `config/themes/robotics.yaml` を作成（パラメータのみ）:

```yaml
theme: robotics
display_name: "Robotics / ロボティクス"
benchmark:
  jp: "1306.T"
  us: "ROBO"
analysis:
  start_date: "2023-01-01"
  min_theme_purity: 2
  top_n_backtest: 5
weights:
  momentum: 0.25
  volatility: 0.10
  drawdown: 0.10
  liquidity: 0.10
  theme_purity: 0.20
  risk_adjusted_return: 0.25
...
```

3. 実行:

```bash
python run_pipeline.py --theme robotics
```

---

## テスト

```bash
pytest tests/ -v
```

---

## v0.1 でできること

| 機能 | 状態 |
|---|---|
| テーマ横断比較（どのテーマが強いか） | ✅ |
| テーマ内ランキング（ランク正規化スコア） | ✅ |
| 相関行列・クラスタリング | ✅ |
| バックテスト（取引コスト・実行ラグ付き） | ✅ |
| Walk-forward 検証 | ✅ |
| ファクター検証（IC/ICIR） | ✅ |
| リスクモデル（Ledoit-Wolf 共分散） | ✅ |
| 個別銘柄分析（全テーマ位置づけ付き） | ✅ |
| HTMLレポート（3種） | ✅ |
| データ品質フラグ | ✅ |

---

## 今後の拡張予定

### Phase 2: 財務データ
売上成長率・営業利益率・ROE・ROIC・FCF・EV/EBITDA・PER・PBR

### Phase 3: テーマ固有KPI（蓄電池例）
BESS受注MWh・納入MWh・補助金採択件数・現金残高・希薄化リスク

### Phase 4: ニュース・イベント分析
決算・大型受注・補助金・増資・工場稼働・政策変更

### Phase 5: 機械学習
IC-weighted factor combination・LightGBM・Walk-forward validation・Feature importance

---

## データソース

- 価格データ: Yahoo Finance (yfinance)
- 設定: `config/universe.yaml`, `config/themes/*.yaml`

## 免責事項

本ツールは研究・教育目的のみです。投資助言ではありません。
過去のパフォーマンスは将来の結果を保証しません。
