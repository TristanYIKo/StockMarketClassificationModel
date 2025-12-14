# Multi-Horizon Classification Model Comparison

Generated: 2025-12-14 18:04:50

---


## 1D Horizon

Predicting 1d ahead


### Validation Metrics

| Model | Accuracy | F1 Macro | F1 Action | Trade Rate | Conf Thresh | Margin Thresh |
|-------|----------|----------|-----------|------------|-------------|---------------|
| random_forest | 0.4266 | 0.3639 | 0.4834 | 64.98% | 0.41 | 0.00 |
| lightgbm | 0.4058 | 0.3687 | 0.5290 | 54.86% | 0.45 | 0.00 |
| xgboost | 0.3909 | 0.3385 | 0.4684 | 65.28% | 0.41 | 0.00 |

### Test Metrics

| Model | Accuracy | F1 Macro | F1 Action | Trade Rate |
|-------|----------|----------|-----------|------------|
| random_forest | 0.4109 | 0.3413 | 0.4174 | 63.63% |
| lightgbm | 0.3326 | 0.2984 | 0.4160 | 57.62% |
| xgboost | 0.3755 | 0.2999 | 0.4055 | 66.42% |


## 5D Horizon

Predicting 5d ahead


### Validation Metrics

| Model | Accuracy | F1 Macro | F1 Action | Trade Rate | Conf Thresh | Margin Thresh |
|-------|----------|----------|-----------|------------|-------------|---------------|
| random_forest | 0.3244 | 0.2558 | 0.4576 | 41.87% | 0.55 | 0.00 |
| lightgbm | 0.4157 | 0.2952 | 0.4288 | 59.82% | 0.55 | 0.00 |
| xgboost | 0.3780 | 0.2724 | 0.4303 | 56.15% | 0.34 | 0.17 |

### Test Metrics

| Model | Accuracy | F1 Macro | F1 Action | Trade Rate |
|-------|----------|----------|-----------|------------|
| random_forest | 0.3262 | 0.2418 | 0.4230 | 45.39% |
| lightgbm | 0.3240 | 0.2295 | 0.3985 | 51.82% |
| xgboost | 0.4024 | 0.2642 | 0.4336 | 61.05% |


## Cross-Horizon Comparison

Best model per horizon:


**1D**: random_forest - 41.09% accuracy, 0.3413 F1 macro, 63.63% trade rate

**5D**: xgboost - 40.24% accuracy, 0.2642 F1 macro, 61.05% trade rate


---


## Key Insights

- **5-day models perform -5.9% better on average**

- 1d average accuracy: 37.30%

- 5d average accuracy: 35.09%

- Random baseline (3-class): 33.3%
