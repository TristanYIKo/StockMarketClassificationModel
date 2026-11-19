# Multi-Horizon Direction Model Report

Generated: 2026-11-19 14:50 UTC

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

**Two kinds of test score.** The candidate table scores models *frozen* at the
end of their training window -- that is how the algorithm and threshold are
chosen. The deployed model is not frozen: **every day it is refit from scratch**
on the labels known by that day's close, scores that one day, and is thrown
away. **As deployed** replays exactly that over the test period -- one model
per day, each day scored against its own outcome -- so it is the out-of-sample
record of what the site serves. Every one of those calls, with the date its
training data ended, is in `reports/<h>/walk_forward.csv`.

## 1D horizon

Independent events (overlapping windows and four correlated ETFs collapsed): **train 5784, val 251, test 471**. Validation spans 252 sessions to hold a comparable number of events at this horizon.

| Model | Thresh | Test acc | vs baseline | Test bal-acc | Calls UP | Test AUC |
|---|---|---|---|---|---|---|
| logistic_regression **(selected)** | 0.520 | 0.5175 | -0.0223 | 0.5196 | 47.6% | 0.5196 |
| random_forest | 0.505 | 0.5133 | -0.0265 | 0.5047 | 60.8% | 0.5048 |
| lightgbm | 0.515 | 0.4761 | -0.0637 | 0.4818 | 42.7% | 0.4851 |
| xgboost | 0.505 | 0.4713 | -0.0685 | 0.4780 | 41.5% | 0.4788 |

Test baseline (majority class): 0.5398 on 1884 rows; actual up-rate 0.5398.

**As deployed** (logistic_regression, test period):

| Fit | Test bal-acc | Test AUC | Calls UP | Independent events |
|---|---|---|---|---|
| Frozen, trained through 2024-01-01 | 0.5196 | 0.5196 | 47.6% | 471 |
| Refit daily (471 separate models) | 0.5028 | 0.5045 | 44.5% | 471 |

Up-rate over these days: 0.540. Days where all four ETF calls were right: 25.1%; all four wrong: 25.9% -- the four move together, so a day is closer to one event than four.

## 5D horizon

Independent events (overlapping windows and four correlated ETFs collapsed): **train 1156, val 49, test 93**. Validation spans 252 sessions to hold a comparable number of events at this horizon.

| Model | Thresh | Test acc | vs baseline | Test bal-acc | Calls UP | Test AUC |
|---|---|---|---|---|---|---|
| logistic_regression **(selected)** | 0.475 | 0.4732 | -0.0840 | 0.4885 | 36.6% | 0.5165 |
| random_forest | 0.535 | 0.4732 | -0.0840 | 0.5061 | 21.4% | 0.5225 |
| lightgbm | 0.520 | 0.5498 | -0.0075 | 0.5282 | 69.2% | 0.5443 |
| xgboost | 0.510 | 0.5359 | -0.0214 | 0.5138 | 69.4% | 0.5376 |

Test baseline (majority class): 0.5573 on 1868 rows; actual up-rate 0.5573.

**As deployed** (logistic_regression, test period):

| Fit | Test bal-acc | Test AUC | Calls UP | Independent events |
|---|---|---|---|---|
| Frozen, trained through 2024-01-01 | 0.4885 | 0.5165 | 36.6% | 93 |
| Refit daily (467 separate models) | 0.4836 | 0.4851 | 55.2% | 93 |

Up-rate over these days: 0.557. Days where all four ETF calls were right: 22.5%; all four wrong: 23.6% -- the four move together, so a day is closer to one event than four.

## 20D horizon

Independent events (overlapping windows and four correlated ETFs collapsed): **train 260, val 39, test 22**. Validation spans 800 sessions to hold a comparable number of events at this horizon.

| Model | Thresh | Test acc | vs baseline | Test bal-acc | Calls UP | Test AUC |
|---|---|---|---|---|---|---|
| logistic_regression | 0.480 | 0.4159 | -0.2218 | 0.5190 | 13.1% | 0.4794 |
| random_forest | 0.490 | 0.3988 | -0.2389 | 0.5230 | 5.5% ⚠ | 0.5012 |
| lightgbm | 0.250 | 0.5265 | -0.1112 | 0.4682 | 70.3% | 0.4549 |
| xgboost **(selected)** | 0.500 | 0.4663 | -0.1715 | 0.4872 | 42.0% | 0.5207 |

Test baseline (majority class): 0.6377 on 1808 rows; actual up-rate 0.6377.

**As deployed** (xgboost, test period):

| Fit | Test bal-acc | Test AUC | Calls UP | Independent events |
|---|---|---|---|---|
| Frozen, trained through 2021-10-25 | 0.4872 | 0.5207 | 42.0% | 22 |
| Refit daily (452 separate models) | 0.4007 | 0.4127 | 60.0% | 22 |

Up-rate over these days: 0.638. Days where all four ETF calls were right: 23.2%; all four wrong: 39.4% -- the four move together, so a day is closer to one event than four.
