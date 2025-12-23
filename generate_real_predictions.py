"""
Generate real model-based predictions for the next trading day.
Uses trained XGBoost models instead of placeholder predictions.
"""
import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas_market_calendars as mcal

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from etl.supabase_client import SupabaseDB

# All symbols to process
SYMBOLS = ['SPY', 'QQQ', 'IWM', 'DIA']

def fetch_latest_features(db: SupabaseDB, symbol: str) -> pd.DataFrame:
    """
    Fetch the most recent features for a symbol.
    Returns a single-row DataFrame with all features unpacked and proper dtypes.
    """
    try:
        # Get asset ID
        asset_result = db.client.table('assets').select('id').eq('symbol', symbol).single().execute()
        asset_id = asset_result.data['id']
        
        # Get latest feature row
        features_result = db.client.table('features_daily')\
            .select('date, feature_json')\
            .eq('asset_id', asset_id)\
            .order('date', desc=True)\
            .limit(1)\
            .execute()
        
        if not features_result.data:
            print(f"    No features found for {symbol}")
            return None
            
        row = features_result.data[0]
        date = row['date']
        feature_json = row['feature_json']
        
        # Parse JSON if needed
        if isinstance(feature_json, str):
            feature_json = json.loads(feature_json)
        
        # Create DataFrame with features
        df = pd.DataFrame([feature_json])
        df.insert(0, 'symbol', symbol)
        df.insert(1, 'date', date)
        
        # Convert all feature columns to numeric (handle string types from JSON)
        exclude_cols = ['symbol', 'date']
        for col in df.columns:
            if col not in exclude_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
        
    except Exception as e:
        print(f"    Error fetching features for {symbol}: {e}")
        return None


def load_model_artifacts(horizon: str, model_name: str = 'xgboost'):
    """Load trained model and preprocessor for given horizon."""
    model_dir = f'ml/artifacts/models/{model_name}_{horizon}'
    
    model_path = os.path.join(model_dir, 'model.pkl')
    preprocessor_path = os.path.join(model_dir, 'preprocessor.pkl')
    
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")
    
    if not os.path.exists(preprocessor_path):
        raise FileNotFoundError(f"Preprocessor not found: {preprocessor_path}")
    
    model = joblib.load(model_path)
    preprocessor = joblib.load(preprocessor_path)
    
    return model, preprocessor


def predict_symbol(db: SupabaseDB, symbol: str, horizon: str, model_name: str = 'xgboost'):
    """Generate prediction for a single symbol and horizon."""
    
    # 1. Fetch latest features
    features_df = fetch_latest_features(db, symbol)
    if features_df is None:
        return None
    
    latest_date = features_df['date'].iloc[0]
    print(f"  Latest feature date: {latest_date}")
    
    # 2. Find next trading day
    nyse = mcal.get_calendar('NYSE')
    latest_dt = pd.to_datetime(latest_date).date()
    schedule = nyse.schedule(start_date=latest_dt, end_date=latest_dt + timedelta(days=10))
    
    if len(schedule) <= 1:
        print(f"    No future trading days found after {latest_date}")
        return None
    
    next_trading_day = schedule.index[1].date().isoformat()
    print(f"  Next trading day (prediction target): {next_trading_day}")
    
    # 3. Check if prediction already exists
    try:
        pred_result = db.client.table('model_predictions_classification')\
            .select('date')\
            .eq('symbol', symbol)\
            .eq('horizon', horizon)\
            .eq('model_name', model_name)\
            .eq('date', next_trading_day)\
            .execute()
        
        if pred_result.data:
            print(f"   Prediction already exists for {next_trading_day}")
            return 0
    except:
        pass
    
    # 4. Load model
    try:
        model, preprocessor = load_model_artifacts(horizon, model_name)
    except FileNotFoundError as e:
        print(f"    {e}")
        print(f"    Train models first: python train_models_{horizon}.py")
        return None
    
    # 5. Preprocess features
    try:
        X_processed = preprocessor.transform(features_df, split_name='inference')
    except Exception as e:
        print(f"    Preprocessing failed: {e}")
        return None
    
    # 6. Make prediction
    try:
        probs = model.predict_proba(X_processed)
        pred_class = model.predict(X_processed)[0]
        
        # Binary classification: [p_down, p_up]
        p_down = float(probs[0, 0])
        p_up = float(probs[0, 1])
        confidence = max(p_down, p_up)
        margin = abs(p_up - p_down)
        
        print(f"  Prediction: {'UP' if pred_class == 1 else 'DOWN'} (conf: {confidence:.3f}, p_up: {p_up:.3f}, p_down: {p_down:.3f})")
        
    except Exception as e:
        print(f"    Prediction failed: {e}")
        return None
    
    # 7. Store prediction
    pred_data = {
        'symbol': symbol,
        'date': next_trading_day,
        'horizon': horizon,
        'model_name': model_name,
        'split': 'production',
        'y_true': None,
        'pred_class_raw': int(pred_class),
        'pred_class_final': int(pred_class),
        'p_down': p_down,
        'p_up': p_up,
        'confidence': confidence,
        'margin': margin
    }
    
    try:
        result = db.client.table('model_predictions_classification').upsert(
            pred_data,
            on_conflict='symbol,date,horizon,model_name,split'
        ).execute()
        return 1
    except Exception as e:
        print(f"   Error storing prediction: {e}")
        return None


def main():
    """Generate predictions for all symbols and horizons."""
    print("=" * 70)
    print("Generating Real Model-Based Predictions")
    print("=" * 70)
    print(f"Symbols: {', '.join(SYMBOLS)}")
    print(f"Horizons: 1d, 5d")
    print(f"Model: xgboost")
    print("=" * 70)
    print()
    
    db = SupabaseDB()
    
    total_generated = 0
    horizons = ['1d', '5d']
    
    for symbol in SYMBOLS:
        print(f"Processing {symbol}...")
        
        for horizon in horizons:
            print(f"   {horizon} horizon...")
            result = predict_symbol(db, symbol, horizon, model_name='xgboost')
            
            if result == 1:
                print(f"     Inserted 1 prediction")
                total_generated += 1
            elif result == 0:
                print(f"     Prediction already exists")
            else:
                print(f"     Failed to generate prediction")
        
        print()
    
    print("=" * 70)
    if total_generated > 0:
        print(f" Complete! Generated {total_generated} new predictions")
    else:
        print(" Complete! All predictions up to date")
    print("=" * 70)
    print()
    print("  These predictions use trained XGBoost models with real probabilities")
    print("   and confidence scores based on model certainty.")
    print()


if __name__ == "__main__":
    main()
