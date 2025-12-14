# FEATURE MANIFEST (Post-Pruning)

## Summary
Total features: **60 features** (22 technical + 12 macro + 4 VIX + 8 cross-asset + 4 breadth + 3 events + 6 OHLCV + 1 symbol)

## Feature Categories

### 1. Technical Features (22)

**Returns / Momentum (4)**
- `log_ret_1d`: 1-day log return
- `log_ret_5d`: 5-day log return  
- `log_ret_20d`: 20-day log return (monthly)
- `rsi_14`: 14-day RSI momentum indicator

**MACD (1)**
- `macd_hist`: MACD histogram (divergence from signal line)

**Volatility / Range (8)**
- `vol_5`: 5-day rolling volatility (std of daily returns)
- `vol_20`: 20-day rolling volatility
- `vol_60`: 60-day rolling volatility (quarterly)
- `atr_14`: 14-day Average True Range
- `high_low_pct`: Daily high-low range as % of close
- `close_open_pct`: Daily close-open change as % of open

**Moving Averages (6)**
- `sma_20`: 20-day simple moving average
- `sma_50`: 50-day simple moving average
- `sma_200`: 200-day simple moving average
- `ema_20`: 20-day exponential moving average
- `ema_50`: 50-day exponential moving average
- `sma20_gt_sma50`: Binary indicator (1 if SMA20 > SMA50, 0 otherwise)

**Volume (2)**
- `volume_z`: Volume z-score (20-day rolling)
- `volume_chg_pct`: Daily volume % change

**Drawdown (1)**
- `dd_60`: Current drawdown from 60-day rolling max

**Calendar (2)**
- `dow`: Day of week (0=Mon, 4=Fri)
- `days_since_prev`: Days since previous trading day (detects holiday gaps)

---

### 2. Macro Features (12)

**Interest Rates (5)**
- `dgs2`: 2-year Treasury yield (%)
- `dgs10`: 10-year Treasury yield (%)
- `yield_curve_slope`: 10Y - 2Y yield spread (bps)
- `dgs10_change_1d`: 1-day change in 10Y yield
- `dgs10_change_5d`: 5-day change in 10Y yield

**Credit Spreads (3)**
- `hy_oas_level`: High-yield option-adjusted spread (bps)
- `hy_oas_change_1d`: 1-day change in HY OAS
- `hy_oas_change_5d`: 5-day change in HY OAS

**Liquidity (4)**
- `liquidity_expanding`: Binary indicator (1 if Fed balance sheet expanding)
- `fed_bs_chg_pct`: Fed balance sheet % change (5-day)
- `rrp_level`: Overnight reverse repo level ($B)
- `rrp_chg_pct_5d`: RRP % change (5-day)

---

### 3. VIX Features (4)

- `vix_level`: VIX index level (volatility)
- `vix_change_1d`: 1-day change in VIX
- `vix_change_5d`: 5-day change in VIX
- `vix_term_structure`: VIX / VIX9D ratio (term structure slope)

---

### 4. Cross-Asset Features (8)

**Currency & Commodities (3)**
- `dxy_ret_5d`: US Dollar Index 5-day return
- `gold_ret_5d`: Gold (GLD) 5-day return
- `oil_ret_5d`: Oil (USO) 5-day return

**Credit (5)**
- `hyg_ret_5d`: High-yield credit (HYG) 5-day return
- `hyg_vs_spy_5d`: HYG vs SPY relative strength (5-day)
- `hyg_spy_corr_20d`: HYG-SPY 20-day rolling correlation
- `lqd_ret_5d`: Investment-grade credit (LQD) 5-day return
- `tlt_ret_5d`: Long-term Treasury (TLT) 5-day return

---

### 5. Breadth Features (4)

- `rsp_spy_ratio`: Equal-weight / market-cap ratio (RSP/SPY)
- `rsp_spy_ratio_z`: RSP/SPY ratio z-score (20-day rolling)
- `qqq_spy_ratio_z`: QQQ/SPY ratio z-score (tech strength)
- `iwm_spy_ratio_z`: IWM/SPY ratio z-score (small-cap strength)

---

### 6. Event Flags (3)

- `is_fomc`: 1 if FOMC meeting day, 0 otherwise (~8 per year)
- `is_cpi_release`: 1 if CPI release day, 0 otherwise (~12 per year)
- `is_nfp_release`: 1 if NFP release day, 0 otherwise (~12 per year)

---

### 7. OHLCV (6)

- `open`: Opening price
- `high`: High price
- `low`: Low price
- `close`: Closing price
- `adj_close`: Adjusted closing price (dividend/split adjusted)
- `volume`: Trading volume

---

### 8. Metadata (1)

- `symbol`: Asset ticker (SPY, QQQ, DIA, IWM)

---

## Dropped Features (11)

### Why We Pruned

**Redundant Moving Averages (4)**
- `sma_5`, `sma_10`: Too short, noisy, captured by 20-day
- `ema_5`, `ema_10`, `ema_200`: Redundant with kept MAs

**Redundant MACD (2)**
- `macd_line`, `macd_signal`: Histogram captures divergence sufficiently

**Redundant Returns/Vol (2)**
- `log_ret_10d`: Redundant with 5d/20d
- `vol_10d`: Redundant with 5d/20d

**Noisy Volume (1)**
- `obv`: On-Balance Volume is noisy, z-score more robust

**Redundant Drawdown (1)**
- `dd_20`: 60-day captures longer trend

**Low-ROI Calendar (1)**
- `month`: Seasonal effects captured by macro features

**Dropped Events (3 types)**
- `is_month_end`: Weak signal, redundant with calendar
- `is_quarter_end`: Weak signal, redundant with calendar
- `is_options_expiry_week`: High frequency noise, low predictive power

---

## Training Window Requirements

**Minimum warm-up period: 260 trading days (~1 year)**

This ensures all features have sufficient history:
- SMA200 needs 200 days
- Rolling vol 60d needs 60 days
- Macro forward-fill tolerates 5-7 day gaps

**Recommended split:**
- Training: 2001-01-01 to 2022-12-31 (after 260-day warm-up from 2000 start)
- Validation: 2023-01-01 to 2023-12-31
- Test: 2024-01-01 to present

---

## Data Quality Checks

1. **No duplicate (asset_id, date)** in features_daily / labels_daily
2. **NaN handling**: First 260 rows may have NaN (warm-up period)
3. **Event validation**: Only fomc, cpi_release, nfp_release allowed
4. **Label shift**: Labels use future closes (no leakage)
5. **Timezone**: All dates in America/New_York

---

## Feature Access

**SQL View:** `v_model_dataset` (pruned feature set)
**Raw JSONB:** `features_daily.feature_json` column
**Pruned View:** `v_features_pruned` (exploded columns from JSONB)

---

## Usage Example

```python
import pandas as pd
from etl.supabase_client import SupabaseDB

db = SupabaseDB()

# Get full modeling dataset
query = """
    select * from v_model_dataset
    where symbol = 'SPY'
    and date >= '2021-01-01'
    order by date
"""
df = pd.DataFrame(db.client.table('v_model_dataset').select('*').execute().data)

# Split features and labels
feature_cols = [c for c in df.columns if c not in ['symbol', 'date', 'y_1d', 'y_5d', 'y_thresh']]
X = df[feature_cols]
y = df['y_thresh']  # or y_1d, y_5d

# Handle NaN (first 260 rows)
X = X.iloc[260:]
y = y.iloc[260:]

# Ready for sklearn
from sklearn.ensemble import RandomForestClassifier
clf = RandomForestClassifier()
clf.fit(X, y)
```

---

## Version History

- **v1 (001_init_schema.sql)**: Initial schema with comprehensive features
- **v2 (002_add_context_data.sql)**: Added macro, proxies, events
- **v3 (003_prune_features_and_events.sql)**: Pruned to 60 high-signal features
