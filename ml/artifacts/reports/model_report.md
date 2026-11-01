# Multi-Horizon Direction Model Report

Generated: 2026-11-01 13:43 UTC

Binary UP/DOWN classification.

**vs baseline** is accuracy minus the always-UP rate. **Bal-acc** is balanced
accuracy, the mean of per-class recall: 0.50 means no discrimination no matter
how high plain accuracy looks. **Calls UP** is the share of predictions that
were UP -- if it approaches 100%, the model has collapsed to the majority class
and its headline accuracy is the base rate rather than skill (flagged ⚠).

Each horizon is a separate problem: its own base rate (up-rates rise with
horizon), its own purged split boundaries, and its own effective sample size.
Row counts are NOT sample sizes -- consecutive 20-day windows share 19 of their
20 days and SPY/QQQ/DIA/IWM are near-copies, so 25,748 rows carry only a few
hundred independent events. Every error bar is sized on the effective count.

## 1D horizon

Independent events (overlapping windows and four correlated ETFs collapsed): **train 5784, val 251, test 449**. Validation spans 252 sessions to hold a comparable number of events at this horizon.

| Model | Thresh | Test acc | vs baseline | Test bal-acc | Calls UP | Test AUC |
|---|---|---|---|---|---|---|
| logistic_regression **(selected)** | 0.500 | 0.5284 | -0.0134 | 0.5234 | 56.2% | 0.5116 |
| random_forest | 0.510 | 0.4894 | -0.0523 | 0.4845 | 55.8% | 0.4987 |
| lightgbm | 0.515 | 0.4994 | -0.0423 | 0.4952 | 55.0% | 0.5017 |
| xgboost | 0.505 | 0.4783 | -0.0635 | 0.4803 | 47.4% | 0.4792 |

Test baseline (majority class): 0.5418 on 1796 rows; actual up-rate 0.5418.

## 5D horizon

Independent events (overlapping windows and four correlated ETFs collapsed): **train 1156, val 49, test 89**. Validation spans 252 sessions to hold a comparable number of events at this horizon.

| Model | Thresh | Test acc | vs baseline | Test bal-acc | Calls UP | Test AUC |
|---|---|---|---|---|---|---|
| logistic_regression **(selected)** | 0.475 | 0.4799 | -0.0893 | 0.4916 | 41.4% | 0.5109 |
| random_forest | 0.530 | 0.4989 | -0.0703 | 0.5242 | 32.0% | 0.5265 |
| lightgbm | 0.565 | 0.5513 | -0.0179 | 0.5426 | 56.9% | 0.5440 |
| xgboost | 0.525 | 0.5379 | -0.0312 | 0.5140 | 67.5% | 0.5343 |

Test baseline (majority class): 0.5692 on 1792 rows; actual up-rate 0.5692.

## 20D horizon

Independent events (overlapping windows and four correlated ETFs collapsed): **train 260, val 39, test 21**. Validation spans 800 sessions to hold a comparable number of events at this horizon.

| Model | Thresh | Test acc | vs baseline | Test bal-acc | Calls UP | Test AUC |
|---|---|---|---|---|---|---|
| logistic_regression | 0.485 | 0.4036 | -0.2494 | 0.5192 | 12.8% | 0.4756 |
| random_forest | 0.495 | 0.3568 | -0.2962 | 0.4989 | 3.5% ⚠ | 0.4893 |
| lightgbm | 0.245 | 0.5756 | -0.0774 | 0.4755 | 82.0% | 0.4391 |
| xgboost **(selected)** | 0.495 | 0.4440 | -0.2090 | 0.4768 | 38.6% | 0.4870 |

Test baseline (majority class): 0.6530 on 1732 rows; actual up-rate 0.6530.
