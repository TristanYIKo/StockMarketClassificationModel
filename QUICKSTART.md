# Quick Start Guide

## Step 1: Set Environment Variables

```powershell
# Supabase connection string
setx SUPABASE_DB_URL "postgresql://postgres:your_password@db.your_project.supabase.co:5432/postgres"

# FRED API key (get free key at https://fred.stlouisfed.org/docs/api/api_key.html)
setx FRED_API_KEY "your_fred_api_key_here"
```

**Important**: Restart your terminal/PowerShell after setting environment variables.

## Step 2: Install Dependencies

```powershell
pip install -r requirements.txt
```

## Step 3: Apply Database Migrations

Open Supabase SQL Editor and run these files in order:

1. `migrations/001_init_schema.sql`
2. `migrations/002_add_context_data.sql`

Or use psql:
```powershell
psql $env:SUPABASE_DB_URL -f migrations/001_init_schema.sql
psql $env:SUPABASE_DB_URL -f migrations/002_add_context_data.sql
```

## Step 4: Validate Setup

```powershell
python validate_setup.py
```

This checks:
- ✓ Environment variables set
- ✓ Python dependencies installed
- ✓ Database connection works
- ✓ FRED API accessible

## Step 5: Run ETL

**Full backfill** (2000-2025, ~15-20 minutes):
```powershell
python -m etl.main --start 2000-01-01 --end 2025-12-12 --mode backfill
```

**Incremental update** (last month only):
```powershell
python -m etl.main --start 2025-11-01 --end 2025-12-12 --mode incremental
```

## Step 6: Verify Data

Open Supabase SQL Editor and run queries from `example_queries.sql`:

```sql
-- Check data coverage
select 
  a.symbol,
  count(distinct db.date) as bar_days,
  count(distinct f.date) as feature_days,
  count(distinct l.date) as label_days
from public.assets a
left join public.daily_bars db on db.asset_id = a.id
left join public.features_daily f on f.asset_id = a.id
left join public.labels_daily l on l.asset_id = a.id
where a.symbol in ('SPY', 'QQQ', 'DIA', 'IWM')
group by a.symbol;
```

Expected results for SPY (2000-2025):
- bar_days: ~6,300
- feature_days: ~6,300
- label_days: ~6,295 (last 5 dropped for labels)

## Step 7: Query Modeling Dataset

```sql
select 
  symbol, date, close,
  (feature_json->>'vix_level')::numeric as vix_level,
  (feature_json->>'yield_curve_slope')::numeric as yield_curve_slope,
  (feature_json->>'rsp_spy_ratio_z')::numeric as rsp_spy_ratio_z,
  y_1d, y_5d, y_thresh
from public.v_model_dataset
where symbol = 'SPY' and date between '2020-01-01' and '2023-12-31'
order by date;
```

## Troubleshooting

### Error: "SUPABASE_DB_URL not set"
- Restart terminal after running `setx`
- Or temporarily set: `$env:SUPABASE_DB_URL = "postgresql://..."`

### Error: "FRED_API_KEY not set"
- Get free key: https://fred.stlouisfed.org/docs/api/api_key.html
- Set with `setx FRED_API_KEY "your_key"`

### Error: yfinance download fails
- yfinance sometimes throttles; retry after 1 minute
- Reduce date range for testing

### Error: Database connection refused
- Check Supabase project is running
- Verify connection string format
- Check firewall/network

### FRED series returns empty
- Some series have limited history
- Check series exists: https://fred.stlouisfed.org/series/DGS10

## What Gets Created

### In Database
- **4 ETF assets** (SPY, QQQ, DIA, IWM)
- **10 proxy assets** (VIX, UUP, GLD, USO, HYG, LQD, TLT, RSP, etc)
- **9 macro series** (FRED yields, rates, credit, liquidity)
- **~25,000 daily bars** (4 ETFs × 6,300 days)
- **~25,000 feature rows** (100+ features per row as JSONB)
- **~25,000 label rows** (y_1d, y_5d, y_thresh)
- **~10,000 macro observations**
- **~1,500 calendar events**

### Storage Required
- Total database size: ~500 MB - 1 GB

## Next Steps

1. **Feature analysis**: Explore correlations, importance
2. **Model training**: Build classification models
3. **Backtesting**: Walk-forward validation
4. **Production**: Schedule daily incremental runs

## Support

See full documentation:
- `README.md` - Overview and setup
- `PROJECT_SUMMARY.md` - Architecture and details
- `example_queries.sql` - Query examples
