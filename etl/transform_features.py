import numpy as np
import pandas as pd

# Helper indicators

def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    up = np.maximum(delta, 0.0)
    down = np.maximum(-delta, 0.0)
    roll_up = pd.Series(up).rolling(window).mean()
    roll_down = pd.Series(down).rolling(window).mean()
    rs = roll_up / (roll_down + 1e-12)
    return 100.0 - (100.0 / (1.0 + rs))


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    return true_range(df).rolling(window).mean()


def obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff())
    return (direction.fillna(0.0) * df["volume"]).cumsum()


def adx(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """
    Average Directional Index (ADX) - measures trend strength.
    
    High ADX (>25) = strong trend
    Low ADX (<20) = choppy/ranging
    """
    # Calculate +DM and -DM
    high_diff = df["high"].diff()
    low_diff = -df["low"].diff()
    
    plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
    minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)
    
    # Smooth with EMA
    tr = true_range(df)
    atr_val = tr.ewm(span=window, adjust=False).mean()
    
    plus_di = 100 * pd.Series(plus_dm).ewm(span=window, adjust=False).mean() / (atr_val + 1e-9)
    minus_di = 100 * pd.Series(minus_dm).ewm(span=window, adjust=False).mean() / (atr_val + 1e-9)
    
    # DX = difference between DIs
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
    
    # ADX = smoothed DX
    adx_val = dx.ewm(span=window, adjust=False).mean()
    return adx_val


def return_autocorr(returns: pd.Series, window: int = 20) -> pd.Series:
    """
    Rolling autocorrelation of returns (lag 1).
    
    Positive = momentum
    Negative = mean reversion
    Near zero = random walk
    """
    return returns.rolling(window).apply(lambda x: x.autocorr(lag=1) if len(x) >= 2 else np.nan, raw=False)


def price_rsquared(price: pd.Series, window: int = 20) -> pd.Series:
    """
    Rolling R² of price vs time (linear regression).
    
    High R² = strong linear trend
    Low R² = choppy/non-trending
    """
    def compute_rsq(x):
        if len(x) < 5:
            return np.nan
        y = x.values
        X = np.arange(len(y))
        # Simple linear regression
        X_mean = X.mean()
        y_mean = y.mean()
        
        ss_tot = np.sum((y - y_mean) ** 2)
        if ss_tot < 1e-9:
            return 0.0
        
        slope = np.sum((X - X_mean) * (y - y_mean)) / (np.sum((X - X_mean) ** 2) + 1e-9)
        intercept = y_mean - slope * X_mean
        y_pred = slope * X + intercept
        
        ss_res = np.sum((y - y_pred) ** 2)
        r_squared = 1 - (ss_res / ss_tot)
        return np.clip(r_squared, 0, 1)
    
    return price.rolling(window).apply(compute_rsq, raw=False)


# OPTIMIZED FEATURE MANIFEST (v2.0 - Regression Optimized)
# 
# TECHNICAL (22): log_ret_1d, log_ret_5d, log_ret_20d, rsi_14, macd_hist, 
#                 vol_5, vol_20, vol_60, atr_14, high_low_pct, close_open_pct,
#                 sma_20, sma_50, sma_200, ema_20, ema_50, sma20_gt_sma50,
#                 volume_z, volume_chg_pct, dd_60, dow, days_since_prev
#
# OVERNIGHT/INTRADAY (7): overnight_return, intraday_return, overnight_mean_20,
#                         overnight_std_20, intraday_mean_20, intraday_std_20,
#                         overnight_share (FIXED for numerical stability)
#
# TREND QUALITY (3): adx_14, return_autocorr_20, price_rsq_20
#
# MACRO (11): dgs2, dgs10, yield_curve_slope, dgs10_change_5d (REMOVED: dgs10_change_1d),
#             hy_oas_level, hy_oas_change_1d, hy_oas_change_5d, liquidity_expanding,
#             fed_bs_chg_pct, rrp_level, rrp_chg_pct_5d
#
# VIX (4): vix_level, vix_change_1d, vix_change_5d, vix_term_structure
#
# CROSS-ASSET (8): dxy_ret_5d, gold_ret_5d, oil_ret_5d, hyg_ret_5d, hyg_vs_spy_5d,
#                  hyg_spy_corr_20d, lqd_ret_5d, tlt_ret_5d
#
# BREADTH (4): rsp_spy_ratio, rsp_spy_ratio_z, qqq_spy_ratio_z, iwm_spy_ratio_z
#
# EVENTS (3): is_fomc, is_cpi_release, is_nfp_release
#
# DROPPED FEATURES (redundancy reduction):
# - dgs10_change_1d: redundant with dgs10_change_5d
# - SMA 5/10, EMA 5/10/200: redundant with kept MAs
# - MACD line/signal: redundant with histogram
# - log_ret_10d, vol_10d: redundant with 5d/20d
# - OBV: noisy volume proxy, redundant with volume_z
# - dd_20: redundant with dd_60

KEPT_FEATURES = [
    # Returns / momentum
    "log_ret_1d", "log_ret_5d", "log_ret_20d", "rsi_14",
    # MACD
    "macd_hist",
    # Volatility / range
    "vol_5", "vol_20", "vol_60", "atr_14", "high_low_pct", "close_open_pct",
    # Moving averages
    "sma_20", "sma_50", "sma_200", "ema_20", "ema_50", "sma20_gt_sma50",
    # Volume
    "volume_z", "volume_chg_pct",
    # Drawdown
    "dd_60",
    # Calendar
    "dow", "days_since_prev",
    # Overnight/Intraday (NEW)
    "overnight_return", "intraday_return", 
    "overnight_mean_20", "overnight_std_20",
    "intraday_mean_20", "intraday_std_20", "overnight_share",
    # Trend Quality (NEW)
    "adx_14", "return_autocorr_20", "price_rsq_20"
]


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute pruned feature set (22 technical features).
    
    Dropped low-ROI / redundant features:
    - SMA 5/10, EMA 5/10/200
    - MACD line/signal
    - log_ret_10d, vol_10d
    - OBV, dd_20
    - month, is_month_end, is_quarter_end
    """
    out = df.copy()
    
    # Returns (keep 1d, 5d, 20d; drop 10d)
    out["log_ret_1d"] = np.log(out["close"]).diff(1)
    out["log_ret_5d"] = np.log(out["close"]).diff(5)
    out["log_ret_20d"] = np.log(out["close"]).diff(20)

    # Volatility (keep 5, 20, 60; drop 10)
    for w in [5, 20, 60]:
        out[f"vol_{w}"] = out["log_ret_1d"].rolling(w).std()

    # Moving averages (keep 20, 50, 200 for SMA; 20, 50 for EMA)
    for w in [20, 50, 200]:
        out[f"sma_{w}"] = out["close"].rolling(w).mean()
    
    for w in [20, 50]:
        out[f"ema_{w}"] = ema(out["close"], w)

    out["sma20_gt_sma50"] = (out["sma_20"] > out["sma_50"]).astype(int)

    # RSI
    out["rsi_14"] = rsi(out["close"], 14)
    
    # MACD (keep histogram only)
    _, _, hist = macd(out["close"], 12, 26, 9)
    out["macd_hist"] = hist

    # ATR and range
    out["tr"] = true_range(out)
    out["atr_14"] = atr(out, 14)
    out["high_low_pct"] = (out["high"] - out["low"]) / out["close"].replace(0, np.nan)
    out["close_open_pct"] = (out["close"] - out["open"]) / out["open"].replace(0, np.nan)

    # Volume features (drop OBV)
    vol_ma20 = out["volume"].rolling(20).mean()
    vol_std20 = out["volume"].rolling(20).std()
    out["volume_z"] = (out["volume"] - vol_ma20) / (vol_std20 + 1e-9)
    out["volume_chg_pct"] = out["volume"].pct_change()

    # Drawdown (keep 60d only)
    out["rolling_max_60"] = out["close"].rolling(60).max()
    out["dd_60"] = (out["close"] / out["rolling_max_60"] - 1.0)

    # Calendar features (keep day of week and days since prev; drop month, month_end, quarter_end)
    out["dow"] = pd.to_datetime(out["date"]).dt.weekday
    out["days_since_prev"] = pd.to_datetime(out["date"]).diff().dt.days.fillna(1)

    # ========================================
    # OVERNIGHT / INTRADAY FEATURES (HIGH ROI)
    # ========================================
    # Split daily returns into overnight (gap) vs intraday (session) components
    prev_close = out["close"].shift(1)
    
    # Overnight return: today_open - yesterday_close
    out["overnight_return"] = np.log(out["open"] / prev_close)
    
    # Intraday return: today_close - today_open
    out["intraday_return"] = np.log(out["close"] / out["open"])
    
    # Rolling statistics of overnight/intraday
    out["overnight_mean_20"] = out["overnight_return"].rolling(20).mean()
    out["overnight_std_20"] = out["overnight_return"].rolling(20).std()
    out["intraday_mean_20"] = out["intraday_return"].rolling(20).mean()
    out["intraday_std_20"] = out["intraday_return"].rolling(20).std()
    
    # Overnight share: ratio of overnight vs total movement (numerically stable)
    # Formula: overnight / (|overnight| + |intraday| + epsilon)
    # This prevents division by zero and handles near-zero returns gracefully
    # Clip to [-1, 1] as overnight cannot exceed total movement
    total_movement = out["overnight_return"].abs() + out["intraday_return"].abs() + 1e-6
    out["overnight_share"] = out["overnight_return"] / total_movement
    out["overnight_share"] = out["overnight_share"].clip(-1, 1)  # bounded ratio

    # ========================================
    # TREND QUALITY FEATURES (REGRESSION-FRIENDLY)
    # ========================================
    # ADX: trend strength (>25 = strong trend, <20 = chop)
    out["adx_14"] = adx(out, 14)
    
    # Return autocorrelation: momentum vs mean reversion
    out["return_autocorr_20"] = return_autocorr(out["log_ret_1d"], 20)
    
    # Price R²: linear trend fit quality
    out["price_rsq_20"] = price_rsquared(out["close"], 20)

    return out
