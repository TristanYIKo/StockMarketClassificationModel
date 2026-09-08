# Multi-Horizon Direction Model Report

Generated: 2026-09-08 00:06 UTC

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

Independent events (overlapping windows and four correlated ETFs collapsed): **train 5784, val 251, test 419**. Validation spans 252 sessions to hold a comparable number of events at this horizon.

| Model | Thresh | Test acc | vs baseline | Test bal-acc | Calls UP | Test AUC |
|---|---|---|---|---|---|---|
| logistic_regression **(selected)** | 0.500 | 0.5346 | -0.0167 | 0.5315 | 53.3% | 0.5289 |
| random_forest | 0.510 | 0.4922 | -0.0591 | 0.4841 | 57.8% | 0.4984 |
| lightgbm | 0.515 | 0.4994 | -0.0519 | 0.4948 | 54.5% | 0.5039 |
| xgboost | 0.505 | 0.4952 | -0.0561 | 0.4974 | 47.9% | 0.4958 |

Test baseline (majority class): 0.5513 on 1676 rows; actual up-rate 0.5513.

## 5D horizon

Independent events (overlapping windows and four correlated ETFs collapsed): **train 1156, val 49, test 83**. Validation spans 252 sessions to hold a comparable number of events at this horizon.

| Model | Thresh | Test acc | vs baseline | Test bal-acc | Calls UP | Test AUC |
|---|---|---|---|---|---|---|
| logistic_regression **(selected)** | 0.475 | 0.4789 | -0.1000 | 0.4983 | 37.7% | 0.5216 |
| random_forest | 0.530 | 0.4970 | -0.0819 | 0.5238 | 33.4% | 0.5172 |
| lightgbm | 0.565 | 0.5482 | -0.0307 | 0.5341 | 59.5% | 0.5388 |
| xgboost | 0.530 | 0.5355 | -0.0434 | 0.5232 | 58.2% | 0.5222 |

Test baseline (majority class): 0.5789 on 1660 rows; actual up-rate 0.5789.

## 20D horizon

Independent events (overlapping windows and four correlated ETFs collapsed): **train 260, val 39, test 20**. Validation spans 800 sessions to hold a comparable number of events at this horizon.

| Model | Thresh | Test acc | vs baseline | Test bal-acc | Calls UP | Test AUC |
|---|---|---|---|---|---|---|
| logistic_regression | 0.485 | 0.3831 | -0.2925 | 0.5264 | 10.1% | 0.4641 |
| random_forest | 0.495 | 0.3350 | -0.3406 | 0.4968 | 3.8% ⚠ | 0.4674 |
| lightgbm | 0.245 | 0.5906 | -0.0850 | 0.4807 | 80.6% | 0.4440 |
| xgboost **(selected)** | 0.495 | 0.4219 | -0.2538 | 0.4514 | 39.9% | 0.4691 |

Test baseline (majority class): 0.6756 on 1600 rows; actual up-rate 0.6756.
