"""Check prediction dates in database."""
from dotenv import load_dotenv
load_dotenv()

from etl.supabase_client import SupabaseDB

db = SupabaseDB()

# Get latest predictions
result = db.client.table('model_predictions_classification')\
    .select('date, symbol, horizon, pred_class_final, confidence')\
    .eq('symbol', 'SPY')\
    .order('date', desc=True)\
    .limit(30)\
    .execute()

print("\n=== Latest SPY Predictions in Database ===\n")
for row in result.data:
    print(f"{row['date']} | {row['horizon']} | Pred: {row['pred_class_final']} | Conf: {row['confidence']:.3f}")

# Get latest prices
asset_result = db.client.table('assets').select('id').eq('symbol', 'SPY').single().execute()
asset_id = asset_result.data['id']

price_result = db.client.table('daily_bars')\
    .select('date, close')\
    .eq('asset_id', asset_id)\
    .order('date', desc=True)\
    .limit(20)\
    .execute()

print("\n=== Latest SPY Prices in Database ===\n")
for row in price_result.data:
    print(f"{row['date']} | Close: ${row['close']:.2f}")

db.close()
