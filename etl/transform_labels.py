"""
Compute regression and classification targets with volatility scaling (v2.0 OPTIMIZED).

CRITICAL: All targets use FORWARD-SHIFTED data (no leakage).
- future_1d = close.shift(-1) uses NEXT day's close
- future_5d = close.shift(-5) uses 5 days ahead close

PRIMARY REGRESSION TARGETS (use these):
- primary_target: Alias for y_1d_vol_clip (default for modeling)
- y_1d_vol_clip: 1d vol-scaled + clipped to ±3 (RECOMMENDED)
- y_5d_vol_clip: 5d vol-scaled + clipped to ±3 (secondary)

Diagnostic regression targets (for research):
- y_1d_raw, y_5d_raw: Raw log returns
- y_1d_vol, y_5d_vol: Volatility-scaled (unclipped)
- y_1d_clipped, y_5d_clipped: Clipped raw returns

Classification targets (legacy):
- y_1d, y_5d, y_thresh: Binary up/down labels
"""

import numpy as np
import pandas as pd


def compute_labels(
    close: pd.Series, 
    vol_20: pd.Series,  # 20-day realized volatility for scaling
    y_thresh: float = 0.002
) -> pd.DataFrame:
    """
    Compute regression-friendly targets with volatility scaling (v2.0 OPTIMIZED).
    
    PRIMARY TARGET: primary_target (y_1d_vol_clip)
    - Volatility-scaled 1-day return clipped to ±3σ
    - Use this for default modeling
    
    Args:
        close: Close prices (chronological)
        vol_20: 20-day rolling volatility (for scaling)
        y_thresh: Threshold for binary classification (default 0.2%)
    
    Returns:
        DataFrame with PRIMARY targets (primary_target, y_1d_vol_clip, y_5d_vol_clip)
        and diagnostic targets for comparison
    """
    # Forward-shifted closes (FUTURE data, no leakage)
    future_1d = close.shift(-1)
    future_5d = close.shift(-5)
    
    # Raw log returns (regression targets)
    y_1d_raw = np.log(future_1d / close)
    y_5d_raw = np.log(future_5d / close)
    
    # Volatility-scaled returns (heteroskedasticity adjustment)
    # Divide by realized vol to stabilize variance across time
    y_1d_vol = y_1d_raw / (vol_20 + 1e-9)  # avoid division by zero
    y_5d_vol = y_5d_raw / (vol_20 + 1e-9)
    
    # Clipped returns (robustness to outliers)
    # Clip to ±3 standard deviations of raw returns
    std_1d = y_1d_raw.std()
    std_5d = y_5d_raw.std()
    y_1d_clipped = y_1d_raw.clip(-3 * std_1d, 3 * std_1d)
    y_5d_clipped = y_5d_raw.clip(-3 * std_5d, 3 * std_5d)
    
    # PRIMARY TARGETS: Volatility-scaled AND clipped (best of both worlds)
    # Clip vol-scaled returns to ±3σ for outlier robustness
    y_1d_vol_clip = y_1d_vol.clip(-3.0, 3.0)
    y_5d_vol_clip = y_5d_vol.clip(-3.0, 3.0)
    
    # Primary target alias (for default modeling)
    primary_target = y_1d_vol_clip
    
    # Classification targets (legacy, for comparison)
    y_1d_class = (future_1d > close).astype(int)
    y_5d_class = (future_5d > close).astype(int)
    ret_1d = (future_1d / close - 1.0)
    y_thresh_class = (ret_1d > y_thresh).astype(int)
    
    labels = pd.DataFrame({
        # PRIMARY REGRESSION TARGETS (optimized)
        "primary_target": primary_target,
        "y_1d_vol_clip": y_1d_vol_clip,
        "y_5d_vol_clip": y_5d_vol_clip,
        
        # Diagnostic targets
        "y_1d_raw": y_1d_raw,
        "y_5d_raw": y_5d_raw,
        "y_1d_vol": y_1d_vol,
        "y_5d_vol": y_5d_vol,
        "y_1d_clipped": y_1d_clipped,
        "y_5d_clipped": y_5d_clipped,
        
        # Classification targets (LEGACY)
        "y_1d": y_1d_class,
        "y_5d": y_5d_class,
        "y_thresh": y_thresh_class,
    })
    
    # Drop last rows where future labels not available
    labels = labels.iloc[:-5] if len(labels) >= 5 else labels.iloc[0:0]
    return labels
