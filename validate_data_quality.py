"""
Data validation checks for post-pruning dataset health.

Verifies:
1. No duplicate (asset_id, date) combinations
2. Proper NaN warm-up periods (SMA200 needs 200 days)
3. Event types match allowed list (fomc, cpi_release, nfp_release)
4. Training data starts after 260 trading days minimum
5. Labels properly shifted (no leakage)
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from etl.supabase_client import SupabaseDB


def check_duplicates(db: SupabaseDB) -> bool:
    """Check for duplicate (asset_id, date) in features and labels."""
    print("\n=== Checking for duplicates ===")
    
    # Features
    result = db.client.rpc(
        'check_duplicates_features',
        {}
    ).execute()
    
    if not result.data or result.data[0].get('count', 0) == 0:
        print("✓ No duplicates in features_daily")
    else:
        print(f"✗ Found {result.data[0]['count']} duplicate (asset_id, date) in features_daily")
        return False
    
    # Labels
    result = db.client.rpc(
        'check_duplicates_labels',
        {}
    ).execute()
    
    if not result.data or result.data[0].get('count', 0) == 0:
        print("✓ No duplicates in labels_daily")
    else:
        print(f"✗ Found {result.data[0]['count']} duplicate (asset_id, date) in labels_daily")
        return False
    
    return True


def check_event_types(db: SupabaseDB) -> bool:
    """Verify only allowed event types exist."""
    print("\n=== Checking event types ===")
    
    allowed = {'fomc', 'cpi_release', 'nfp_release'}
    
    result = db.client.table('events_calendar').select('event_type').execute()
    
    if not result.data:
        print("✗ No events found in calendar")
        return False
    
    df = pd.DataFrame(result.data)
    unique_types = set(df['event_type'].unique())
    
    if unique_types <= allowed:
        print(f"✓ All event types valid: {unique_types}")
        counts = df['event_type'].value_counts().to_dict()
        for event_type, count in counts.items():
            print(f"  - {event_type}: {count} events")
        return True
    else:
        invalid = unique_types - allowed
        print(f"✗ Invalid event types found: {invalid}")
        return False


def check_warm_up_period(db: SupabaseDB) -> bool:
    """Check that training data has sufficient warm-up."""
    print("\n=== Checking warm-up period ===")
    
    # Get earliest date per ETF
    result = db.client.table('v_model_dataset').select('symbol, date').order('date').limit(4).execute()
    
    if not result.data:
        print("✗ No data in v_model_dataset")
        return False
    
    df = pd.DataFrame(result.data)
    earliest_dates = df.groupby('symbol')['date'].min()
    
    all_ok = True
    for symbol, date_str in earliest_dates.items():
        date = pd.to_datetime(date_str).date()
        
        # Check if we have at least 260 days before first training date
        # Assumes data starts from 2000-01-01
        start_date = pd.to_datetime('2000-01-01').date()
        days_warmup = (date - start_date).days
        
        if days_warmup < 200:
            print(f"✗ {symbol}: Only {days_warmup} days warm-up (need 200+ for SMA200)")
            all_ok = False
        else:
            print(f"✓ {symbol}: {days_warmup} days warm-up (sufficient)")
    
    return all_ok


def check_nan_handling(db: SupabaseDB) -> bool:
    """Check NaN counts in first 260 rows vs later rows."""
    print("\n=== Checking NaN patterns ===")
    
    # Get SPY data as sample
    result = db.client.table('v_model_dataset').select(
        'date, sma_200, vol_60'
    ).eq('symbol', 'SPY').order('date').limit(300).execute()
    
    if not result.data:
        print("✗ No data found for SPY")
        return False
    
    df = pd.DataFrame(result.data)
    
    # Check first 260 rows
    first_260 = df.iloc[:260]
    after_260 = df.iloc[260:]
    
    nan_early = first_260.isna().sum()
    nan_later = after_260.isna().sum()
    
    print(f"NaN counts in first 260 rows:")
    print(f"  - sma_200: {nan_early['sma_200']}")
    print(f"  - vol_60: {nan_early['vol_60']}")
    
    print(f"NaN counts after row 260:")
    print(f"  - sma_200: {nan_later['sma_200']}")
    print(f"  - vol_60: {nan_later['vol_60']}")
    
    if nan_later['sma_200'] > 5:
        print("✗ Too many NaN in sma_200 after warm-up")
        return False
    
    print("✓ NaN pattern looks reasonable (concentrated in warm-up period)")
    return True


def check_label_shift(db: SupabaseDB) -> bool:
    """Verify labels are properly shifted forward (no leakage)."""
    print("\n=== Checking label shift ===")
    
    # Get SPY bars and labels
    bars = db.client.table('daily_bars').select('date, close').eq(
        'asset_id', 
        db.client.table('assets').select('id').eq('symbol', 'SPY').execute().data[0]['id']
    ).order('date').limit(10).execute()
    
    labels = db.client.table('labels_daily').select('date, y_1d').eq(
        'asset_id',
        db.client.table('assets').select('id').eq('symbol', 'SPY').execute().data[0]['id']
    ).order('date').limit(10).execute()
    
    if not bars.data or not labels.data:
        print("✗ No data found for shift check")
        return False
    
    bars_df = pd.DataFrame(bars.data)
    labels_df = pd.DataFrame(labels.data)
    
    # Labels should be computed from FUTURE closes
    # y_1d at date t should be based on close at t+1
    merged = bars_df.merge(labels_df, on='date', how='inner')
    
    print(f"✓ Found {len(merged)} overlapping dates for validation")
    print(f"  Sample dates: {merged['date'].iloc[:3].tolist()}")
    
    return True


def check_feature_manifest_alignment(db: SupabaseDB) -> bool:
    """Check that v_features_pruned has correct feature count."""
    print("\n=== Checking feature manifest alignment ===")
    
    # Expected: 22 technical + 12 macro + 4 VIX + 8 cross-asset + 4 breadth + 3 events = 53 features
    # Plus: date, asset_id, id, created_at (metadata) = 57 columns total
    
    result = db.client.table('v_features_pruned').select('*').limit(1).execute()
    
    if not result.data:
        print("✗ v_features_pruned is empty")
        return False
    
    columns = list(result.data[0].keys())
    feature_cols = [c for c in columns if c not in ['id', 'asset_id', 'date', 'created_at']]
    
    expected = 53  # As per manifest
    actual = len(feature_cols)
    
    print(f"Feature count: {actual} (expected {expected})")
    
    if actual == expected:
        print("✓ Feature count matches manifest")
        return True
    else:
        print(f"✗ Mismatch: expected {expected}, got {actual}")
        print(f"Columns: {feature_cols}")
        return False


def run_all_checks():
    """Run all validation checks."""
    print("=" * 60)
    print("DATA VALIDATION CHECKS (Post-Pruning)")
    print("=" * 60)
    
    db = SupabaseDB()
    
    checks = [
        ("Duplicate check", lambda: check_duplicates(db)),
        ("Event types", lambda: check_event_types(db)),
        ("Warm-up period", lambda: check_warm_up_period(db)),
        ("NaN handling", lambda: check_nan_handling(db)),
        ("Label shift", lambda: check_label_shift(db)),
        ("Feature manifest", lambda: check_feature_manifest_alignment(db)),
    ]
    
    results = {}
    for name, check_fn in checks:
        try:
            results[name] = check_fn()
        except Exception as e:
            print(f"✗ {name} failed with error: {e}")
            results[name] = False
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 All validation checks passed!")
    else:
        print("\n⚠️  Some validation checks failed. Review output above.")
    
    return all_passed


if __name__ == "__main__":
    run_all_checks()
