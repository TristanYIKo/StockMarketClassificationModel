"""
Quick script to check ETL progress and verify binary labels.
"""

from dotenv import load_dotenv
load_dotenv()

from etl.supabase_client import SupabaseDB
import pandas as pd

def check_progress():
    db = SupabaseDB()
    
    print("📊 Checking ETL Progress...\n")
    
    # Check labels
    result = db.client.table('labels_daily').select('*', count='exact').limit(1).execute()
    label_count = result.count
    print(f"Labels: {label_count:,} rows")
    
    # Check features
    result = db.client.table('features_daily').select('*', count='exact').limit(1).execute()
    feature_count = result.count
    print(f"Features: {feature_count:,} rows")
    
    # Check bars
    result = db.client.table('daily_bars').select('*', count='exact').limit(1).execute()
    bars_count = result.count
    print(f"Daily bars: {bars_count:,} rows")
    
    if label_count > 100:
        # Check if labels are binary
        result = db.client.table('labels_daily').select('y_class_1d').limit(500).execute()
        df = pd.DataFrame(result.data)
        unique_vals = sorted(df['y_class_1d'].dropna().unique())
        
        print(f"\n🎯 Label Status:")
        print(f"   Unique values: {unique_vals}")
        
        if set(unique_vals) == {-1.0, 1.0}:
            print("   ✅ BINARY CLASSIFICATION (UP/DOWN only)")
        elif 0.0 in unique_vals:
            print("   ⚠️  Still contains HOLD class (0)")
        
        print(f"\n   Distribution:")
        print(df['y_class_1d'].value_counts().to_string())
    
    print(f"\n{'✅ ETL Complete!' if label_count > 20000 else '⏳ ETL still running...'}")

if __name__ == '__main__':
    check_progress()
