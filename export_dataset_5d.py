"""
Export 5-day (weekly) classification dataset from Supabase to CSV.
Uses raw tables (faster than view) and unpacks JSON features.
"""

from dotenv import load_dotenv
load_dotenv()

from etl.supabase_client import SupabaseDB
import pandas as pd
import json

def export_dataset_5d():
    db = SupabaseDB()
    
    print("Fetching labels and features from raw tables...")
    
    # Fetch 5-day labels with pagination (include both for compatibility)
    print("1/3 Fetching labels_daily (y_class_5d)...")
    all_labels = []
    offset = 0
    batch_size = 1000
    while True:
        result = db.client.table('labels_daily')\
            .select('asset_id, date, y_class_1d, y_class_5d')\
            .not_.is_('y_class_5d', 'null')\
            .range(offset, offset + batch_size - 1)\
            .execute()
        if not result.data:
            break
        all_labels.extend(result.data)
        print(f"   {len(all_labels)} labels...")
        offset += batch_size
        if len(result.data) < batch_size:
            break
    labels_df = pd.DataFrame(all_labels)
    print(f"   ✅ Labels: {len(labels_df)} rows")
    
    # Fetch features with pagination
    print("2/3 Fetching features_daily...")
    all_features = []
    offset = 0
    while True:
        result = db.client.table('features_daily')\
            .select('asset_id, date, feature_json')\
            .range(offset, offset + batch_size - 1)\
            .execute()
        if not result.data:
            break
        all_features.extend(result.data)
        print(f"   {len(all_features)} features...")
        offset += batch_size
        if len(result.data) < batch_size:
            break
    features_df = pd.DataFrame(all_features)
    print(f"   ✅ Features: {len(features_df)} rows")
    
    # Fetch assets
    print("3/3 Fetching assets...")
    assets_result = db.client.table('assets').select('id, symbol').execute()
    assets_df = pd.DataFrame(assets_result.data)
    print(f"   ✅ Assets: {len(assets_df)} symbols\n")
    
    print("Unpacking feature JSON...")
    # Unpack feature_json into columns (already dict, no json.loads needed)
    features_unpacked = features_df['feature_json'].apply(pd.Series)
    features_df = pd.concat([features_df[['asset_id', 'date']], features_unpacked], axis=1)
    
    print("Merging labels + features...")
    # Merge labels with features
    merged = labels_df.merge(features_df, on=['asset_id', 'date'], how='inner')
    
    # Merge with asset symbols
    merged = merged.merge(assets_df, left_on='asset_id', right_on='id', how='left')
    merged = merged.drop(columns=['asset_id', 'id'])
    
    print(f"\n✅ Dataset ready!")
    print(f"   Shape: {merged.shape}")
    print(f"   Rows per symbol:")
    print(merged['symbol'].value_counts().sort_index())
    
    # Export to CSV
    output_path = 'classification_dataset_5d.csv'
    merged.to_csv(output_path, index=False)
    print(f"\n✅ Exported to {output_path}")
    
    # Show target distribution
    print(f"\nClass distribution:")
    print(merged['y_class_5d'].value_counts().sort_index())
    
    return merged

if __name__ == '__main__':
    export_dataset_5d()
