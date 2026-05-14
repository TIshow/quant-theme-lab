# CLAUDE.md — src/scoring/

## なぜ z-score ではなくランク正規化か

このプロジェクトのユニバースには EOSE・AMPX・SLDP のような
超小型・低流動性株が含まれる。これらの売買代金は大型株の
1/1000 以下になることがあり、z-score では外れ値が支配的になる。

**ランク正規化 + ウィンソライズ** の利点:
- 出力が必ず [0, 1] に収まる（スコアが爆発しない）
- 外れ値の影響を上下5%カットで遮断
- ランク変換後は全銘柄が均等に分布

## scorer.py の処理フロー

```python
# 1. ウィンソライズ（上下5%をクリップ）
arr = winsorize(series, limits=[0.05, 0.05])

# 2. ランク変換（1〜N）
ranks = rankdata(arr)

# 3. [0, 1] 正規化
normalized = (ranks - 1) / (N - 1)

# 4. 低い方が良い指標（volatility, drawdown）は反転
if not higher_is_better:
    normalized = 1.0 - normalized
```

## スコア構成（battery_storage.yaml デフォルト）

```
final_score =
  momentum_score              × 0.18
  volatility_score（低=良）  × 0.08
  drawdown_score（低=良）    × 0.08
  liquidity_score             × 0.06
  volume_score                × 0.06
  theme_purity_score          × 0.17
  risk_adjusted_return_score  × 0.22
  fundamentals_score          × 0.15
```

### momentum_score の内訳（momentum_weights）
```
return_1m × 0.20 + return_3m × 0.50 + return_6m × 0.30
```
→ 合成後に rank_normalize

### volume_score の内訳（volume_weights）
```
rvol_20_60 × 0.60 + price_volume_alignment × 0.40
```
→ 合成後に rank_normalize

### risk_adjusted_return_score の内訳（risk_adjusted_return_weights）
```
sharpe_6m × 0.40 + sharpe_12m × 0.40 + calmar_12m × 0.20
```
→ 合成後に rank_normalize

### ファンダメンタルズの正規化

`fundamentals_score` は `compute_scores_by_region()` により JP/US 内で独立してランク正規化される。JP の ROE 平均 8〜10% と US の 15〜20% という構造差を補正するため。

### 無リスク金利

Sharpe の rf は `config/market_params.yaml` から読み込む（JP: JGB 10年、US: UST 10年）。
コード側: `src/config/loader.py` の `get_risk_free_rate(country)` を参照。

## 欠損値の扱い

- ファクター計算で NaN が発生した場合（短期上場銘柄等）は中央値で補完してからスコア計算
- `data_quality_flag` でレポートに注意表示

## 将来改善: IC-weighted scoring

現在は weights を YAML で固定しているが、
`factor_validation.py` の ICIR を使って重みを自動調整できる:
```python
weights = {factor: max(0, icir[factor]) for factor in factors}
weights = normalize(weights)  # 合計=1に正規化
```
→ Phase 5 で実装予定
