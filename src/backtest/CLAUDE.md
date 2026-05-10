# CLAUDE.md — src/backtest/

## モジュール一覧

| ファイル | 役割 |
|---|---|
| `simple_backtest.py` | 月次モメンタム top-N バックテスト（取引コスト込み） |
| `walk_forward.py` | Walk-forward アウトオブサンプル検証 |

## simple_backtest.py のロジック

```
毎月末:
  1. 過去 lookback_days（デフォルト63=3M）のリターンで全銘柄をランク
  2. 上位 top_n 銘柄を選択
  3. execution_lag_days 後の終値で約定（実行ラグ）
  4. 翌月末 + execution_lag_days で決済
  5. 往路・復路それぞれ transaction_cost_bps を差引く
```

### 取引コストの考え方
- 新規に選ばれた銘柄：買い + 売り = 往復コスト
- 前月から継続の銘柄：ターンオーバーなし → コスト軽減
- 設定: `config/themes/*.yaml` の `backtest.transaction_cost_bps`

### 主要パラメータ（themes/*.yaml から読み込み）
```yaml
backtest:
  transaction_cost_bps: 30   # 片道30bps（0.30%）= 往復60bps
  execution_lag_days: 1      # 月末翌営業日に執行
```

## walk_forward.py のロジック

```
インサンプル過学習を防ぐためのアウトオブサンプル検証:

  [訓練期間 train_months] → [テスト期間 test_months] → スライド →
  [訓練期間] → [テスト期間] → スライド → ...

訓練期間: ファクターランクを計算して top-N を決定
テスト期間: その top-N を実際に保有して実現リターンを測定
```

### なぜ Walk-forward が必要か
`simple_backtest.py` は全期間のデータを使ってランキングするため、
「過去全体を見た上でのバックテスト」になる。
Walk-forward は「その時点で入手可能なデータのみ」でランキングするため、
実際の運用に近い形で検証できる。

## 制約事項（現バージョン）

- 生存者バイアス: 上場廃止銘柄はユニバースに含まれない
- 実行価格: 終値での約定を仮定（実際はスリッページがある）
- 無リスク金利: ゼロと仮定（Sharpe計算時）
- 財務データ: 使用していない（価格のみ）
