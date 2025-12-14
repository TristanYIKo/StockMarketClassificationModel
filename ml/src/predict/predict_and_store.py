"""
Multi-horizon prediction pipeline with calibration and gating.

Supports both 1d and 5d horizons with separate calibration and thresholds.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
import yaml
import joblib
import pandas as pd
import numpy as np


class XGBWrapper:
    """Wrapper for XGBoost that handles label mapping for classification."""
    def __init__(self, model, label_mapping):
        self.model = model
        self.label_mapping = label_mapping  # {0: -1, 1: 0, 2: 1}
    
    def predict(self, X):
        # Predict with mapped labels (0,1,2) and convert back to (-1,0,1)
        preds_mapped = self.model.predict(X)
        return np.array([self.label_mapping[int(p)] for p in preds_mapped])
    
    def predict_proba(self, X):
        return self.model.predict_proba(X)

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.utils.io import load_from_csv, load_from_supabase
from src.utils.splits import create_time_splits, prepare_X_y
from src.utils.calibration import calibrate_probabilities, save_calibrator, load_calibrator, MulticlassCalibrator
from src.utils.decision import compute_pred_features, apply_gating, tune_thresholds, evaluate_gating, save_thresholds, load_thresholds
from etl.supabase_client import SupabaseDB

logger = logging.getLogger(__name__)


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def load_registry(registry_path: str) -> dict:
    """Load model registry."""
    with open(registry_path, 'r') as f:
        registry = yaml.safe_load(f)
    return registry


def get_raw_predictions(model, preprocessor, X: pd.DataFrame) -> np.ndarray:
    """
    Get raw probabilities from model.
    
    Returns:
        probs: (N, 3) array of [p_sell, p_hold, p_buy]
    """
    X_processed = preprocessor.transform(X, split_name='inference')
    
    # Get probabilities
    probs = model.predict_proba(X_processed)
    
    # Ensure shape is (N, 3) and ordered as [-1, 0, 1]
    if probs.shape[1] != 3:
        raise ValueError(f"Expected 3 classes, got {probs.shape[1]}")
    
    return probs


def create_prediction_dataframe(
    df: pd.DataFrame,
    y: np.ndarray,
    probs_cal: np.ndarray,
    pred_class_raw: np.ndarray,
    pred_class_final: np.ndarray,
    confidence: np.ndarray,
    margin: np.ndarray,
    horizon: str,
    model_name: str,
    split: str
) -> pd.DataFrame:
    """Create dataframe with all prediction info."""
    return pd.DataFrame({
        'symbol': df['symbol'].values,
        'date': df['date'].values,
        'horizon': horizon,
        'model_name': model_name,
        'split': split,
        'y_true': y,
        'pred_class_raw': pred_class_raw,
        'pred_class_final': pred_class_final,
        'p_sell': probs_cal[:, 0],
        'p_hold': probs_cal[:, 1],
        'p_buy': probs_cal[:, 2],
        'confidence': confidence,
        'margin': margin
    })


def upsert_predictions_to_supabase(df: pd.DataFrame, db: SupabaseDB):
    """Upsert predictions to Supabase."""
    data = df.to_dict('records')
    
    # Convert dates to strings
    for row in data:
        row['date'] = str(row['date'].date()) if hasattr(row['date'], 'date') else str(row['date'])
        # Convert numpy types to Python types
        for key, val in row.items():
            if isinstance(val, (np.integer, np.floating)):
                row[key] = float(val) if 'p_' in key or key in ['confidence', 'margin'] else int(val)
    
    # Batch upsert
    batch_size = 1000
    for i in range(0, len(data), batch_size):
        chunk = data[i:i+batch_size]
        db.client.table('model_predictions_classification').upsert(
            chunk,
            on_conflict='symbol,date,horizon,model_name,split'
        ).execute()
    
    logger.info(f"Upserted {len(data)} predictions to Supabase")


def process_horizon_model(
    horizon: str,
    model_info: dict,
    registry: dict,
    splits: dict,
    args,
    db: SupabaseDB = None
):
    """Process predictions for a single horizon and model."""
    logger.info("\n" + "=" * 70)
    logger.info(f"PROCESSING: {horizon.upper()} - {model_info['name']}")
    logger.info("=" * 70)
    
    # Load model and preprocessor
    model_path = model_info['path']
    preprocessor_path = model_info['preprocessor_path']
    
    if not os.path.exists(model_path):
        logger.warning(f"Model not found: {model_path}. Skipping.")
        return
    
    model = joblib.load(model_path)
    preprocessor = joblib.load(preprocessor_path)
    logger.info(f"Loaded model from {model_path}")
    
    # Prepare data
    target_col = registry['horizons'][horizon]['target_col']
    X_val, y_val = prepare_X_y(splits['val'], target_col=target_col)
    X_test, y_test = prepare_X_y(splits['test'], target_col=target_col)
    
    # Get raw predictions
    logger.info("Computing raw predictions...")
    probs_val_raw = get_raw_predictions(model, preprocessor, X_val)
    probs_test_raw = get_raw_predictions(model, preprocessor, X_test)
    
    # Calibration
    calibrator_dir = Path(f"ml/artifacts/calibrators/{horizon}")
    calibrator_dir.mkdir(parents=True, exist_ok=True)
    calibrator_path = calibrator_dir / f"{model_info['name']}_ovr.joblib"
    
    if args.recalibrate or not calibrator_path.exists():
        probs_val_cal, probs_test_cal, calibrator, cal_metrics = calibrate_probabilities(
            probs_val_raw, y_val.values,
            probs_test_raw, y_test.values
        )
        save_calibrator(calibrator, str(calibrator_path))
    else:
        logger.info(f"Loading existing calibrator from {calibrator_path}")
        calibrator = load_calibrator(str(calibrator_path))
        probs_val_cal = calibrator.transform(probs_val_raw)
        probs_test_cal = calibrator.transform(probs_test_raw)
    
    # Compute prediction features
    pred_raw_val, conf_val, margin_val = compute_pred_features(probs_val_cal)
    pred_raw_test, conf_test, margin_test = compute_pred_features(probs_test_cal)
    
    # Threshold tuning
    thresholds_dir = Path(f"ml/artifacts/thresholds/{horizon}")
    thresholds_dir.mkdir(parents=True, exist_ok=True)
    thresholds_path = thresholds_dir / f"{model_info['name']}.json"
    
    if args.retune or not thresholds_path.exists():
        thresholds = tune_thresholds(probs_val_cal, y_val.values, horizon)
        save_thresholds(thresholds, str(thresholds_path))
    else:
        logger.info(f"Loading existing thresholds from {thresholds_path}")
        thresholds = load_thresholds(str(thresholds_path))
    
    # Apply gating
    pred_final_val = apply_gating(
        pred_raw_val, conf_val, margin_val,
        thresholds['conf_thresh'], thresholds['margin_thresh']
    )
    pred_final_test = apply_gating(
        pred_raw_test, conf_test, margin_test,
        thresholds['conf_thresh'], thresholds['margin_thresh']
    )
    
    # Evaluate
    logger.info("\nVAL Metrics (after gating):")
    val_metrics = evaluate_gating(y_val.values, pred_final_val)
    for k, v in val_metrics.items():
        logger.info(f"  {k}: {v:.4f}")
    
    logger.info("\nTEST Metrics (after gating):")
    test_metrics = evaluate_gating(y_test.values, pred_final_test)
    for k, v in test_metrics.items():
        logger.info(f"  {k}: {v:.4f}")
    
    # Create prediction dataframes
    df_val = create_prediction_dataframe(
        splits['val'], y_val.values, probs_val_cal,
        pred_raw_val, pred_final_val, conf_val, margin_val,
        horizon, model_info['name'], 'val'
    )
    
    df_test = create_prediction_dataframe(
        splits['test'], y_test.values, probs_test_cal,
        pred_raw_test, pred_final_test, conf_test, margin_test,
        horizon, model_info['name'], 'test'
    )
    
    # Save to parquet
    reports_dir = Path(f"ml/artifacts/reports/{horizon}")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    df_val.to_parquet(reports_dir / f"preds_{model_info['name']}_val.parquet", index=False)
    df_test.to_parquet(reports_dir / f"preds_{model_info['name']}_test.parquet", index=False)
    logger.info(f"Saved predictions to {reports_dir}")
    
    # Store in Supabase if requested
    if args.store_db and db is not None:
        upsert_predictions_to_supabase(pd.concat([df_val, df_test]), db)
    
    return {
        'horizon': horizon,
        'model': model_info['name'],
        'val_metrics': val_metrics,
        'test_metrics': test_metrics,
        'thresholds': thresholds
    }


def main():
    parser = argparse.ArgumentParser(description='Multi-horizon prediction pipeline')
    parser.add_argument('--horizon', type=str, default='all', choices=['1d', '5d', 'all'],
                        help='Prediction horizon')
    parser.add_argument('--model', type=str, default='all',
                        help='Model name (or "all" for all models)')
    parser.add_argument('--data_source', type=str, default='csv', choices=['csv', 'supabase'],
                        help='Data source')
    parser.add_argument('--csv_path_1d', type=str, default='classification_dataset.csv',
                        help='Path to 1d CSV file')
    parser.add_argument('--csv_path_5d', type=str, default='classification_dataset_5d.csv',
                        help='Path to 5d CSV file')
    parser.add_argument('--store_db', action='store_true',
                        help='Store predictions in Supabase')
    parser.add_argument('--recalibrate', action='store_true',
                        help='Force recalibration even if calibrator exists')
    parser.add_argument('--retune', action='store_true',
                        help='Force threshold retuning even if thresholds exist')
    args = parser.parse_args()
    
    setup_logging()
    
    # Load registry
    registry_path = 'ml/config/model_registry.yaml'
    registry = load_registry(registry_path)
    logger.info(f"Loaded registry from {registry_path}")
    
    # Connect to Supabase if needed
    db = None
    if args.store_db:
        db = SupabaseDB()
        logger.info("Connected to Supabase")
    
    # Determine horizons to process
    horizons_to_process = ['1d', '5d'] if args.horizon == 'all' else [args.horizon]
    
    # Load config for splits
    config_path = 'ml/config/model_config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    all_results = []
    
    for horizon in horizons_to_process:
        logger.info(f"\n{'='*70}")
        logger.info(f"HORIZON: {horizon.upper()}")
        logger.info(f"{'='*70}")
        
        # Load data
        if args.data_source == 'csv':
            csv_path = args.csv_path_1d if horizon == '1d' else args.csv_path_5d
            df = load_from_csv(csv_path)
        else:
            # Supabase view names
            view_name = f'v_classification_dataset_{horizon}'
            df = load_from_supabase(view_name=view_name)
        
        # Create splits
        splits = create_time_splits(
            df,
            train_start=config['splits']['train_start'],
            train_end=config['splits']['train_end'],
            val_start=config['splits']['val_start'],
            val_end=config['splits']['val_end'],
            test_start=config['splits']['test_start'],
            test_end=config['splits']['test_end'],
            target_col=registry['horizons'][horizon]['target_col']
        )
        
        # Determine models to process
        models_to_process = registry['horizons'][horizon]['models']
        if args.model != 'all':
            models_to_process = [m for m in models_to_process if m['name'] == args.model]
        
        # Process each model
        for model_info in models_to_process:
            result = process_horizon_model(
                horizon, model_info, registry, splits, args, db
            )
            if result:
                all_results.append(result)
    
    # Generate summary report
    if all_results:
        summary_df = pd.DataFrame([
            {
                'horizon': r['horizon'],
                'model': r['model'],
                'val_accuracy': r['val_metrics']['accuracy'],
                'val_f1_macro': r['val_metrics']['f1_macro'],
                'val_f1_action': r['val_metrics']['f1_action'],
                'val_trade_rate': r['val_metrics']['trade_rate'],
                'test_accuracy': r['test_metrics']['accuracy'],
                'test_f1_macro': r['test_metrics']['f1_macro'],
                'test_f1_action': r['test_metrics']['f1_action'],
                'test_trade_rate': r['test_metrics']['trade_rate'],
                'conf_thresh': r['thresholds']['conf_thresh'],
                'margin_thresh': r['thresholds']['margin_thresh']
            }
            for r in all_results
        ])
        
        # Save summary
        summary_path = Path('ml/artifacts/reports/summary_by_horizon.csv')
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_df.to_csv(summary_path, index=False)
        logger.info(f"\nSaved summary to {summary_path}")
        
        # Print summary
        logger.info("\n" + "=" * 70)
        logger.info("SUMMARY BY HORIZON")
        logger.info("=" * 70)
        print(summary_df.to_string(index=False))
    
    logger.info("\n" + "=" * 70)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
