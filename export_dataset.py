"""
Export full classification dataset from Supabase to CSV.
Uses raw tables (faster than view) and unpacks JSON features.
"""

from dotenv import load_dotenv
load_dotenv()

from etl.supabase_client import SupabaseDB
import pandas as pd
import json

def export_dataset():
    db = SupabaseDB()
    
    print("Fetching labels and features from raw tables...")
    
    # Fetch labels with pagination
    print("1/3 Fetching labels_daily...")
    all_labels = []
    offset = 0
    batch_size = 1000
    while True:
        result = db.client.table('labels_daily')\
            .select('asset_id, date, y_class_1d')\
            .not_.is_('y_class_1d', 'null')\
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
    
    # Fetch assets for symbol mapping
    print("3/3 Fetching assets...")
    assets_result = db.client.table('assets')\
        .select('id, symbol')\
        .eq('asset_type', 'ETF')\
        .execute()
    assets_df = pd.DataFrame(assets_result.data)
    assets_map = dict(zip(assets_df['id'], assets_df['symbol']))
    print(f"   ✅ Assets: {len(assets_df)} symbols")
    
    print("\nUnpacking feature JSON...")
    # Unpack JSON to columns
    features_unpacked = pd.json_normalize(features_df['feature_json'])
    features_final = pd.concat([
        features_df[['asset_id', 'date']], 
        features_unpacked
    ], axis=1)
    
    print("Merging labels + features...")
    # Merge
    df = labels_df.merge(features_final, on=['asset_id', 'date'], how='inner')
    df['symbol'] = df['asset_id'].map(assets_map)
    
    # Drop asset_id, reorder columns
    df = df.drop('asset_id', axis=1)
    cols = ['symbol', 'date', 'y_class_1d'] + [c for c in df.columns if c not in ['symbol', 'date', 'y_class_1d']]
    df = df[cols]
    
    print(f"\n✅ Dataset ready!")
    print(f"   Shape: {df.shape}")
    print(f"   Rows per symbol:")
    print(df.groupby('symbol').size())
    
    # Save to CSV
    output_file = 'classification_dataset.csv'
    df.to_csv(output_file, index=False)
    print(f"\n✅ Exported to {output_file}")
    
    # Show class distribution
    print(f"\nClass distribution:")
    print(df['y_class_1d'].value_counts().sort_index())
    
    return df

if __name__ == '__main__':
    export_dataset()
