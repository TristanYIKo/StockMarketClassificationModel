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
    import pandas_market_calendars as mcal
    from datetime import datetime
    
    # Get asset ID
    try:
        asset_result = db.client.table('assets').select('id').eq('symbol', symbol).single().execute()
        asset_id = asset_result.data['id']
    except Exception as e:
        print(f"  ⚠️  Symbol {symbol} not found in assets table. Skipping.")
        return 0
    
    # Get the latest date with features
    try:
        latest_result = db.client.table('features_daily')\
            .select('date')\
            .eq('asset_id', asset_id)\
            .order('date', desc=True)\
            .limit(1)\
            .execute()
        
        if not latest_result.data:
            print(f"  ⚠️  No features found for {symbol}")
            return 0
        
        latest_date = latest_result.data[0]['date']
        print(f"  Latest feature date: {latest_date}")
        
        # Find next trading day after latest_date
        nyse = mcal.get_calendar('NYSE')
        latest_dt = datetime.fromisoformat(latest_date).date()
        schedule = nyse.schedule(start_date=latest_dt, end_date=latest_dt + timedelta(days=10))
        
        if len(schedule) <= 1:
            print(f"  ⚠️  No future trading days found after {latest_date}")
            return 0
        
        next_trading_day = schedule.index[1].date().isoformat()
        print(f"  Next trading day (prediction target): {next_trading_day}")
        
    except Exception as e:
        print(f"  ⚠️  Error finding dates: {e}")
        return 0
    
    # Check if prediction already exists for next trading day
    try:
        pred_result = db.client.table('model_predictions_classification')\
            .select('date')\
            .eq('symbol', symbol)\
            .eq('horizon', horizon)\
            .eq('date', next_trading_day)\
            .execute()
        
        if pred_result.data:
            print(f"  ✓ Prediction already exists for {next_trading_day}")
            return 0
    except:
        pass
    
    # We need to predict for the next trading day
    missing_dates = [next_trading_day]
    print(f"  Generating prediction for {next_trading_day}")
    
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
