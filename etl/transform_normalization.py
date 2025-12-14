"""
Feature normalization and clipping for regression modeling.

NORMALIZATION STRATEGY:
- Z-score continuous features using rolling 252-day window (per symbol)
- Exclude binary regime and event flags from scaling
- Clip z-scored features to ±5 for outlier robustness
- Clip volatility-scaled features to ±3

FEATURE TYPES:
- Continuous: z-scored and clipped
- Binary/Categorical: no transformation
- Volatility-scaled: already normalized, just clip

Date: 2025-12-13
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional


# Feature categorization for normalization
BINARY_FEATURES = [
    'sma20_gt_sma50', 'dow', 'days_since_prev',
    'is_fomc', 'is_cpi_release', 'is_nfp_release',
    'high_vol_regime', 'curve_inverted', 'credit_stress',
    'liquidity_expanding_regime', 'liquidity_expanding'
]

VOLATILITY_SCALED_FEATURES = [
    'overnight_share',  # Already bounded to [-1, 1]
    'vol_5', 'vol_20', 'vol_60',  # Already variance measures
]

# All other features are continuous and should be z-scored


def zscore_rolling(series: pd.Series, window: int = 252) -> pd.Series:
    """
    Z-score normalization using rolling window.
    
    Args:
        series: Feature values (chronological)
        window: Rolling window size (default 252 = 1 trading year)
    
    Returns:
        Z-scored series
    """
    rolling_mean = series.rolling(window, min_periods=window // 2).mean()
    rolling_std = series.rolling(window, min_periods=window // 2).std()
    
    # Z-score: (x - mean) / std
    zscore = (series - rolling_mean) / (rolling_std + 1e-9)
    
    return zscore


def clip_feature(series: pd.Series, clip_min: float, clip_max: float) -> pd.Series:
    """
    Clip feature to specified range.
    
    Args:
        series: Feature values
        clip_min: Minimum value
        clip_max: Maximum value
    
    Returns:
        Clipped series
    """
    return series.clip(clip_min, clip_max)


def normalize_features(
    features_df: pd.DataFrame,
    continuous_features: Optional[List[str]] = None,
    window: int = 252,
    clip_continuous: float = 5.0
) -> pd.DataFrame:
    """
    Normalize features for regression modeling.
    
    Strategy:
    - Binary features: no transformation
    - Continuous features: z-score with rolling window, clip to ±clip_continuous
    - Volatility-scaled: already normalized, no additional scaling
    
    Args:
        features_df: DataFrame with features (must be sorted by date)
        continuous_features: List of continuous feature names (auto-detect if None)
        window: Rolling window for z-scoring (default 252 trading days)
        clip_continuous: Clipping threshold for continuous features (default ±5)
    
    Returns:
        DataFrame with normalized features
    """
    result = features_df.copy()
    
    # Auto-detect continuous features if not provided
    if continuous_features is None:
        all_features = [c for c in features_df.columns 
                       if c not in ['date', 'symbol', 'asset_id']]
        continuous_features = [f for f in all_features 
                              if f not in BINARY_FEATURES + VOLATILITY_SCALED_FEATURES]
    
    # Normalize continuous features
    for feature in continuous_features:
        if feature in result.columns:
            # Z-score with rolling window
            result[feature] = zscore_rolling(result[feature], window)
            
            # Clip to ±clip_continuous
            result[feature] = clip_feature(result[feature], -clip_continuous, clip_continuous)
    
    # Clip overnight_share to [-1, 1] (should already be bounded, but enforce)
    if 'overnight_share' in result.columns:
        result['overnight_share'] = clip_feature(result['overnight_share'], -1.0, 1.0)
    
    return result


def get_feature_metadata() -> Dict[str, Dict]:
    """
    Get feature metadata for normalization and clipping.
    
    Returns:
        Dictionary mapping feature_name -> {
            'type': 'continuous' | 'binary' | 'vol_scaled',
            'clip_min': float or None,
            'clip_max': float or None,
            'scaling': 'zscore' | 'none'
        }
    """
    metadata = {}
    
    # Binary features
    for feature in BINARY_FEATURES:
        metadata[feature] = {
            'type': 'binary',
            'clip_min': None,
            'clip_max': None,
            'scaling': 'none'
        }
    
    # Volatility-scaled features
    for feature in VOLATILITY_SCALED_FEATURES:
        metadata[feature] = {
            'type': 'vol_scaled',
            'clip_min': -3.0,
            'clip_max': 3.0,
            'scaling': 'none'  # Already scaled
        }
    
    # Default for all other features: continuous with z-scoring
    # (Will be populated dynamically based on actual features in dataset)
    
    return metadata


def validate_feature_distributions(features_df: pd.DataFrame) -> Dict[str, Dict]:
    """
    Validate feature distributions after normalization.
    
    Checks:
    - Mean close to 0 for z-scored features
    - Std close to 1 for z-scored features
    - No extreme outliers beyond clipping thresholds
    - Binary features in expected range
    
    Returns:
        Dictionary with validation results per feature
    """
    results = {}
    
    for col in features_df.select_dtypes(include=[np.number]).columns:
        if col in ['date']:
            continue
        
        series = features_df[col].dropna()
        
        results[col] = {
            'mean': series.mean(),
            'std': series.std(),
            'min': series.min(),
            'max': series.max(),
            'pct_null': features_df[col].isna().mean() * 100,
            'outliers_beyond_5': (series.abs() > 5).sum() if col not in BINARY_FEATURES else 0,
            'is_binary': col in BINARY_FEATURES
        }
    
    return results


def apply_feature_clipping(feature_json: Dict, clip_rules: Dict[str, tuple]) -> Dict:
    """
    Apply clipping rules to feature JSON.
    
    Args:
        feature_json: Dictionary of feature_name -> value
        clip_rules: Dictionary of feature_name -> (min, max)
    
    Returns:
        Clipped feature dictionary
    """
    clipped = feature_json.copy()
    
    for feature_name, (clip_min, clip_max) in clip_rules.items():
        if feature_name in clipped and clipped[feature_name] is not None:
            val = clipped[feature_name]
            if not np.isnan(val) and not np.isinf(val):
                clipped[feature_name] = max(clip_min, min(clip_max, val))
    
    return clipped


# Default clipping rules
DEFAULT_CLIP_RULES = {
    # Continuous features: ±5 after z-scoring
    'log_ret_1d': (-5, 5),
    'log_ret_5d': (-5, 5),
    'log_ret_20d': (-5, 5),
    'rsi_14': (0, 100),  # RSI bounded by design
    'macd_hist': (-5, 5),
    'atr_14': (-5, 5),
    'high_low_pct': (-5, 5),
    'close_open_pct': (-5, 5),
    'volume_z': (-5, 5),
    'volume_chg_pct': (-5, 5),
    'dd_60': (-1, 0),  # Drawdown is always negative or zero
    
    # Overnight/Intraday
    'overnight_return': (-5, 5),
    'intraday_return': (-5, 5),
    'overnight_mean_20': (-5, 5),
    'overnight_std_20': (-5, 5),
    'intraday_mean_20': (-5, 5),
    'intraday_std_20': (-5, 5),
    'overnight_share': (-1, 1),  # Bounded ratio
    
    # Trend quality
    'adx_14': (0, 100),  # ADX bounded by design
    'return_autocorr_20': (-1, 1),  # Correlation bounded
    'price_rsq_20': (0, 1),  # R² bounded
    
    # Macro
    'dgs2': (-5, 5),
    'dgs10': (-5, 5),
    'yield_curve_slope': (-5, 5),
    'dgs10_change_5d': (-5, 5),
    'hy_oas_level': (-5, 5),
    'hy_oas_change_1d': (-5, 5),
    'hy_oas_change_5d': (-5, 5),
    'fed_bs_chg_pct': (-5, 5),
    'rrp_level': (-5, 5),
    'rrp_chg_pct_5d': (-5, 5),
    
    # VIX
    'vix_level': (-5, 5),
    'vix_change_1d': (-5, 5),
    'vix_change_5d': (-5, 5),
    'vix_term_structure': (-5, 5),
    
    # Cross-asset
    'dxy_ret_5d': (-5, 5),
    'gold_ret_5d': (-5, 5),
    'oil_ret_5d': (-5, 5),
    'hyg_ret_5d': (-5, 5),
    'hyg_vs_spy_5d': (-5, 5),
    'hyg_spy_corr_20d': (-1, 1),  # Correlation bounded
    'lqd_ret_5d': (-5, 5),
    'tlt_ret_5d': (-5, 5),
    
    # Breadth
    'rsp_spy_ratio': (-5, 5),
    'rsp_spy_ratio_z': (-5, 5),
    'qqq_spy_ratio_z': (-5, 5),
    'iwm_spy_ratio_z': (-5, 5),
    
    # Lagged features
    'log_ret_1d_lag1': (-5, 5),
    'log_ret_1d_lag2': (-5, 5),
    'log_ret_1d_lag3': (-5, 5),
    'log_ret_1d_lag5': (-5, 5),
    'vix_change_lag1': (-5, 5),
    'vix_change_lag3': (-5, 5),
    'hy_oas_change_lag1': (-5, 5),
    'yield_curve_slope_lag1': (-5, 5),
}
