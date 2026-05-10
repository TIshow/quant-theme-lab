# CLAUDE.md — src/analytics/

## モジュール一覧と役割

| ファイル | 役割 |
|---|---|
| `correlation.py` | 日次リターンのSpearman相関行列 |
| `clustering.py` | 相関ベース階層クラスタリング（距離 = 1 - corr） |
| `benchmark.py` | beta（OLS回帰の傾き）、alpha（超過リターン年率換算） |
| `factor_validation.py` | **IC/ICIR/IC Decay** — ファクターの予測力検証 |
| `theme_comparison.py` | テーマ等金額ポートフォリオの横断比較 |
| `risk_model.py` | Ledoit-Wolf縮小共分散、VaR、CVaR |

## factor_validation.py の概念

### IC（Information Coefficient）
```
IC = ファクター値（時点T）と翌期リターンのSpearman順位相関係数
```
- IC > 0：ファクター高 → リターン高（正の予測力）
- IC < 0：ファクター高 → リターン低（逆張り的予測力）
- IC ≈ 0：予測力なし（ノイズ）

### ICIR（IC Information Ratio）
```
ICIR = mean(IC系列) / std(IC系列)
```
- ICIR > 0.3：使えるファクター
- ICIR > 0.5：強いファクター
- ICIR < 0.1：ノイズ → スコアから除外検討

### IC Decay
時間が経つにつれて予測力がどう減衰するかを測る。
1M先ICが高く12M先ICが低ければ「短期ファクター」と判断。

### 使い方
```python
from src.analytics.factor_validation import validate_all_factors
result = validate_all_factors(prices)
# usable=True のファクターだけを compute_scores() に渡す
```

## risk_model.py の概念

### なぜ Ledoit-Wolf か
銘柄数N > 観測期間T の場合、標本共分散行列は特異行列に近づく。
Ledoit-Wolf は単位行列方向へ最適線形縮小（shrinkage）を行い、
条件数を改善した安定な共分散行列を推定する。

このプロジェクトでは N=20〜50銘柄、T=500〜700営業日 程度のため
標本共分散でも実用上問題ないが、将来的にユニバース拡大時に必要になる。

## theme_comparison.py の概念

テーマ = テーマ内銘柄の等金額（またはpurity加重）ポートフォリオとして扱い、
テーマ間でリターン・Sharpe・最大ドローダウンを比較する。

「テーマモメンタムスコア」= 短期リターン（1M）- 長期リターン（3M）
→ 正：最近加速中のテーマ
→ 負：勢いが落ちているテーマ
