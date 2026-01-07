# ETF Classification Model - 1-Day Trading Signals

Triple-barrier classification system for SPY, QQQ, DIA, IWM using 83 optimized features and volatility-aware thresholds.

**Target:** `y_class_1d` → -1 (Sell), 0 (Hold), 1 (Buy) using ±0.25 volatility threshold

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


