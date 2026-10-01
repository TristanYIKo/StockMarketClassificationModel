# Multi-Horizon Direction Model Report

Generated: 2026-10-01 13:46 UTC

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

Independent events (overlapping windows and four correlated ETFs collapsed): **train 5784, val 251, test 433**. Validation spans 252 sessions to hold a comparable number of events at this horizon.

| Model | Thresh | Test acc | vs baseline | Test bal-acc | Calls UP | Test AUC |
|---|---|---|---|---|---|---|
| logistic_regression **(selected)** | 0.500 | 0.5300 | -0.0139 | 0.5262 | 54.6% | 0.5175 |
| random_forest | 0.510 | 0.4890 | -0.0548 | 0.4827 | 57.1% | 0.4989 |
| lightgbm | 0.515 | 0.4977 | -0.0462 | 0.4936 | 54.6% | 0.5007 |
| xgboost | 0.505 | 0.4758 | -0.0681 | 0.4781 | 47.1% | 0.4776 |

Test baseline (majority class): 0.5439 on 1732 rows; actual up-rate 0.5439.

## 5D horizon

Independent events (overlapping windows and four correlated ETFs collapsed): **train 1156, val 49, test 86**. Validation spans 252 sessions to hold a comparable number of events at this horizon.

| Model | Thresh | Test acc | vs baseline | Test bal-acc | Calls UP | Test AUC |
|---|---|---|---|---|---|---|
| logistic_regression **(selected)** | 0.475 | 0.4767 | -0.0930 | 0.4920 | 39.0% | 0.5132 |
| random_forest | 0.530 | 0.5017 | -0.0680 | 0.5264 | 32.7% | 0.5255 |
| lightgbm | 0.565 | 0.5535 | -0.0163 | 0.5436 | 57.7% | 0.5470 |
| xgboost | 0.525 | 0.5401 | -0.0297 | 0.5137 | 69.1% | 0.5358 |

Test baseline (majority class): 0.5698 on 1720 rows; actual up-rate 0.5698.

## 20D horizon

Independent events (overlapping windows and four correlated ETFs collapsed): **train 260, val 39, test 20**. Validation spans 800 sessions to hold a comparable number of events at this horizon.

| Model | Thresh | Test acc | vs baseline | Test bal-acc | Calls UP | Test AUC |
|---|---|---|---|---|---|---|
| logistic_regression | 0.485 | 0.3978 | -0.2608 | 0.5285 | 9.7% ⚠ | 0.4837 |
| random_forest | 0.495 | 0.3516 | -0.3071 | 0.4984 | 3.7% ⚠ | 0.4819 |
| lightgbm | 0.245 | 0.5781 | -0.0805 | 0.4766 | 81.2% | 0.4415 |
| xgboost **(selected)** | 0.495 | 0.4435 | -0.2151 | 0.4762 | 38.9% | 0.4844 |

Test baseline (majority class): 0.6587 on 1664 rows; actual up-rate 0.6587.
