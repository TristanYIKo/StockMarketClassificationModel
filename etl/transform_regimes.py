"""
Compute explicit market regime flags for regression models.

REGIMES IMPROVE MODEL PERFORMANCE:
- Help models condition predictions on macro environment
- Binary flags are interpretable and stable
- Capture non-linear regime shifts that linear features miss

Four key regimes:
1. High volatility: VIX > 20 OR VIX > 75th percentile (60d rolling)
2. Inverted curve: DGS10 < DGS2 (recession signal)
3. Credit stress: HY OAS > 80th percentile (60d rolling)
4. Liquidity expanding: Fed balance sheet 4-week change > 0
"""

import pandas as pd
import numpy as np
from typing import Optional


def compute_high_vol_regime(vix_level: pd.Series, threshold: float = 20.0, window: int = 60) -> pd.Series:
    """
    High volatility regime flag.
    
    Triggers when:
    - VIX > 20 (absolute threshold, classic "fear" level)
    - OR VIX > 75th percentile of recent 60 days
    
    Args:
        vix_level: VIX index level
        threshold: Absolute VIX threshold (default 20)
        window: Rolling window for percentile (default 60d)
    
    Returns:
        Binary series (1 = high vol regime, 0 = normal)
    """
    # Absolute threshold
    high_vol_abs = vix_level > threshold
    
    # Relative threshold (75th percentile)
    rolling_75th = vix_level.rolling(window).quantile(0.75)
    high_vol_rel = vix_level > rolling_75th
    
    # Combine (either condition triggers)
    high_vol_regime = (high_vol_abs | high_vol_rel).astype(int)
    
    return high_vol_regime


def compute_inverted_curve_regime(DGS10: pd.Series, DGS2: pd.Series) -> pd.Series:
    """
    Inverted yield curve regime flag.
    
    Triggers when: DGS10 < DGS2 (long rates below short rates)
    
    Strong recession predictor historically.
    
    Args:
        DGS10: 10-year Treasury yield (%)
        DGS2: 2-year Treasury yield (%)
    
    Returns:
        Binary series (1 = inverted, 0 = normal/steep)
    """
    inverted = (DGS10 < DGS2).astype(int)
    return inverted


def compute_credit_stress_regime(hy_oas: pd.Series, window: int = 60, percentile: float = 0.80) -> pd.Series:
    """
    Credit stress regime flag.
    
    Triggers when: HY OAS > 80th percentile of recent 60 days
    
    High-yield spreads widen during credit stress.
    
    Args:
        hy_oas: High-yield option-adjusted spread (bps)
        window: Rolling window for percentile (default 60d)
        percentile: Percentile threshold (default 80th = 0.80)
    
    Returns:
        Binary series (1 = credit stress, 0 = normal)
    """
    rolling_pct = hy_oas.rolling(window).quantile(percentile)
    credit_stress = (hy_oas > rolling_pct).astype(int)
    return credit_stress


def compute_liquidity_regime(fed_balance_sheet: pd.Series, window: int = 20) -> pd.Series:
    """
    Liquidity expanding regime flag.
    
    Triggers when: Fed balance sheet 4-week (20 trading day) change > 0
    
    Expanding Fed balance sheet = liquidity injection (bullish for risk assets).
    Contracting = liquidity drain (bearish).
    
    Args:
        fed_balance_sheet: WALCL series (Fed balance sheet, billions)
        window: Window for change (default 20d = ~4 weeks)
    
    Returns:
        Binary series (1 = expanding, 0 = contracting)
    """
    change = fed_balance_sheet.diff(window)
    liquidity_expanding = (change > 0).astype(int)
    return liquidity_expanding


def compute_all_regimes(
    features_df: pd.DataFrame,
    vix_col: str = "vix_level",
    dgs10_col: str = "DGS10",
    dgs2_col: str = "DGS2",
    hy_oas_col: str = "hy_oas_level",
    fed_bs_col: str = "fed_bs_level",  # Need to add this to features
) -> pd.DataFrame:
    """
    Compute all regime flags and add to features DataFrame.
    
    Args:
        features_df: DataFrame with base features
        vix_col: Column name for VIX level
        dgs10_col: Column name for 10Y yield
        dgs2_col: Column name for 2Y yield
        hy_oas_col: Column name for HY OAS
        fed_bs_col: Column name for Fed balance sheet
    
    Returns:
        DataFrame with regime flags added
    """
    result = features_df.copy()
    
    # High vol regime
    if vix_col in result.columns:
        result["high_vol_regime"] = compute_high_vol_regime(result[vix_col])
    else:
        print(f"Warning: {vix_col} not found, skipping high_vol_regime")
        result["high_vol_regime"] = 0
    
    # Inverted curve regime
    if dgs10_col in result.columns and dgs2_col in result.columns:
        result["curve_inverted"] = compute_inverted_curve_regime(result[dgs10_col], result[dgs2_col])
    else:
        print(f"Warning: {dgs10_col} or {dgs2_col} not found, skipping curve_inverted")
        result["curve_inverted"] = 0
    
    # Credit stress regime
    if hy_oas_col in result.columns:
        result["credit_stress"] = compute_credit_stress_regime(result[hy_oas_col])
    else:
        print(f"Warning: {hy_oas_col} not found, skipping credit_stress")
        result["credit_stress"] = 0
    
    # Liquidity regime (use existing liquidity_expanding feature if available)
    # Otherwise compute from Fed balance sheet level
    if "liquidity_expanding" in result.columns:
        # Already have it from macro features
        result["liquidity_expanding_regime"] = result["liquidity_expanding"]
    elif fed_bs_col in result.columns:
        result["liquidity_expanding_regime"] = compute_liquidity_regime(result[fed_bs_col])
    else:
        print(f"Warning: Neither liquidity_expanding nor {fed_bs_col} found, skipping liquidity_expanding_regime")
        result["liquidity_expanding_regime"] = 0
    
    return result


def get_regime_summary(features_df: pd.DataFrame) -> pd.DataFrame:
    """
    Get summary statistics of regime flags.
    
    Useful for understanding regime frequency and co-occurrence.
    """
    regime_cols = [
        "high_vol_regime",
        "curve_inverted", 
        "credit_stress",
        "liquidity_expanding_regime"
    ]
    
    existing_cols = [c for c in regime_cols if c in features_df.columns]
    
    if not existing_cols:
        print("No regime columns found")
        return pd.DataFrame()
    
    summary = pd.DataFrame({
        "regime": existing_cols,
        "pct_active": [features_df[c].mean() * 100 for c in existing_cols],
        "total_days": [features_df[c].sum() for c in existing_cols],
    })
    
    return summary


if __name__ == "__main__":
    # Example usage
    np.random.seed(42)
    n = 100
    
    df = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=n),
        "vix_level": 15 + np.random.randn(n) * 5 + np.sin(np.arange(n) / 10) * 10,  # Oscillating VIX
        "dgs10": 4.0 + np.random.randn(n) * 0.5,
        "dgs2": 4.2 + np.random.randn(n) * 0.5,  # Sometimes inverts
        "hy_oas_level": 400 + np.random.randn(n) * 100,
        "liquidity_expanding": (np.random.rand(n) > 0.5).astype(int),
    })
    
    # Make some days have inverted curve
    df.loc[20:30, "dgs10"] = 3.8
    df.loc[20:30, "dgs2"] = 4.5
    
    print("Original DataFrame:")
    print(df.head())
    
    result = compute_all_regimes(df, fed_bs_col="liquidity_expanding")  # Use existing col as proxy
    
    print("\nWith regime flags:")
    print(result[["date", "vix_level", "high_vol_regime", "curve_inverted", "credit_stress"]].head(10))
    
    print("\nRegime summary:")
    print(get_regime_summary(result))
    
    print("\nRegime co-occurrence (high vol + inverted curve):")
    co_occur = ((result["high_vol_regime"] == 1) & (result["curve_inverted"] == 1)).sum()
    print(f"  {co_occur} days with both high vol AND inverted curve")
