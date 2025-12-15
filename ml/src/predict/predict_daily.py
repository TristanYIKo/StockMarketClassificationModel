
import os
import sys
import pandas as pd
import joblib
import json
import numpy as np
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load env before other imports
load_dotenv()


# Add parent directories to path
# We need both the project root (for etl) and 'ml' (for src) 
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, 'ml'))

from etl.supabase_client import SupabaseDB

def fetch_latest_features(db: SupabaseDB, lookback_days: int = 5) -> pd.DataFrame:
    """
    Fetch the most recent feature rows from Supabase.
    Unlike the training views, this pulls RAW features_daily which includes today's data.
    """
    print(f"Fetching features for last {lookback_days} days...")
    
    # 1. Fetch Assets
    assets = db.client.table("assets").select("id, symbol").execute()
    assets_map = {row['id']: row['symbol'] for row in assets.data}
    
    # 2. Fetch Features
    # We can't do complex joins or filtering easily in one go with simple client, 
    # so we'll fetch a range and filter in pandas.
    latest_date = db.get_latest_date()
    if not latest_date:
        print("No data found in DB.")
        return pd.DataFrame()
        
    start_date = (datetime.fromisoformat(latest_date) - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    
    # Pagination loop just in case
    all_rows = []
    print(f"Querying from {start_date}...")
    
    response = db.client.table("features_daily")\
        .select("asset_id, date, feature_json")\
        .gte("date", start_date)\
        .execute()
        
    all_rows.extend(response.data)
    
    if not all_rows:
        return pd.DataFrame()
        
    # 3. Convert to DataFrame
    df = pd.DataFrame(all_rows)
    df['symbol'] = df['asset_id'].map(assets_map)
    df['date'] = pd.to_datetime(df['date'])
    
    # Unpack JSON features
    print("Unpacking feature JSON...")
    
    # feature_json might be a dict or a string depending on how it came back
    # The client might have auto-parsed it if it was JSON type in postgres
    
    # Normalize feature_json
    def parse_json(x):
        if isinstance(x, str):
            return json.loads(x)
        return x

    df['feature_json'] = df['feature_json'].apply(parse_json)
    features_unpacked = df['feature_json'].apply(pd.Series)
    
    # Combine
    full_df = pd.concat([df[['symbol', 'date']], features_unpacked], axis=1)
    
    # Sort and Keep only the LATEST row per symbol
    latest_df = full_df.sort_values('date').groupby('symbol').tail(1).reset_index(drop=True)
    
    print(f"Found latest data for {len(latest_df)} symbols. Date: {latest_df['date'].max().date()}")
    return latest_df

def load_prediction_artifacts(model_name: str):
    """Load model and preprocessor."""
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'artifacts', 'models', model_name)
    
    model_path = os.path.join(base_dir, 'model.pkl')
    preproc_path = os.path.join(base_dir, 'preprocessor.pkl')
    
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found at {model_path}")
        
    print(f"Loading {model_name} from {base_dir}...")
    model = joblib.load(model_path)
    preprocessor = joblib.load(preproc_path)
    
    return model, preprocessor

class XGBWrapper:
    """Re-definition of wrapper since we can't easily import it without circular deps or path issues if not careful."""
    def __init__(self, model, label_mapping):
        self.model = model
        self.label_mapping = label_mapping
    
    def predict(self, X):
        preds_mapped = self.model.predict(X)
        return np.array([self.label_mapping[int(p)] for p in preds_mapped])
    
    def predict_proba(self, X):
        return self.model.predict_proba(X)

# We need to make sure the customized class is available in main if pickle needs it,
# but usually joblib saves the class definition ref. If it fails, we might need to import the exact class from training script.
# For now, let's try loading.


def upsert_predictions(db: SupabaseDB, results: pd.DataFrame):
    """Upsert predictions to Supabase."""
    if results.empty:
        return
        
    print(f"Upserting {len(results)} predictions to Supabase...")
    
    # Prepare data for model_predictions_classification table
    # Schema: symbol, date, horizon, model_name, split, y_true, pred_class_raw, pred_class_final, 
    #         p_sell, p_hold, p_buy, confidence, margin, created_at
    
    records = []
    now_iso = datetime.now().isoformat()
    
    for _, row in results.iterrows():
        record = {
            "symbol": row['symbol'],
            "date": row['date'].strftime('%Y-%m-%d'),
            "horizon": row['horizon'],
            "model_name": row['model_name'],
            "split": "inference",
            "y_true": None,
            "pred_class_raw": int(row['prediction']),
            "pred_class_final": int(row['prediction']), # Gating not applied here yet
            "p_sell": float(row['p_sell']),
            "p_hold": float(row['p_hold']),
            "p_buy": float(row['p_buy']),
            "confidence": float(max(row['p_sell'], row['p_hold'], row['p_buy'])),
            "margin": float(abs(row['p_buy'] - row['p_sell'])), # Approximation
            #"created_at": now_iso # specific to supabase auto-gen usually
        }
        records.append(record)
        
    try:
        # UPSERT
        # on_conflict needs to match the unique constraint of the table
        # usually (symbol, date, horizon, model_name, split)
        db.client.table("model_predictions_classification").upsert(
            records, 
            on_conflict="symbol,date,horizon,model_name,split"
        ).execute()
        print("✅ Upsert successful.")
    except Exception as e:
        print(f"❌ Upsert failed: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_base", type=str, default="xgboost", help="Base model name (xgboost, lightgbm, etc)")
    args = parser.parse_args()
    
    db = SupabaseDB()
    
    # 1. Get Data
    df = fetch_latest_features(db)
    if df.empty:
        print("No data available.")
        return

    all_results = []
    
    # 2. Loop Horizons
    horizons = [('1d', ''), ('5d', '_5d')]
    
    print("\n" + "="*60)
    print(f"GENERATING PREDICTIONS FOR {df['date'].max().date()}")
    print("="*60)
    
    for horizon_name, suffix in horizons:
        model_name = args.model_base + suffix
        print(f"\nHorizon: {horizon_name.upper()} | Model: {model_name}")
        
        try:
            model, preprocessor = load_prediction_artifacts(model_name)
        except Exception as e:
            print(f"  Skipping {model_name}: {e}")
            continue

        # 3. Preprocess
        try:
            X_processed = preprocessor.transform(df, split_name='test')
        except Exception as e:
            print(f"  Preprocessing failed: {e}")
            continue

        # 4. Predict
        probs = model.predict_proba(X_processed)
        preds = model.predict(X_processed)
        
        # 5. Format
        res = df[['symbol', 'date']].copy()
        res['horizon'] = horizon_name
        res['model_name'] = args.model_base
        res['prediction'] = preds
        res['p_sell'] = probs[:, 0]
        res['p_hold'] = probs[:, 1]
        res['p_buy'] = probs[:, 2]
        
        # Recommendation String
        def get_rec(row):
            p = row['prediction']
            conf = max(row['p_sell'], row['p_hold'], row['p_buy'])
            label = "HOLD"
            if p == 1: label = "BUY"
            if p == -1: label = "SELL"
            return f"{label} ({conf:.2f})"
            
        res['rec'] = res.apply(get_rec, axis=1)
        all_results.append(res)
        
        # Print Table
        print(res[['symbol', 'rec', 'p_sell', 'p_hold', 'p_buy']].to_string(index=False))

    # 6. Upsert to DB
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        upsert_predictions(db, final_df)
    
    print("\nRun complete.")

if __name__ == "__main__":
    main()
