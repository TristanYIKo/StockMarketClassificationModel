# ETL Fix: Store Current Day Data with Outcome Prices

## Problem
The ETL was dropping the last 5 rows because it couldn't calculate labels without future data. When running at 5 PM on Dec 22:
- Daily bars were updated through Dec 19
- Labels only went through Dec 12 (7 days behind!)
- Dec 22's close price existed but wasn't being used for predictions

## Solution
Modified the ETL to:
1. **Store outcome prices separately** in `daily_bars` table (not just computed labels)
2. **Keep all rows** including those without future data (outcome_price will be NULL until future data arrives)
3. **Allow predictions** before the outcome is known

## Changes Made

### 1. Database Schema (`migrations/015_add_outcome_prices.sql`)
```sql
alter table public.daily_bars
  add column if not exists outcome_price_1d numeric,
  add column if not exists outcome_price_5d numeric;
```

### 2. Transform Labels (`etl/transform_labels.py`)
- Added `keep_incomplete=True` parameter to `compute_labels()`
- Added `outcome_price_1d` and `outcome_price_5d` to output DataFrame
- Changed behavior: now keeps rows even when future data is not available

### 3. Supabase Client (`etl/supabase_client.py`)
- Added `upsert_outcome_prices()` method to update outcome prices in daily_bars

### 4. Load DB (`etl/load_db.py`)
- Added `upsert_outcome_prices()` function to handle outcome price uploads

### 5. ETL Main (`etl/main.py`)
- Updated to call `upsert_outcome_prices()` after upserting labels
- Now upserts ALL data including current day

## How It Works Now

### At 5 PM on Dec 22:
1. ETL downloads Dec 22's OHLC data (close price is set)
2. Updates `daily_bars` with Dec 22's data
3. Creates features for Dec 22
4. Creates labels for Dec 22:
   - `outcome_price_1d`: NULL (will be Dec 23's close)
   - `outcome_price_5d`: NULL (will be Dec 29's close)
   - `y_class_1d`: NULL (can't calculate without outcome)
5. Makes predictions for Dec 23 using Dec 22's features

### Next Day (Dec 23) at 5 PM:
1. ETL downloads Dec 23's OHLC data
2. Updates Dec 22's row:
   - `outcome_price_1d`: Dec 23's close ✅
   - `y_class_1d`: 1 (UP) or -1 (DOWN) ✅
3. Creates new row for Dec 23 (with NULL outcomes)

## Installation Steps

### 1. Apply Database Migration
Go to Supabase Dashboard > SQL Editor and run:

```sql
begin;

alter table public.daily_bars
  add column if not exists outcome_price_1d numeric,
  add column if not exists outcome_price_5d numeric;

comment on column public.daily_bars.outcome_price_1d is 
  'Close price 1 trading day in the future (for next-day predictions). NULL if not yet available.';

comment on column public.daily_bars.outcome_price_5d is 
  'Close price 5 trading days in the future (for weekly predictions). NULL if not yet available.';

create index if not exists idx_daily_bars_outcomes
  on public.daily_bars(asset_id, date)
  where outcome_price_1d is not null or outcome_price_5d is not null;

commit;
```

### 2. Test the ETL
```bash
python run_etl.py
```

### 3. Verify the Results
```bash
python check_db_dates.py
```

You should now see:
- `daily_bars`: Latest date = Dec 22 (or current trading day)
- `labels_daily`: Latest date = Dec 22 (with NULL y_class for recent days)
- `features_daily`: Latest date = Dec 22

## Benefits

1. **Real-time predictions**: Can make predictions using today's data
2. **No data lag**: Labels are created as soon as OHLC data is available
3. **Backfill support**: Outcome prices automatically filled when future data arrives
4. **Clear separation**: Predictions (features) vs. outcomes (labels) are clearly separated
