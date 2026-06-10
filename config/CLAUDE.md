# CLAUDE.md — config/

## ファイル構成

```
config/
  universe.yaml          # 全銘柄マスターレジストリ（変更頻度：低）
  market_params.yaml     # JP/US 10年債金利（手動管理、Sharpe rf に使用）
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

# （任意）コストドライバー連動性。定義すると個別分析レポートに
# 「コスト連動性」セクションが自動表示される（半導体テーマが SOXX と
# 自動比較されるのと同じ仕組みの、コスト要因版）。
# 各ドライバーに対し 相関(日次/月次) と 月次ベータ を算出する。
# 中食・食品・物流など、入力コストでマージンが動く銘柄向け。
cost_benchmarks:             # 省略可。yfinance ティッカーで指定
  - ticker: "JPY=X"          # USD/JPY（輸入コスト）
    label: "USD/JPY (輸入コスト)"
  - ticker: "ZR=F"           # 米先物（US CBOT）※国産米価は反映しない代理指数
    label: "米先物 (US CBOT, 代理)"
  - ticker: "CL=F"           # WTI原油（物流燃料）
    label: "WTI原油 (物流燃料)"
  # 注: 商品先物はドル建て。円ベースの実コストは「商品×USD/JPY」になる点に留意。

analysis:
  start_date: "2023-01-01"  # データ取得開始日
  min_theme_purity: 2       # これ未満のpurityは分析対象外
  top_n_backtest: 5         # バックテストで保有する上位N銘柄

weights:                    # ファクタースコアの重み（合計=1.0）
  momentum: 0.23
  volatility: 0.10
  drawdown: 0.10
  liquidity: 0.08
  theme_purity: 0.18
  risk_adjusted_return: 0.23
  volume: 0.08          # 出来高ファクター（新規）

volume_weights:         # volume_score 内の内訳（合計=1.0）
  rvol_20_60: 0.60      # 直近20D/60D 出来高比率
  price_volume_alignment: 0.40  # 価格・出来高方向の一致度

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

## market_params.yaml

Sharpe・Sortino の超過リターン計算に使う無リスク金利を手動管理するファイル。
コードから自動更新されることはない。金利が大きく動いたときだけ手動で編集する。

| キー | 意味 |
|---|---|
| `risk_free_rates.JP.rate` | JGB 10年利回り（小数。例: 0.015 = 1.5%） |
| `risk_free_rates.US.rate` | UST 10年利回り（小数。例: 0.044 = 4.4%） |

コード側の読み込み: `src/config/loader.py` の `get_risk_free_rate(country)` 参照。
