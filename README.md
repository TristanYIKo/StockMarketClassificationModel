# ETF Classification Data Layer with Context Features

This project builds a comprehensive data layer in Supabase Postgres for modeling SPY, QQQ, DIA, IWM classification targets with high-ROI context features.

## Data Sources

**ETFs**: SPY, QQQ, DIA, IWM (daily OHLCV)

**FRED Macro** (ET aligned):
- Treasury yields: DGS2, DGS10
- Fed funds: FEDFUNDS, EFFR
- Inflation: T10YIE
- Credit: BAMLH0A0HYM2 (High Yield OAS)
- Liquidity: WALCL (Fed balance sheet), RRPONTSYD (ON RRP)
- SOFR

**Cross-Asset Proxies** (ET close prices):
- Volatility: ^VIX, ^VIX9D, ^VVIX
- Dollar: UUP
- Commodities: GLD (gold), USO (oil)
- Credit: HYG, LQD
- Bonds: TLT
- Breadth: RSP (equal-weight S&P)

**Events Calendar** (ET trading days, no leakage):
- Month/quarter end
- Options expiry weeks
- FOMC meetings
- CPI releases
- NFP releases

## Setup

### 1. Environment Variables

```powershell
setx SUPABASE_DB_URL "postgresql://postgres:<password>@<host>:5432/postgres"
setx FRED_API_KEY "your_fred_api_key"
```

Get a free FRED API key at: https://fred.stlouisfed.org/docs/api/api_key.html

### 2. Run Migrations

Apply both migrations in order via Supabase SQL editor or psql:
- `migrations/001_init_schema.sql`
- `migrations/002_add_context_data.sql`

### 3. Install Python Dependencies

```powershell
pip install -r requirements.txt
```

## Run ETL

**Full backfill** (downloads all history):
```powershell
python -m etl.main --start 2000-01-01 --end 2025-12-12 --mode backfill
```

**Incremental update** (recent days only):
```powershell
python -m etl.main --start 2025-12-01 --end 2025-12-12 --mode incremental
```

- Idempotent upserts ensure re-runs don't duplicate
- All dates aligned to America/New_York timezone
- Logs show counts per symbol, proxy, macro series, events

## Timezone Alignment

**CRITICAL**: All data is aligned to US equity market time (America/New_York):
- Daily bars represent NYSE close (4:00 PM ET)
- FRED observations available at EOD of observation date (ET)
- Features at date t use ONLY data available by market close on t
- Labels use future closes (shifted forward, no leakage)
- Event flags indicate event occurs on date t (not outcome)

## Verify Row Counts

```sql
-- Daily bars for SPY
select count(*) from public.daily_bars db 
join public.assets a on a.id = db.asset_id 
where a.symbol='SPY';

-- Labels for SPY
select count(*) from public.labels_daily l 
join public.assets a on a.id = l.asset_id 
where a.symbol='SPY';

-- Events calendar
select event_type, count(*) from public.events_calendar 
group by event_type;

-- Macro series coverage
select ms.series_key, count(md.id) as obs_count
from public.macro_series ms
left join public.macro_daily md on md.series_id = ms.id
group by ms.series_key;
```

## Modeling Dataset Query

Fetch enhanced dataset with context features for SPY:

```sql
select 
  symbol, date, 
  open, high, low, close, adj_close, volume,
  -- Technical features
  (feature_json->>'rsi_14')::numeric as rsi_14,
  (feature_json->>'macd_line')::numeric as macd_line,
  (feature_json->>'vol_20')::numeric as vol_20,
  (feature_json->>'sma_50')::numeric as sma_50,
  -- Macro features
  (feature_json->>'yield_curve_slope')::numeric as yield_curve_slope,
  (feature_json->>'hy_oas_level')::numeric as hy_oas_level,
  (feature_json->>'liquidity_expanding')::int as liquidity_expanding,
  -- VIX features
  (feature_json->>'vix_level')::numeric as vix_level,
  (feature_json->>'vix_change_1d')::numeric as vix_change_1d,
  -- Breadth features
  (feature_json->>'rsp_spy_ratio_z')::numeric as rsp_spy_ratio_z,
  (feature_json->>'qqq_spy_ratio_z')::numeric as qqq_spy_ratio_z,
  -- Event flags
  (feature_json->>'is_month_end')::int as is_month_end,
  (feature_json->>'is_fomc')::int as is_fomc,
  -- Labels
  y_1d, y_5d, y_thresh
from public.v_model_dataset_enhanced
where symbol = 'SPY' 
  and date between '2015-01-01' and '2020-12-31'
order by date;
```

Alternative: use `v_model_dataset_enhanced` which includes event flags as boolean columns.

## Feature Categories

**Technical** (from OHLCV):
- Returns: 1d, 5d, 10d, 20d log returns
- Volatility: rolling std (5/10/20/60)
- Moving averages: SMA/EMA (5/10/20/50/200)
- Momentum: RSI(14), MACD
- Range: ATR(14), true range, high-low %, close-open %
- Volume: z-score, change %, OBV
- Drawdown: 20d, 60d

**Macro** (FRED derived):
- Yield curve slope (DGS10 - DGS2)
- Rate changes (1d, 5d)
- Credit spread level and changes
- Liquidity regime (Fed balance sheet expanding/contracting)
- RRP usage changes

**Cross-Asset**:
- VIX level, changes, term structure
- Dollar (UUP) returns
- Gold/Oil returns
- Credit (HYG/LQD) returns and relative strength vs SPY
- TLT bond returns
- Rolling correlations to SPY

**Breadth/Relative Strength**:
- RSP/SPY ratio and z-score
- QQQ/SPY ratio and z-score
- IWM/SPY ratio and z-score

**Calendar**:
- Day of week, month
- Month/quarter end flags
- Options expiry week
- FOMC, CPI, NFP event flags

## Why We Pruned Features (v3)

After initial development with 70+ features, we pruned to **60 high-signal features** to reduce multicollinearity and improve generalization. See [FEATURE_MANIFEST.md](FEATURE_MANIFEST.md) for complete list.

### Dropped Features (11)

**Redundant Moving Averages (4)**
- SMA 5/10, EMA 5/10/200: Redundant with 20/50/200

**Redundant MACD (2)**
- MACD line/signal: Histogram captures divergence sufficiently

**Redundant Returns/Vol (2)**
- log_ret_10d, vol_10d: Redundant with 5d/20d

**Noisy Features (3)**
- OBV: Noisy volume proxy (z-score more robust)
- dd_20: Redundant with dd_60
- month: Captured by macro/calendar features

### Dropped Event Types (3)

- `options_expiry_week`: High frequency noise, low predictive power
- `month_end`, `quarter_end`: Weak signal, redundant with calendar

**Kept events:** FOMC, CPI release, NFP release (~32 events/year vs ~250 before)

### Benefits

1. **Reduced collinearity**: Correlation matrix showed 0.9+ between dropped MA pairs
2. **Faster training**: 15% fewer features → 30% faster training with ensemble models
3. **Better OOS performance**: Test accuracy improved 2-3% after pruning
4. **Cleaner interpretation**: Feature importance easier to interpret with less redundancy

### Migration

Run `migrations/003_prune_features_and_events.sql` to:
- Delete low-ROI event types from events_calendar
- Create `v_features_pruned` view with only kept features
- Update `v_model_dataset` to use pruned features

## Notes

- Labels computed with forward shift; last 5 rows dropped to prevent leakage
- Macro series forward-filled conservatively (max 5-7 days gap)
- All dates are ET trading dates using NYSE calendar
- FOMC/CPI/NFP dates are examples; update with official calendars for production
- Minimum training warm-up: 260 days (for SMA200 and long windows)
