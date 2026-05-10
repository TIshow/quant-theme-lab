# テーマ追加ガイド

## 概要

新しい投資テーマを追加するには、以下の2ファイルを編集・作成するだけです。
分析コードは変更不要です。

```
config/
  universe.yaml        ← 銘柄を追加（既存ファイルを編集）
  themes/
    <new_theme>.yaml   ← 新規作成
```

---

## Step 1: universe.yaml に銘柄を追加

`config/universe.yaml` を開き、`stocks:` リストに銘柄を追加します。

```yaml
stocks:
  # 既存の銘柄...

  # 新しいテーマの銘柄を追加
  - ticker: "6501.T"
    name: "Hitachi"
    country: "JP"
    sector: "industrials"
    themes:
      robotics: 4            # 新テーマ名と theme_purity（1〜5）
      ai_infrastructure: 3   # 複数テーマに属してもOK

  - ticker: "ISRG"
    name: "Intuitive Surgical"
    country: "US"
    sector: "healthcare"
    themes:
      robotics: 5
```

### theme_purity の設定基準

| 値 | 基準 |
|---|---|
| 5 | そのテーマが主要事業（売上の70%以上） |
| 4 | そのテーマが主力事業（売上の40〜70%） |
| 3 | テーマへの明確な露出（売上の20〜40%） |
| 2 | 間接的な露出や関連製品の一部 |
| 1 | 周辺的な関係（使わなくてもよい） |

### 既存銘柄への新テーマ追加

既存銘柄が新テーマにも関連する場合、`themes:` に追記するだけです:

```yaml
# 変更前
- ticker: "NVDA"
  themes:
    semiconductor: 5
    ai_infrastructure: 5

# 変更後（roboticsテーマを追加）
- ticker: "NVDA"
  themes:
    semiconductor: 5
    ai_infrastructure: 5
    robotics: 4              # 追記
```

---

## Step 2: themes/<new_theme>.yaml を作成

`config/themes/` に既存ファイルをコピーして編集します。

```bash
cp config/themes/battery_storage.yaml config/themes/robotics.yaml
```

`robotics.yaml` を編集:

```yaml
theme: robotics                          # universe.yaml の themes キーと一致させること
display_name: "Robotics / ロボティクス"
description: >
  Industrial robots, collaborative robots (cobots),
  medical robots, autonomous systems, and actuators.

benchmark:
  jp: "1306.T"
  us: "ROBO"           # テーマに合ったETFがあれば使う（なければSPYで可）

analysis:
  start_date: "2023-01-01"
  min_theme_purity: 2   # 2以上の銘柄のみ分析対象
  top_n_backtest: 5

weights:
  momentum: 0.25
  volatility: 0.10
  drawdown: 0.10
  liquidity: 0.10
  theme_purity: 0.20
  risk_adjusted_return: 0.25

momentum_weights:
  return_1m: 0.20
  return_3m: 0.50
  return_6m: 0.30

risk_adjusted_return_weights:
  sharpe_6m: 0.40
  sharpe_12m: 0.40
  calmar_12m: 0.20

backtest:
  transaction_cost_bps: 25   # 日本中型株 + 米国中型株 の混合
  execution_lag_days: 1
```

---

## Step 3: 実行

```bash
# テーマ内分析
pnpm run pipeline --theme robotics

# テーマ横断比較（全テーマ）
pnpm run universe

# 個別銘柄分析
pnpm run analyze --theme robotics --ticker 6501.T
```

---

## よくある問題

### `FileNotFoundError: Theme config not found`
→ `config/themes/<theme_name>.yaml` のファイル名と `--theme` 引数が一致しているか確認

### 銘柄データが取得できない
→ yfinance のティッカーシンボルを確認。日本株は `.T` サフィックスが必要（例: `6501.T`）

### `LIMITED_HISTORY` フラグが出る
→ 上場から日が浅い銘柄（120〜251営業日）。分析は実行されるが、
  一部指標（12M Sharpe 等）が NaN になる。レポートに警告が表示される。

### スコアの重みを変えたい
→ `config/themes/<theme>.yaml` の `weights:` を変更する。合計が 1.0 になるようにすること。
  `momentum_weights:` と `risk_adjusted_return_weights:` の合計も各々 1.0 にすること。
