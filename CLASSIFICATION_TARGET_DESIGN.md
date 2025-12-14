# Classification Target Design - Why Keep the "Hold" Class?

## The Triple-Barrier Method

**Target Definition:**
- **1 (Buy):** `y_1d_vol > +0.25` (significant up move)
- **-1 (Sell):** `y_1d_vol < -0.25` (significant down move)  
- **0 (Hold):** `y_1d_vol` between -0.25 and +0.25 (noise/chop)

---

## Why Keep Class 0 (Hold)?

### ❌ **WRONG Approach: Filter Out Hold Class**

Many traders make this mistake:

```python
# BAD: Remove Hold class
df_filtered = df[df['y_class_1d'] != 0]  # Only Buy and Sell

# Train binary classifier
model.fit(X, y)  # y is now only {-1, 1}
```

**Problems:**
1. **Model never sees "do nothing" examples** → doesn't learn when NOT to trade
2. **Forces prediction on every day** → overtrades in choppy markets
3. **Ignores regime context** → treats ranging and trending markets the same
4. **Poor calibration** → model confidence meaningless

**Real-world result:** Model trades 100% of days, most trades are noise, loses money to friction.

---

### ✅ **CORRECT Approach: Keep Hold Class**

```python
# GOOD: Keep all three classes
# y_class_1d has values: -1, 0, 1

# Train 3-class classifier
model.fit(X, y)  # Model learns Buy, Hold, AND Sell

# At prediction time:
pred = model.predict(X_today)
if pred == 0:
    # Do nothing - market is choppy
    pass
```

**Benefits:**

#### 1. **Anti-Overtrading**
- Model explicitly learns when market movement is just noise
- Prevents trading in low signal-to-noise conditions
- Reduces transaction costs (commissions + slippage)

#### 2. **Regime Awareness**
- Model learns: "High VIX + narrow range = chop (Hold)"
- Distinguishes: "Trend day vs range day"
- Adapts trading frequency to market conditions

#### 3. **Better Calibration**
- Probability outputs are meaningful:
  - `P(Buy)=0.7, P(Hold)=0.2, P(Sell)=0.1` → confident Buy
  - `P(Buy)=0.4, P(Hold)=0.5, P(Sell)=0.1` → stay out
- Can threshold on confidence: "Only trade if P(action) > 0.6"

#### 4. **Realistic Backtesting**
- Backtest reflects actual trading behavior
- Win rate is "wins / (wins + losses)", not "wins / total days"
- Can measure: "Model trades 30% of days with 55% win rate"

---

## Example: Why This Matters

### Scenario: Choppy Sideways Market (Jan 2024)

**Binary Classifier (no Hold class):**
```
Days traded: 20/20 (100%)
Wins: 10, Losses: 10
Win rate: 50%
P&L: -0.5% (friction eats profit)
```

**3-Class Classifier (with Hold):**
```
Predictions: 8 Buy, 10 Hold, 2 Sell
Days traded: 10/20 (50%)
Wins: 6, Losses: 4
Win rate: 60%
P&L: +1.2% (selective trading wins)
```

The Hold class **saved** the trader from 10 unprofitable coin-flip trades.

---

## Threshold Selection

The threshold `±0.25` is calibrated to `y_1d_vol` (volatility-scaled returns).

**Intuition:**
- `y_1d_vol = 0.25` means "1-day return = 0.25 × rolling_vol_20"
- For SPY with 15% annual vol → daily vol ≈ 1% → threshold ≈ 0.25%
- This separates signal (>0.25%) from noise (<0.25%)

**Class Distribution Guidelines:**
- **Ideal:** 30-40% Buy, 30-40% Hold, 20-30% Sell (markets trend up)
- **Warning:** Hold > 85% → threshold too strict → model rarely trades
- **Danger:** Hold < 10% → threshold too loose → mostly noise

Check distribution:
```sql
select * from public.v_classification_stats_1d;
```

---

## Model Training Best Practices

### 1. **Handle Class Imbalance**
```python
from sklearn.ensemble import RandomForestClassifier

# Option A: Class weights
model = RandomForestClassifier(class_weight='balanced')

# Option B: SMOTE (oversample minority class)
from imblearn.over_sampling import SMOTE
X_resampled, y_resampled = SMOTE().fit_resample(X_train, y_train)
```

### 2. **Evaluate on All Three Classes**
```python
from sklearn.metrics import classification_report

print(classification_report(y_test, y_pred, 
                          target_names=['Sell', 'Hold', 'Buy']))
```

**Key metrics:**
- Precision(Buy): "Of predicted Buys, how many were correct?"
- Recall(Hold): "Of actual Holds, how many did model catch?"
- F1(Sell): Balance of precision and recall for Sells

### 3. **Backtesting with Hold**
```python
# Only trade when model is NOT Hold
for date, pred in predictions.items():
    if pred == 1:  # Buy
        enter_long(date)
    elif pred == -1:  # Sell
        enter_short(date)
    else:  # Hold (pred == 0)
        pass  # Do nothing - stay out of market
```

---

## SQL Validation

Check your dataset health:

```sql
-- Overall distribution
select * from public.v_classification_stats_1d_overall;

-- Per symbol
select * from public.v_classification_stats_1d;

-- Run validation checks
select * from public.validate_classification_dataset_1d();
```

**Python validation:**
```bash
python validate_classification_dataset.py --supabase
```

---

## Summary

| Approach | Hold Class | Result |
|----------|-----------|--------|
| Binary (Bad) | Filtered out | Overtrades, low profit, poor calibration |
| 3-Class (Good) | Kept in | Selective trading, higher win rate, regime-aware |

**The Hold class is not noise to remove—it's signal about when NOT to trade.**

In real trading, knowing when to stand aside is as important as knowing when to act.

---

**Next Steps:**
1. Run migration 008: `psql $DB_URL -f migrations/008_add_classification_support.sql`
2. Backfill data: `python -m etl.main --start 2000-01-01 --end 2025-12-14 --mode backfill`
3. Validate: `python validate_classification_dataset.py --supabase`
4. Check distribution: `select * from v_classification_stats_1d;`
5. Train 3-class model with class weights
