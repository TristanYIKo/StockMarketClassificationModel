"""Verify predictions for all symbols."""
from dotenv import load_dotenv
load_dotenv()

from etl.supabase_client import SupabaseDB

SYMBOLS = ['SPY', 'QQQ', 'IWM', 'DIA']

db = SupabaseDB()

print("\n=== Latest Predictions by Symbol ===\n")

for symbol in SYMBOLS:
    result = db.client.table('model_predictions_classification')\
        .select('date, horizon, pred_class_final, confidence')\
        .eq('symbol', symbol)\
        .order('date', desc=True)\
        .limit(6)\
        .execute()
    
    print(f"{symbol}:")
    if result.data:
        for row in result.data:
            direction = "UP" if row['pred_class_final'] == 1 else "DOWN"
            print(f"  {row['date']} | {row['horizon']} | {direction} | Conf: {row['confidence']:.3f}")
    else:
        print(f"  No predictions found")
    print()

db.close()
