"""
Generate predictions for all symbols (SPY, QQQ, IWM, DIA).
This script generates predictions for any missing dates across all symbols.
"""
import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from etl.supabase_client import SupabaseDB

# All symbols to process
SYMBOLS = ['SPY', 'QQQ', 'IWM', 'DIA']

def generate_predictions_for_symbol(db: SupabaseDB, symbol: str, horizon: str):
    """Generate predictions for a single symbol and horizon."""
    
    # Get asset ID
    try:
        asset_result = db.client.table('assets').select('id').eq('symbol', symbol).single().execute()
        asset_id = asset_result.data['id']
    except Exception as e:
        print(f"  ⚠️  Symbol {symbol} not found in assets table. Skipping.")
        return 0
    
    # Get dates with features
    try:
        features_result = db.client.table('features_daily')\
            .select('date')\
            .eq('asset_id', asset_id)\
            .gte('date', '2025-12-06')\
            .order('date', desc=False)\
            .execute()
    except Exception as e:
        print(f"  ⚠️  No features found for {symbol}")
        return 0
    
    # Get existing predictions
    try:
        pred_result = db.client.table('model_predictions_classification')\
            .select('date')\
            .eq('symbol', symbol)\
            .eq('horizon', horizon)\
            .gte('date', '2025-12-06')\
            .execute()
        
        existing_pred_dates = set(row['date'] for row in pred_result.data)
    except:
        existing_pred_dates = set()
    
    # Find missing dates
    missing_dates = []
    for row in features_result.data:
        if row['date'] not in existing_pred_dates:
            missing_dates.append(row['date'])
    
    if not missing_dates:
        return 0
    
    print(f"  Found {len(missing_dates)} dates needing predictions")
    
    # Generate predictions (using placeholder values)
    predictions_to_insert = []
    for date in missing_dates:
        # Default prediction (replace with actual model in production)
        p_up = 0.55
        p_down = 0.45
        pred_class = 1  # UP
        confidence = p_up
        
        pred_data = {
            'symbol': symbol,
            'date': date,
            'horizon': horizon,
            'model_name': 'placeholder_xgb',
            'split': 'production',
            'y_true': None,
            'pred_class_raw': pred_class,
            'pred_class_final': pred_class,
            'p_down': p_down,
            'p_up': p_up,
            'confidence': confidence,
            'margin': abs(p_up - p_down)
        }
        
        predictions_to_insert.append(pred_data)
    
    # Insert predictions
    if predictions_to_insert:
        try:
            result = db.client.table('model_predictions_classification').upsert(
                predictions_to_insert,
                on_conflict='symbol,date,horizon,model_name,split'
            ).execute()
            return len(predictions_to_insert)
        except Exception as e:
            print(f"  ✗ Error inserting predictions: {e}")
            return 0
    
    return 0

def main():
    """Generate predictions for all symbols."""
    print("\n" + "="*70)
    print("Generating Predictions for All Symbols")
    print("="*70)
    print(f"Symbols: {', '.join(SYMBOLS)}")
    print(f"Horizons: 1d, 5d")
    print("="*70 + "\n")
    
    db = SupabaseDB()
    
    total_predictions = 0
    
    for symbol in SYMBOLS:
        print(f"\n📊 Processing {symbol}...")
        
        # Generate 1d predictions
        print(f"  → 1-day horizon...")
        count_1d = generate_predictions_for_symbol(db, symbol, '1d')
        if count_1d > 0:
            print(f"    ✓ Inserted {count_1d} predictions")
        
        # Generate 5d predictions
        print(f"  → 5-day horizon...")
        count_5d = generate_predictions_for_symbol(db, symbol, '5d')
        if count_5d > 0:
            print(f"    ✓ Inserted {count_5d} predictions")
        
        total_predictions += count_1d + count_5d
        
        if count_1d == 0 and count_5d == 0:
            print(f"  ✓ All predictions up to date for {symbol}")
    
    db.close()
    
    print("\n" + "="*70)
    print(f"✓ Complete! Generated {total_predictions} total predictions")
    print("="*70)
    
    if total_predictions > 0:
        print("\n⚠️  Note: These are placeholder predictions (55% UP probability)")
        print("For actual model-based predictions:")
        print("  1. Train models: python train_models_1d.py")
        print("  2. Run predictions: cd ml && python src/predict/predict_and_store.py")
        print("  3. Or use GitHub Actions with trained models committed to repo")
    
    print()

if __name__ == '__main__':
    main()
