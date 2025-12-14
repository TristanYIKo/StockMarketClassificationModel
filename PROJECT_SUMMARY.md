# Stock Market Classification Model - Project Overview

## Summary

Triple-barrier classification system for 1-day trading signals on SPY, QQQ, DIA, IWM. Uses 83 optimized features from technical indicators, macro data, and cross-asset proxies. All data is **ET timezone aligned** with **zero future leakage**.

**Primary Target:** `y_class_1d` → -1 (Sell), 0 (Hold), 1 (Buy) using ±0.25 volatility threshold

## Architecture

### Data Layer (Supabase Postgres)

**Tables:**
- `assets` - ETFs, indices, proxies with timezone metadata
- `daily_bars` - OHLCV for all assets (ET trading dates)
- `corporate_actions` - Splits/dividends
- `macro_series` - FRED series catalog
- `macro_daily` - FRED observations with `days_since_update` tracking
- `features_daily` - Computed features as JSONB
- `labels_daily` - Classification targets (y_1d, y_5d, y_thresh)
- `events_calendar` - Calendar events (month-end, FOMC, CPI, NFP, options expiry)

**Views:**
- `v_model_dataset` - Original dataset view
- `v_model_dataset_enhanced` - Enhanced with event flags as boolean columns

### ETL Pipeline (Python 3.11)

**Modules:**

1. **config.py** - Configuration with FRED series, proxy tickers, feature windows
2. **supabase_client.py** - Postgres client with idempotent upserts
3. **extract_yf.py** - yfinance extraction for ETF OHLCV
4. **extract_fred.py** - FRED API with ET alignment and forward-fill tracking
5. **extract_proxies.py** - Cross-asset proxy data (VIX, UUP, GLD, USO, HYG, LQD, TLT, RSP)
6. **build_events.py** - Events calendar builder (computed + known dates)
7. **transform_features.py** - Technical features from OHLCV
8. **transform_features_context.py** - Context feature merging with leakage prevention
9. **transform_labels.py** - Label generation with forward shift
10. **load_db.py** - Database loaders
11. **main.py** - ETL orchestrator

## Data Sources

### FRED Macro (9 series)
- **DGS2, DGS10** - Treasury yields → yield curve slope
- **FEDFUNDS, EFFR** - Fed funds rate
- **T10YIE** - 10Y breakeven inflation
- **BAMLH0A0HYM2** - High yield OAS (credit spread)
- **WALCL** - Fed balance sheet (liquidity regime)
- **RRPONTSYD** - Overnight reverse repo (liquidity)
- **SOFR** - Secured overnight financing rate

### Cross-Asset Proxies (10 tickers)
- **^VIX, ^VIX9D, ^VVIX** - Volatility complex
- **UUP** - Dollar index ETF
- **GLD** - Gold
- **USO** - Oil
- **HYG, LQD** - Credit ETFs
- **TLT** - Long-term bonds
- **RSP** - Equal-weight S&P (breadth)

### Events Calendar
- **Month/quarter end** - Last trading day
- **Options expiry week** - Week of 3rd Friday
- **FOMC** - Fed meeting days
- **CPI** - CPI release days
- **NFP** - Non-farm payrolls release days

## Feature Categories (100+ features)

### Technical (from OHLCV)
- Returns: 1d, 5d, 10d, 20d log returns
- Volatility: rolling std (5/10/20/60)
- MA: SMA/EMA (5/10/20/50/200), crossovers
- Momentum: RSI(14), MACD(12,26,9)
- Range: ATR(14), true range, high-low %, close-open %
- Volume: z-score, change %, OBV
- Drawdown: 20d, 60d rolling max drawdown

### Macro Context (FRED derived)
- Yield curve slope (DGS10 - DGS2)
- Rate changes (1d, 5d)
- Credit spread level and changes
- Liquidity regime (Fed balance sheet expanding/contracting)
- RRP usage changes

### Risk Proxies
- VIX level, changes (1d, 5d), pct changes
- VIX term structure (VIX - VIX9D)
- Dollar returns (1d, 5d, 20d)
- Gold/Oil returns (1d, 5d, 20d)
- Credit returns (HYG, LQD)
- HYG vs SPY relative strength
- HYG-SPY rolling correlation (20d)
- TLT returns

### Breadth/Relative Strength
- RSP/SPY ratio, MA, z-score
- QQQ/SPY ratio, MA, z-score
- IWM/SPY ratio, MA, z-score

### Calendar
- Day of week, month
- Month/quarter end flags
- Options expiry week flag
- FOMC/CPI/NFP event flags
- Days since last trading day

## Timezone Alignment (CRITICAL)

All data aligned to **America/New_York** timezone:

1. **Daily bars** represent NYSE close (4:00 PM ET)
2. **FRED observations** available at EOD of observation date (ET)
3. **Features at date t** use ONLY data available by market close on t
4. **Labels** use future closes (shifted forward, no leakage)
5. **Event flags** indicate event occurs on date t (not outcome)
6. **Sparse series** (weekly/monthly) forward-filled with `days_since_update` tracking

## Leakage Prevention

- Labels computed with forward shift: `y_1d = close[t+1] > close[t]`
- Last 5 rows dropped from labels (future not available)
- All features strictly use past/current data only
- Event flags are binary indicators (no surprise values)
- Macro forward-fill limited to 5-7 days max gap
- `days_since_update` column tracks stale data

## Setup & Execution

### 1. Environment Variables
```powershell
setx SUPABASE_DB_URL "postgresql://postgres:<password>@<host>:5432/postgres"
setx FRED_API_KEY "your_fred_api_key"
```

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Run Migrations
Apply in order:
- `migrations/001_init_schema.sql`
- `migrations/002_add_context_data.sql`

### 4. Validate Setup
```powershell
python validate_setup.py
```

### 5. Run ETL
```powershell
python -m etl.main --start 2000-01-01 --end 2025-12-12 --mode backfill
```

## Data Quality

**Idempotency**: Upserts on `(asset_id, date)` and `(series_id, date)` uniqueness

**Missing Data Handling**:
- FRED sparse series forward-filled within max gap
- `days_since_update` tracks forward-fill age
- Prefer leaving NaN over stale data (model can handle)

**Validation**:
- NYSE calendar ensures valid trading days
- Date alignment validates ET timezone
- Label truncation prevents leakage

## Query Examples

See `example_queries.sql` for:
- Flattened modeling dataset query
- Data coverage checks
- Macro series validation
- Events calendar inspection

## Performance Considerations

**Backfill time** (2000-2025, ~6,000 trading days):
- ETF OHLCV: ~1 min per symbol
- FRED series: ~30 sec per series
- Proxies: ~1 min per ticker
- Feature computation: ~2-3 min per symbol
- **Total: ~15-20 minutes** for full backfill

**Storage** (per symbol):
- Daily bars: ~6k rows
- Features: ~6k rows × JSONB (~200 KB per row)
- Labels: ~6k rows
- **Total: ~10-15 MB per symbol**

**Incremental updates** (daily):
- Last 5 trading days: <1 minute

## Next Steps

1. **Feature selection**: Use correlation analysis, mutual information, SHAP values
2. **Feature engineering**: Cross-feature interactions (VIX × yield curve, etc)
3. **Target engineering**: Multi-class (up/down/flat), regression (return magnitude)
4. **Model training**: LightGBM, XGBoost, neural networks
5. **Backtesting**: Walk-forward validation with proper train/test splits
6. **Production**: Incremental ETL via scheduler (daily 5 PM ET)

## Files Created

### Migrations
- `migrations/001_init_schema.sql` - Initial schema
- `migrations/002_add_context_data.sql` - Context data extensions

### ETL Modules
- `etl/__init__.py`
- `etl/config.py`
- `etl/supabase_client.py`
- `etl/extract_yf.py`
- `etl/extract_fred.py`
- `etl/extract_proxies.py`
- `etl/build_events.py`
- `etl/transform_features.py`
- `etl/transform_features_context.py`
- `etl/transform_labels.py`
- `etl/load_db.py`
- `etl/main.py`

### Documentation
- `README.md`
- `PROJECT_SUMMARY.md` (this file)
- `example_queries.sql`
- `.env.example`
- `requirements.txt`
- `validate_setup.py`
- `.gitignore`

## Dependencies

- pandas >= 2.2.0
- numpy >= 1.26.0
- yfinance >= 0.2.40
- psycopg2-binary >= 2.9.9
- fredapi >= 0.5.1
- pandas-market-calendars >= 4.3.3
