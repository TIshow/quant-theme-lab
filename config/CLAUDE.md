# CLAUDE.md — config/

## ファイル構成

```
config/
  universe.yaml          # 全銘柄マスターレジストリ（変更頻度：低）
  themes/
    battery_storage.yaml # テーマパラメータ（変更頻度：中）
    semiconductor.yaml
    defense.yaml
    ai_infrastructure.yaml
```

## universe.yaml の構造

```yaml
stocks:
  - ticker: "NVDA"
    name: "NVIDIA"
    country: "US"          # JP or US
    sector: "technology"   # GICSセクター（小文字スネークケース）
    themes:
      semiconductor: 5     # theme_purity: 1（低）〜 5（高）
      ai_infrastructure: 5 # 複数テーマに属せる
```

### theme_purity の目安
| 値 | 意味 | 例 |
|---|---|---|
| 5 | テーマの純粋プレイ | FLNC（蓄電専業）、QS（全固体電池専業） |
| 4 | テーマへの高い露出 | 6674.T（GSユアサ：電池が主力） |
| 3 | テーマへの中程度の露出 | 6752.T（パナソニック：電池は一部） |
| 2 | テーマへの周辺的な露出 | - |
| 1 | テーマとの間接的関係 | - |

## themes/*.yaml の構造

テーマYAMLにはユニバース定義を書かない（universe.yaml が一元管理）。
パラメータのみを記載する。

```yaml
theme: battery_storage      # universe.yaml の themes キーと一致させること
display_name: "Battery Storage / 蓄電池"
description: >
  テーマの説明文

benchmark:
  jp: "1306.T"              # 日本株ベンチマーク
  us: "SPY"                 # 米国株ベンチマーク

analysis:
  start_date: "2023-01-01"  # データ取得開始日
  min_theme_purity: 2       # これ未満のpurityは分析対象外
  top_n_backtest: 5         # バックテストで保有する上位N銘柄

weights:                    # ファクタースコアの重み（合計=1.0）
  momentum: 0.25
  volatility: 0.10
  drawdown: 0.10
  liquidity: 0.10
  theme_purity: 0.20
  risk_adjusted_return: 0.25

momentum_weights:           # momentum_score 内の内訳（合計=1.0）
  return_1m: 0.20
  return_3m: 0.50
  return_6m: 0.30

risk_adjusted_return_weights:  # risk_adjusted_return_score 内の内訳（合計=1.0）
  sharpe_6m: 0.40
  sharpe_12m: 0.40
  calmar_12m: 0.20

backtest:
  transaction_cost_bps: 30  # 片道コスト（bps）。日本小型株は30〜50、米大型は10〜20が目安
  execution_lag_days: 1     # 月末から何営業日後に執行するか
```

## 新テーマ追加の手順

```bash
# 1. universe.yaml に銘柄追加（新テーマ名でpurityを設定）
# 2. themes/robotics.yaml を作成（既存ファイルをコピーして編集）
# 3. 動作確認
pnpm run pipeline -- --theme robotics
```
