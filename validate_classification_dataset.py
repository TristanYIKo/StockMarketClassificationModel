"""
Validation script for 1-day classification dataset.

Validates:
- No NULL targets (after warm-up)
- Valid class values only (-1, 0, 1)
- Class balance (warns if Hold > 85%)
- No duplicates
- Feature count matches expected

Usage:
    python validate_classification_dataset.py --supabase

Date: 2025-12-14
"""

import os
import sys
import argparse
import pandas as pd
from typing import Dict, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.supabase_client import SupabaseDB


def validate_no_nulls(df: pd.DataFrame, warmup_days: int = 252) -> Tuple[bool, str]:
    """Check for NULL in y_class_1d beyond warm-up period."""
    if 'y_class_1d' not in df.columns:
        return False, "Column 'y_class_1d' not found in dataset"
    
    min_date = df['date'].min()
    warmup_end = pd.to_datetime(min_date) + pd.Timedelta(days=warmup_days)
    df_after_warmup = df[pd.to_datetime(df['date']) > warmup_end]
    
    null_count = df_after_warmup['y_class_1d'].isna().sum()
    total_rows = len(df_after_warmup)
    
    if null_count == 0:
        return True, f"✓ No NULL in y_class_1d after {warmup_days}-day warm-up ({total_rows} rows checked)"
    else:
        pct = (null_count / total_rows * 100) if total_rows > 0 else 0
        return False, f"✗ Found {null_count} NULL in y_class_1d ({pct:.2f}% of {total_rows} rows)"


def validate_valid_classes(df: pd.DataFrame) -> Tuple[bool, str]:
    """Check that all class values are -1, 0, or 1."""
    if 'y_class_1d' not in df.columns:
        return False, "Column 'y_class_1d' not found"
    
    valid_values = {-1, 0, 1}
    actual_values = set(df['y_class_1d'].dropna().unique())
    invalid = actual_values - valid_values
    
    if len(invalid) == 0:
        return True, f"✓ All class values are valid: {sorted(actual_values)}"
    else:
        return False, f"✗ Found invalid class values: {invalid}"


def validate_class_balance(df: pd.DataFrame) -> Tuple[bool, str]:
    """Check class distribution and warn if Hold > 85%."""
    if 'y_class_1d' not in df.columns:
        return False, "Column 'y_class_1d' not found"
    
    counts = df['y_class_1d'].value_counts()
    total = counts.sum()
    
    pct_buy = (counts.get(1, 0) / total * 100) if total > 0 else 0
    pct_hold = (counts.get(0, 0) / total * 100) if total > 0 else 0
    pct_sell = (counts.get(-1, 0) / total * 100) if total > 0 else 0
    
    message = f"Class distribution: Buy={pct_buy:.1f}%, Hold={pct_hold:.1f}%, Sell={pct_sell:.1f}%"
    
    if pct_hold > 90:
        return False, f"✗ {message} (Hold > 90% indicates threshold too strict)"
    elif pct_hold > 85:
        return False, f"⚠ {message} (WARNING: Hold > 85%)"
    else:
        return True, f"✓ {message}"


def validate_no_duplicates(df: pd.DataFrame) -> Tuple[bool, str]:
    """Check for duplicate (symbol, date) pairs."""
    if 'symbol' not in df.columns or 'date' not in df.columns:
        return False, "Columns 'symbol' and 'date' required"
    
    duplicates = df.duplicated(subset=['symbol', 'date']).sum()
    
    if duplicates == 0:
        return True, f"✓ No duplicate (symbol, date) pairs"
    else:
        return False, f"✗ Found {duplicates} duplicate (symbol, date) pairs"


def validate_feature_count(df: pd.DataFrame, expected: int = 83) -> Tuple[bool, str]:
    """Check that feature count matches expected."""
    feature_cols = [c for c in df.columns 
                   if c not in ['symbol', 'date', 'y_class_1d']]
    
    actual = len(feature_cols)
    
    if actual == expected:
        return True, f"✓ Feature count matches expected: {actual} features"
    else:
        return False, f"⚠ Feature count mismatch: expected {expected}, got {actual}"


def validate_class_distribution_per_symbol(df: pd.DataFrame) -> Tuple[bool, str]:
    """Check class distribution per symbol."""
    if 'symbol' not in df.columns or 'y_class_1d' not in df.columns:
        return False, "Required columns not found"
    
    stats = []
    for symbol in df['symbol'].unique():
        symbol_df = df[df['symbol'] == symbol]
        counts = symbol_df['y_class_1d'].value_counts()
        total = counts.sum()
        
        pct_hold = (counts.get(0, 0) / total * 100) if total > 0 else 0
        stats.append(f"{symbol}: Hold={pct_hold:.1f}%")
    
    return True, f"✓ Per-symbol Hold%: {', '.join(stats)}"


def run_all_validations(df: pd.DataFrame) -> Dict[str, Tuple[bool, str]]:
    """Run all validation checks."""
    checks = {
        'no_nulls': validate_no_nulls(df, 252),
        'valid_classes': validate_valid_classes(df),
        'class_balance': validate_class_balance(df),
        'no_duplicates': validate_no_duplicates(df),
        'feature_count': validate_feature_count(df, 83),
        'per_symbol_distribution': validate_class_distribution_per_symbol(df),
    }
    
    return checks


def print_validation_report(checks: Dict[str, Tuple[bool, str]]):
    """Print formatted validation report."""
    print("\n" + "="*70)
    print("CLASSIFICATION DATASET VALIDATION REPORT")
    print("="*70 + "\n")
    
    passed = 0
    failed = 0
    warned = 0
    
    for check_name, (success, message) in checks.items():
        if success:
            passed += 1
        elif message.startswith("⚠"):
            warned += 1
        else:
            failed += 1
        
        print(f"{check_name:30s} {message}")
    
    print("\n" + "-"*70)
    print(f"SUMMARY: {passed} passed, {failed} failed, {warned} warnings")
    print("="*70 + "\n")
    
    return failed == 0


def load_dataset_from_supabase() -> pd.DataFrame:
    """Load classification dataset from Supabase."""
    print("Loading classification dataset from Supabase...")
    
    db = SupabaseDB(
        url=os.getenv("SUPABASE_URL"),
        key=os.getenv("SUPABASE_KEY")
    )
    
    # Query classification view
    query = """
        select * from public.v_classification_dataset_1d
        order by symbol, date
    """
    
    response = db.client.rpc('exec_sql', {'query': query}).execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
        return df
    else:
        # Fallback: query labels_daily directly
        print("View not found, querying labels_daily directly...")
        query = """
            select 
                a.symbol,
                l.date,
                l.y_class_1d
            from public.labels_daily l
            join public.assets a on a.id = l.asset_id
            where a.asset_type = 'ETF'
              and l.y_class_1d is not null
            order by a.symbol, l.date
        """
        response = db.client.rpc('exec_sql', {'query': query}).execute()
        if response.data:
            df = pd.DataFrame(response.data)
            print(f"Loaded {len(df)} rows from labels_daily")
            return df
        else:
            raise Exception("Failed to load dataset from Supabase")


def run_sql_validation(db: SupabaseDB):
    """Run SQL validation function."""
    print("\n" + "="*70)
    print("RUNNING SQL VALIDATION FUNCTION")
    print("="*70 + "\n")
    
    try:
        response = db.client.rpc('validate_classification_dataset_1d').execute()
        
        if response.data:
            for row in response.data:
                status_symbol = "✓" if row['status'] == 'PASS' else ("⚠" if row['status'] == 'WARN' else "✗")
                print(f"{status_symbol} {row['check_name']:30s} {row['details']}")
        else:
            print("No results returned from SQL validation function")
    except Exception as e:
        print(f"Error running SQL validation: {e}")


def main():
    parser = argparse.ArgumentParser(description="Validate classification dataset")
    parser.add_argument('--supabase', action='store_true', help='Validate data from Supabase')
    parser.add_argument('--csv', type=str, help='Validate data from CSV file')
    parser.add_argument('--sql-only', action='store_true', help='Run SQL validation only')
    
    args = parser.parse_args()
    
    if args.sql_only:
        # Run SQL validation function only
        db = SupabaseDB(
            url=os.getenv("SUPABASE_URL"),
            key=os.getenv("SUPABASE_KEY")
        )
        run_sql_validation(db)
        sys.exit(0)
    
    # Load dataset
    if args.supabase:
        df = load_dataset_from_supabase()
    elif args.csv:
        print(f"Loading dataset from {args.csv}...")
        df = pd.read_csv(args.csv)
        print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    else:
        print("Error: Must specify --supabase, --csv, or --sql-only")
        print("Usage: python validate_classification_dataset.py --supabase")
        print("   or: python validate_classification_dataset.py --csv path/to/data.csv")
        print("   or: python validate_classification_dataset.py --sql-only")
        sys.exit(1)
    
    # Run Python validations
    checks = run_all_validations(df)
    all_passed = print_validation_report(checks)
    
    # Also run SQL validation if using Supabase
    if args.supabase:
        db = SupabaseDB(
            url=os.getenv("SUPABASE_URL"),
            key=os.getenv("SUPABASE_KEY")
        )
        run_sql_validation(db)
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
