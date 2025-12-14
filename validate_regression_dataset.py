"""
Dataset validation for regression modeling.

Validates:
- No NaN in primary target (beyond warm-up period)
- No duplicate (symbol, date) pairs
- Target variance is non-zero per symbol
- Feature count matches expected manifest
- No extreme outliers beyond clipping thresholds
- Feature distributions are reasonable

Usage:
    python validate_regression_dataset.py [--supabase | --local]

Date: 2025-12-13
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.supabase_client import SupabaseDB
from etl.transform_normalization import validate_feature_distributions, BINARY_FEATURES


# Expected feature count (after redundancy removal)
EXPECTED_FEATURE_COUNT = 83  # Updated count after optimization

# Symbols to validate
SYMBOLS = ['SPY', 'QQQ', 'DIA', 'IWM']

# Warm-up period (days to ignore for NaN checks)
WARMUP_DAYS = 252


def validate_no_nans(df: pd.DataFrame, warmup_days: int = 252) -> Tuple[bool, str]:
    """
    Check for NaN in primary_target beyond warm-up period.
    
    Returns:
        (pass: bool, message: str)
    """
    if 'primary_target' not in df.columns:
        return False, "Column 'primary_target' not found in dataset"
    
    # Skip warm-up period
    min_date = df['date'].min()
    warmup_end = pd.to_datetime(min_date) + pd.Timedelta(days=warmup_days)
    df_after_warmup = df[pd.to_datetime(df['date']) > warmup_end]
    
    nan_count = df_after_warmup['primary_target'].isna().sum()
    total_rows = len(df_after_warmup)
    
    if nan_count == 0:
        return True, f"✓ No NaN in primary_target after {warmup_days}-day warm-up ({total_rows} rows checked)"
    else:
        pct = (nan_count / total_rows * 100) if total_rows > 0 else 0
        return False, f"✗ Found {nan_count} NaN in primary_target ({pct:.2f}% of {total_rows} rows)"


def validate_no_duplicates(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Check for duplicate (symbol, date) pairs.
    
    Returns:
        (pass: bool, message: str)
    """
    if 'symbol' not in df.columns or 'date' not in df.columns:
        return False, "Columns 'symbol' and 'date' required"
    
    duplicates = df.duplicated(subset=['symbol', 'date']).sum()
    
    if duplicates == 0:
        return True, f"✓ No duplicate (symbol, date) pairs"
    else:
        return False, f"✗ Found {duplicates} duplicate (symbol, date) pairs"


def validate_target_variance(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Check that target variance is non-zero per symbol.
    
    Returns:
        (pass: bool, message: str)
    """
    if 'symbol' not in df.columns or 'primary_target' not in df.columns:
        return False, "Columns 'symbol' and 'primary_target' required"
    
    zero_var_symbols = []
    for symbol in df['symbol'].unique():
        symbol_data = df[df['symbol'] == symbol]['primary_target'].dropna()
        if len(symbol_data) > 1:
            var = symbol_data.var()
            if var == 0 or pd.isna(var):
                zero_var_symbols.append(symbol)
    
    if len(zero_var_symbols) == 0:
        return True, f"✓ All {len(df['symbol'].unique())} symbols have non-zero target variance"
    else:
        return False, f"✗ Symbols with zero variance: {zero_var_symbols}"


def validate_feature_count(df: pd.DataFrame, expected: int) -> Tuple[bool, str]:
    """
    Check that feature count matches expected.
    
    Returns:
        (pass: bool, message: str)
    """
    # Exclude metadata columns
    feature_cols = [c for c in df.columns 
                   if c not in ['symbol', 'date', 'primary_target', 'asset_id']]
    
    actual = len(feature_cols)
    
    if actual == expected:
        return True, f"✓ Feature count matches expected: {actual} features"
    else:
        return False, f"⚠ Feature count mismatch: expected {expected}, got {actual}"


def validate_no_extreme_outliers(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Check for extreme outliers beyond clipping thresholds.
    
    Returns:
        (pass: bool, message: str)
    """
    if 'primary_target' not in df.columns:
        return False, "Column 'primary_target' not found"
    
    # Primary target should be clipped to ±3
    extreme = (df['primary_target'].abs() > 3.0).sum()
    
    if extreme == 0:
        return True, f"✓ No extreme outliers in primary_target (all within ±3)"
    else:
        return False, f"✗ Found {extreme} rows with |primary_target| > 3.0"


def validate_date_range(df: pd.DataFrame, min_years: int = 10) -> Tuple[bool, str]:
    """
    Check that date range is sufficient.
    
    Returns:
        (pass: bool, message: str)
    """
    if 'date' not in df.columns:
        return False, "Column 'date' not found"
    
    min_date = pd.to_datetime(df['date'].min())
    max_date = pd.to_datetime(df['date'].max())
    days = (max_date - min_date).days
    years = days / 365.25
    
    if years >= min_years:
        return True, f"✓ Date range: {min_date.date()} to {max_date.date()} ({years:.1f} years)"
    else:
        return False, f"⚠ Date range too short: {years:.1f} years (minimum {min_years} recommended)"


def validate_feature_distributions_check(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Check that feature distributions are reasonable.
    
    Returns:
        (pass: bool, message: str)
    """
    # Get distribution stats
    stats = validate_feature_distributions(df)
    
    issues = []
    
    for feature, stat in stats.items():
        # Skip binary features and metadata
        if stat['is_binary'] or feature in ['date', 'symbol', 'primary_target']:
            continue
        
        # Check for excessive nulls
        if stat['pct_null'] > 50:
            issues.append(f"{feature}: {stat['pct_null']:.1f}% null")
        
        # Check for extreme values
        if stat['outliers_beyond_5'] > len(df) * 0.01:  # More than 1% outliers
            issues.append(f"{feature}: {stat['outliers_beyond_5']} outliers beyond ±5")
    
    if len(issues) == 0:
        return True, f"✓ Feature distributions look reasonable ({len(stats)} features checked)"
    else:
        return False, f"⚠ Distribution issues:\n  " + "\n  ".join(issues[:5])


def run_all_validations(df: pd.DataFrame) -> Dict[str, Tuple[bool, str]]:
    """
    Run all validation checks.
    
    Returns:
        Dictionary of check_name -> (pass, message)
    """
    checks = {
        'no_nans': validate_no_nans(df, WARMUP_DAYS),
        'no_duplicates': validate_no_duplicates(df),
        'target_variance': validate_target_variance(df),
        'feature_count': validate_feature_count(df, EXPECTED_FEATURE_COUNT),
        'no_extreme_outliers': validate_no_extreme_outliers(df),
        'date_range': validate_date_range(df, min_years=10),
        'feature_distributions': validate_feature_distributions_check(df),
    }
    
    return checks


def print_validation_report(checks: Dict[str, Tuple[bool, str]]):
    """
    Print formatted validation report.
    """
    print("\n" + "="*70)
    print("REGRESSION DATASET VALIDATION REPORT")
    print("="*70 + "\n")
    
    passed = 0
    failed = 0
    warned = 0
    
    for check_name, (success, message) in checks.items():
        status_symbol = "✓" if success else ("⚠" if message.startswith("⚠") else "✗")
        
        if success:
            passed += 1
        elif message.startswith("⚠"):
            warned += 1
        else:
            failed += 1
        
        print(f"{check_name:25s} {message}")
    
    print("\n" + "-"*70)
    print(f"SUMMARY: {passed} passed, {failed} failed, {warned} warnings")
    print("="*70 + "\n")
    
    return failed == 0


def load_dataset_from_supabase() -> pd.DataFrame:
    """
    Load optimized dataset from Supabase.
    """
    print("Loading dataset from Supabase...")
    
    db = SupabaseDB(
        url=os.getenv("SUPABASE_URL"),
        key=os.getenv("SUPABASE_KEY")
    )
    
    # Query optimized view
    query = """
        select * from public.v_regression_dataset_optimized
        order by symbol, date
    """
    
    response = db.client.rpc('exec_sql', {'query': query}).execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
        return df
    else:
        raise Exception("Failed to load dataset from Supabase")


def main():
    parser = argparse.ArgumentParser(description="Validate regression dataset")
    parser.add_argument('--supabase', action='store_true', help='Validate data from Supabase')
    parser.add_argument('--csv', type=str, help='Validate data from CSV file')
    
    args = parser.parse_args()
    
    # Load dataset
    if args.supabase:
        df = load_dataset_from_supabase()
    elif args.csv:
        print(f"Loading dataset from {args.csv}...")
        df = pd.read_csv(args.csv)
        print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    else:
        print("Error: Must specify --supabase or --csv")
        print("Usage: python validate_regression_dataset.py --supabase")
        print("   or: python validate_regression_dataset.py --csv path/to/data.csv")
        sys.exit(1)
    
    # Run validations
    checks = run_all_validations(df)
    
    # Print report
    all_passed = print_validation_report(checks)
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
