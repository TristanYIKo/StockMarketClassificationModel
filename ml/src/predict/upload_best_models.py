"""
Upload test predictions from the best models (per horizon) to Supabase.

Identifies the most accurate model for each horizon and uploads only those predictions.
"""

import os
import sys
import pandas as pd
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from etl.supabase_client import SupabaseDB

logger = logging.getLogger(__name__)


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def identify_best_models(summary_path: str) -> dict:
    """
    Identify best model per horizon based on test accuracy.
    
    Args:
        summary_path: Path to summary CSV
        
    Returns:
        Dict mapping horizon to best model name
    """
    summary = pd.read_csv(summary_path)
    
    best_models = {}
    for horizon in ['1d', '5d']:
        horizon_df = summary[summary['horizon'] == horizon]
        best_idx = horizon_df['test_accuracy'].idxmax()
        best_model = horizon_df.loc[best_idx, 'model']
        best_acc = horizon_df.loc[best_idx, 'test_accuracy']
        
        best_models[horizon] = best_model
        logger.info(f"{horizon} best model: {best_model} (test accuracy: {best_acc:.4f})")
    
    return best_models


def load_test_predictions(horizon: str, model: str, reports_dir: str) -> pd.DataFrame:
    """
    Load test predictions for a specific horizon and model.
    
    Args:
        horizon: '1d' or '5d'
        model: Model name
        reports_dir: Path to reports directory
        
    Returns:
        DataFrame with test predictions
    """
    test_path = Path(reports_dir) / horizon / f"preds_{model}_test.parquet"
    
    if not test_path.exists():
        raise FileNotFoundError(f"Test predictions not found: {test_path}")
    
    df = pd.read_parquet(test_path)
    logger.info(f"Loaded {len(df)} test predictions for {horizon}/{model}")
    
    return df


def upload_to_supabase(df: pd.DataFrame, db: SupabaseDB, batch_size: int = 1000):
    """
    Upload predictions to Supabase table.
    
    Args:
        df: DataFrame with predictions
        db: SupabaseDB instance
        batch_size: Number of rows per batch
    """
    # Prepare data for upload
    records = df.to_dict('records')
    
    # Convert date to string format
    for record in records:
        if pd.notna(record['date']):
            record['date'] = pd.to_datetime(record['date']).strftime('%Y-%m-%d')
    
    logger.info(f"Uploading {len(records)} records to Supabase...")
    
    # Upload in batches
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        
        try:
            response = db.client.table('model_predictions_classification').upsert(
                batch,
                on_conflict='symbol,date,horizon,model_name,split'
            ).execute()
            
            logger.info(f"Uploaded batch {i//batch_size + 1}/{(len(records)-1)//batch_size + 1}")
            
        except Exception as e:
            logger.error(f"Error uploading batch {i//batch_size + 1}: {e}")
            raise
    
    logger.info(f"Successfully uploaded {len(records)} records")


def main():
    """Main execution."""
    setup_logging()
    
    # Paths
    ml_dir = Path(__file__).parent.parent.parent
    reports_dir = ml_dir / 'artifacts' / 'reports'
    summary_path = reports_dir / 'summary_by_horizon.csv'
    
    logger.info("=" * 70)
    logger.info("UPLOADING BEST MODEL PREDICTIONS TO SUPABASE")
    logger.info("=" * 70)
    
    # Check if summary exists
    if not summary_path.exists():
        logger.error(f"Summary not found: {summary_path}")
        logger.error("Run predict_and_store.py first to generate predictions")
        return
    
    # Identify best models
    logger.info("\nIdentifying best models...")
    best_models = identify_best_models(str(summary_path))
    
    # Initialize Supabase
    logger.info("\nConnecting to Supabase...")
    try:
        db = SupabaseDB()
        logger.info("Connected successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Supabase: {e}")
        logger.error("Make sure SUPABASE_URL and SUPABASE_KEY environment variables are set")
        return
    
    # Load and upload predictions for each horizon
    all_predictions = []
    
    for horizon, model in best_models.items():
        logger.info(f"\n{'='*70}")
        logger.info(f"Processing {horizon} - {model}")
        logger.info(f"{'='*70}")
        
        try:
            # Load test predictions
            df = load_test_predictions(horizon, model, str(reports_dir))
            
            # Add to collection
            all_predictions.append(df)
            
        except Exception as e:
            logger.error(f"Error processing {horizon}/{model}: {e}")
            continue
    
    # Combine all predictions
    if all_predictions:
        combined_df = pd.concat(all_predictions, ignore_index=True)
        logger.info(f"\n{'='*70}")
        logger.info(f"UPLOADING COMBINED PREDICTIONS")
        logger.info(f"{'='*70}")
        logger.info(f"Total records: {len(combined_df)}")
        logger.info(f"Date range: {combined_df['date'].min()} to {combined_df['date'].max()}")
        logger.info(f"Symbols: {sorted(combined_df['symbol'].unique())}")
        logger.info(f"Horizons: {sorted(combined_df['horizon'].unique())}")
        
        # Upload to Supabase
        upload_to_supabase(combined_df, db)
        
        logger.info(f"\n{'='*70}")
        logger.info("UPLOAD COMPLETE")
        logger.info(f"{'='*70}")
        
        # Summary statistics
        for horizon in combined_df['horizon'].unique():
            horizon_df = combined_df[combined_df['horizon'] == horizon]
            accuracy = (horizon_df['y_true'] == horizon_df['pred_class_final']).mean()
            logger.info(f"{horizon} - {len(horizon_df)} predictions, {accuracy:.4f} accuracy")
    
    else:
        logger.error("No predictions were loaded")


if __name__ == '__main__':
    main()
