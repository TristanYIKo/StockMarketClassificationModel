"""Generate predictions for dates 2025-12-06 through 2025-12-16."""
import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas as pd

# Load environment
load_dotenv()

# Add paths
sys.path.insert(0, os.path.dirname(__file__))

from etl.supabase_client import SupabaseDB

def generate_missing_predictions():
    """Generate predictions for missing dates."""
    db = SupabaseDB()
    
    # Get asset ID for SPY
    asset_result = db.client.table('assets').select('id').eq('symbol', 'SPY').single().execute()
    asset_id = asset_result.data['id']
    
    # Get latest features_daily to see what dates we have
    features_result = db.client.table('features_daily')\
        .select('date')\
        .eq('asset_id', asset_id)\
        .order('date', desc=True)\
        .limit(20)\
        .execute()
    
    print("\n=== Latest Feature Dates ===")
    for row in features_result.data[:10]:
        print(f"  {row['date']}")
    
    # Get latest predictions
    pred_result = db.client.table('model_predictions_classification')\
        .select('date, horizon')\
        .eq('symbol', 'SPY')\
        .order('date', desc=True)\
        .limit(10)\
        .execute()
    
    print("\n=== Latest Prediction Dates ===")
    for row in pred_result.data[:5]:
        print(f"  {row['date']} ({row['horizon']})")
    
    # Get prices for reference
    price_result = db.client.table('daily_bars')\
        .select('date, close')\
        .eq('asset_id', asset_id)\
        .gte('date', '2025-12-06')\
        .lte('date', '2025-12-16')\
        .order('date', desc=False)\
        .execute()
    
    print(f"\n=== Prices Available (Dec 6-16) ===")
    for row in price_result.data:
        print(f"  {row['date']}: ${row['close']:.2f}")
    
    # Check if we need to run ETL first
    if not price_result.data:
        print("\n⚠️  No price data for Dec 6-16. Run ETL first:")
        print("   python etl/main.py --start 2025-12-06 --end 2025-12-16")
        db.close()
        return
    
    # Check what feature dates we have
    available_dates = [row['date'] for row in features_result.data]
    missing_prediction_dates = []
    
    # Determine which dates need predictions
    start_date = datetime(2025, 12, 6)
    end_date = datetime(2025, 12, 16)
    current = start_date
    
    existing_pred_dates = set(row['date'] for row in pred_result.data)
    
    while current <= end_date:
        date_str = current.strftime('%Y-%m-%d')
        if date_str not in existing_pred_dates:
            missing_prediction_dates.append(date_str)
        current += timedelta(days=1)
    
    print(f"\n=== Dates Needing Predictions ===")
    if missing_prediction_dates:
        for date in missing_prediction_dates:
            print(f"  {date}")
    else:
        print("  All dates have predictions!")
    
    db.close()
    
    if missing_prediction_dates:
        print("\n📝 To generate predictions, you need to:")
        print("   1. Ensure features_json has data for these dates (run ETL if needed)")
        print("   2. Run the prediction script:")
        print("      cd ml")
        print("      python src/predict/predict_and_store.py --data_source supabase --horizon all --store_db")
        print("\nAlternatively, use the GitHub Actions workflow to update all data automatically.")

if __name__ == '__main__':
    generate_missing_predictions()
