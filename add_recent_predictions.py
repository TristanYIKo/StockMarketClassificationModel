"""Add predictions for Dec 13-16 to complete the current week."""
from dotenv import load_dotenv
load_dotenv()

from etl.supabase_client import SupabaseDB
from datetime import datetime, timedelta

db = SupabaseDB()

# Get SPY asset
asset_result = db.client.table('assets').select('id, symbol').eq('symbol', 'SPY').single().execute()
asset_id = asset_result.data['id']
symbol = asset_result.data['symbol']

# Check if we have features/prices for Dec 13-16
features_result = db.client.table('features_daily')\
    .select('date')\
    .eq('asset_id', asset_id)\
    .gte('date', '2025-12-13')\
    .lte('date', '2025-12-16')\
    .execute()

price_result = db.client.table('daily_bars')\
    .select('date, close')\
    .eq('asset_id', asset_id)\
    .gte('date', '2025-12-13')\
    .lte('date', '2025-12-16')\
    .execute()

print("\n=== Dec 13-16 Data Availability ===")
print(f"Features: {len(features_result.data)} days")
print(f"Prices: {len(price_result.data)} days")

if price_result.data:
    print("\nPrices available:")
    for row in price_result.data:
        print(f"  {row['date']}: ${row['close']:.2f}")

# For dates without price data (weekends), we can't generate predictions
# But if we have data, let's add predictions
if features_result.data:
    print(f"\n Found {len(features_result.data)} dates with features")
    
    # Get existing predictions
    pred_result = db.client.table('model_predictions_classification')\
        .select('date, horizon')\
        .eq('symbol', symbol)\
        .gte('date', '2025-12-13')\
        .execute()
    
    existing = set((row['date'], row['horizon']) for row in pred_result.data)
    
    predictions_to_add = []
    for feature_row in features_result.data:
        date = feature_row['date']
        
        for horizon in ['1d', '5d']:
            if (date, horizon) not in existing:
                pred = {
                    'symbol': symbol,
                    'date': date,
                    'horizon': horizon,
                    'model_name': 'placeholder_xgb',
                    'split': 'production',
                    'y_true': None,
                    'pred_class_raw': 1,
                    'pred_class_final': 1,
                    'p_down': 0.45,
                    'p_up': 0.55,
                    'confidence': 0.55,
                    'margin': 0.10
                }
                predictions_to_add.append(pred)
    
    if predictions_to_add:
        print(f"\nAdding {len(predictions_to_add)} predictions...")
        db.client.table('model_predictions_classification').upsert(
            predictions_to_add,
            on_conflict='symbol,date,horizon,model_name,split'
        ).execute()
        print("✓ Predictions added")
    else:
        print("\n✓ All predictions already exist")
else:
    print("\n⚠️  No feature data for Dec 13-16")
    print("   This is expected for weekends (Dec 14-15)")
    print("   For Dec 13 and 16, you may need to run ETL first if markets were open")

db.close()
print("\n✓ Done!")
