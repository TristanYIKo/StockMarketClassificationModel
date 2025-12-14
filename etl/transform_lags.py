"""
Apply temporal lags to features for regression models.

CRITICAL: Lagging provides memory to the model.
- Lags are applied AFTER base features are computed
- No forward information is introduced (past → present only)
- Useful for capturing momentum, mean reversion, regime persistence

Example:
  log_ret_1d_lag1 at date t = log_ret_1d at date t-1
  This gives the model memory of yesterday's return.
"""

import pandas as pd
import numpy as np
from typing import Dict, List


# Define which features to lag and by how many periods
LAG_SPEC = {
    # Return lags (momentum/mean reversion signals)
    "log_ret_1d": [1, 2, 3, 5],
    
    # VIX change lags (vol regime persistence)
    "vix_change_1d": [1, 3],
    
    # Credit spread lags (credit regime persistence)
    "hy_oas_change_1d": [1],
    
    # Yield curve lags (rate regime persistence)
    "yield_curve_slope": [1],
}


def apply_lags(features_df: pd.DataFrame, lag_spec: Dict[str, List[int]] = None) -> pd.DataFrame:
    """
    Apply temporal lags to specified features.
    
    Args:
        features_df: DataFrame with base features (must be chronological by date)
        lag_spec: Dict mapping feature name → list of lag periods
                  If None, uses LAG_SPEC constant
    
    Returns:
        DataFrame with lagged features added (original features kept)
    
    Example:
        df = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'log_ret_1d': [0.01, -0.005, 0.02]
        })
        result = apply_lags(df)
        # Adds: log_ret_1d_lag1, log_ret_1d_lag2, etc.
    """
    if lag_spec is None:
        lag_spec = LAG_SPEC
    
    result = features_df.copy()
    
    for feature, lags in lag_spec.items():
        if feature not in result.columns:
            print(f"Warning: Feature '{feature}' not found in DataFrame, skipping lags")
            continue
        
        for lag_n in lags:
            lag_col_name = f"{feature}_lag{lag_n}"
            result[lag_col_name] = result[feature].shift(lag_n)
    
    return result


def validate_lag_no_leakage(df: pd.DataFrame, date_col: str = "date") -> bool:
    """
    Validate that lagged features don't introduce future information.
    
    Checks:
    1. Lagged columns have expected NaN pattern (first N rows)
    2. Non-NaN values in lag columns match historical values
    
    Returns True if validation passes.
    """
    lag_cols = [c for c in df.columns if "_lag" in c]
    
    if not lag_cols:
        print("No lagged columns found")
        return True
    
    all_ok = True
    
    for col in lag_cols:
        # Extract lag number
        lag_n = int(col.split("_lag")[-1])
        base_col = col.replace(f"_lag{lag_n}", "")
        
        if base_col not in df.columns:
            continue
        
        # Check first N rows are NaN
        first_n = df[col].iloc[:lag_n]
        if not first_n.isna().all():
            print(f"Warning: {col} should have NaN in first {lag_n} rows")
            all_ok = False
        
        # Check values match shifted base column
        lagged_values = df[col].iloc[lag_n:].values
        original_values = df[base_col].iloc[:-lag_n].values
        
        # Allow for floating point precision
        if not np.allclose(lagged_values, original_values, rtol=1e-5, atol=1e-8, equal_nan=True):
            print(f"Warning: {col} values don't match shifted {base_col}")
            all_ok = False
    
    if all_ok:
        print(f"✓ Lag validation passed for {len(lag_cols)} lagged features")
    
    return all_ok


def get_lagged_feature_names(lag_spec: Dict[str, List[int]] = None) -> List[str]:
    """
    Get list of lagged feature names that will be created.
    
    Useful for feature manifests and documentation.
    """
    if lag_spec is None:
        lag_spec = LAG_SPEC
    
    lagged_names = []
    for feature, lags in lag_spec.items():
        for lag_n in lags:
            lagged_names.append(f"{feature}_lag{lag_n}")
    
    return lagged_names


if __name__ == "__main__":
    # Example usage
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=10),
        "log_ret_1d": np.random.randn(10) * 0.01,
        "vix_change_1d": np.random.randn(10) * 2.0,
        "hy_oas_change_1d": np.random.randn(10) * 10.0,
        "yield_curve_slope": np.random.randn(10) * 50.0,
    })
    
    print("Original DataFrame:")
    print(df.head())
    
    result = apply_lags(df)
    print(f"\nAfter applying lags ({len(result.columns) - len(df.columns)} new columns):")
    print(result.head(6))
    
    print(f"\nLagged features: {get_lagged_feature_names()}")
    
    validate_lag_no_leakage(result)
