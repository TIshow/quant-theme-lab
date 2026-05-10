# Methodology

## スコアリング設計

### なぜランク正規化か

本プロジェクトのユニバースには大型株（NVDA、TSLA 等）と
超小型株（EOSE、AMPX 等）が混在する。

z-score では超小型株の売買代金が外れ値となり liquidity_score が支配的になる。
**ランク正規化 + ウィンソライズ（5%/95%）** を使うことで、
出力を [0, 1] に収め、外れ値の影響を排除している。

```
score = rank(winsorize(factor, 5%/95%)) / (N - 1)
```

高い方が良い指標（リターン、Sharpe 等）はそのまま使用。  
低い方が良い指標（ボラティリティ、ドローダウン）は `1 - score` に変換。

---

### ファクター構成

#### Momentum Score
```
raw = return_1m × 0.20 + return_3m × 0.50 + return_6m × 0.30
momentum_score = rank_normalize(raw, higher_is_better=True)
```
3Mに最大ウェイトを置く。12Mリターンは含めない（超過リバーサルを避けるため）。

#### Volatility Score
```
volatility_score = rank_normalize(annualized_volatility, higher_is_better=False)
```
年率ボラティリティが低い銘柄ほど高スコア。

#### Drawdown Score
```
drawdown_score = rank_normalize(max_drawdown_12m, higher_is_better=False)
```
直近12Mの最大ドローダウンが小さい銘柄ほど高スコア。

#### Liquidity Score
```
liquidity_score = rank_normalize(avg_traded_value_3m, higher_is_better=True)
```
過去3Mの平均売買代金（終値 × 出来高）が大きい銘柄ほど高スコア。

#### Risk-Adjusted Return Score
```
raw = sharpe_6m × 0.40 + sharpe_12m × 0.40 + calmar_12m × 0.20
risk_adjusted_return_score = rank_normalize(raw, higher_is_better=True)
```
無リスク金利はゼロと仮定（初期版）。

#### Theme Purity Score
```
theme_purity_score = rank_normalize(theme_purity, higher_is_better=True)
```
`config/universe.yaml` の手動設定値（1〜5）を使用。

#### Final Score
```
final_score =
  momentum_score              × 0.25
  + volatility_score          × 0.10
  + drawdown_score            × 0.10
  + liquidity_score           × 0.10
  + theme_purity_score        × 0.20
  + risk_adjusted_return_score × 0.25
```

---

## バックテスト設計

### 月次モメンタム top-N 戦略

```
毎月末:
  1. 過去63営業日（≈3M）リターンで全テーマ銘柄をランク
  2. 上位 top_n 銘柄（デフォルト5）を選択
  3. 翌営業日の終値で約定（execution_lag_days=1）
  4. 翌月末の翌営業日で決済
  5. 取引コスト控除:
     - 継続保有銘柄: 片道コストなし
     - 新規/退出銘柄: 片道 transaction_cost_bps を控除
```

### 取引コストの設定目安

| 市場 | 推奨値（片道） |
|---|---|
| 米国大型株 | 10〜20 bps |
| 米国小型株 | 20〜40 bps |
| 日本大型株 | 10〜20 bps |
| 日本小型株 | 30〜50 bps |

デフォルト 30 bps（片道）= 往復 60 bps（0.60%）は保守的な設定。

### 制約事項（現バージョン）

| 項目 | 現状 | 将来対応 |
|---|---|---|
| 生存者バイアス | あり（上場廃止銘柄非考慮） | 廃止銘柄データ追加 |
| 実行価格 | 終値仮定 | VWAP またはオープン価格 |
| 無リスク金利 | ゼロ | 各国政策金利 |
| ショート | なし | ロングオンリー維持の予定 |

---

## ファクター検証（IC / ICIR）

### Information Coefficient（IC）
ファクター値と翌期リターンのSpearman順位相関係数。

```python
IC_t = spearmanr(factor_values_t, forward_returns_t)
```

| IC値の解釈 |
|---|
| IC > 0: ファクター高 → リターン高（正の予測力） |
| IC < 0: ファクター高 → リターン低（反転・逆張り） |
| IC ≈ 0: 予測力なし |

### IC Information Ratio（ICIR）
```
ICIR = mean(IC系列) / std(IC系列)
```

| ICIR | 判定 |
|---|---|
| > 0.5 | 強いシグナル |
| 0.3〜0.5 | 使えるシグナル |
| 0.1〜0.3 | 弱いシグナル（要注意） |
| < 0.1 | ノイズ（スコアから除外検討） |

### IC Decay
複数の先行期間（1M, 2M, ..., 12M）でICを計算し、
ファクターの予測力がどの時間軸で有効かを確認する。
短期で高く長期で低ければ「モメンタム系」、
長期で安定していれば「バリュー系」と分類できる。

---

## リスクモデル（Ledoit-Wolf 共分散）

標本共分散行列は観測期間 T < 銘柄数 N の場合に不安定になる。
Ledoit-Wolf 推定量は単位行列方向への最適線形縮小を適用し、
安定した正定値共分散行列を生成する。

本プロジェクトでは主に以下に使用:
- ポートフォリオの VaR / CVaR 計算
- 将来的な最適ウェイト計算（MVP ポートフォリオ等）
