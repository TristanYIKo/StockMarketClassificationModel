"""
Main training script for stock market classification models.
Supports multiple models with time-series safe evaluation.
"""

import os
import sys
import argparse
import logging
from datetime import datetime
import yaml
import joblib
import json

import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.utils.io import load_from_csv, load_from_supabase
from src.utils.splits import create_time_splits, prepare_X_y
from src.utils.preprocess import TimeSeriesPreprocessor, compute_class_weights
from src.utils.metrics import evaluate_model, compare_models

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
import lightgbm as lgb
import xgboost as xgb


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('ml/artifacts/training.log', mode='w')
        ]
    )
    return logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def train_logistic_regression(X_train, y_train, class_weights, config):
    """Train Logistic Regression model."""
    logger = logging.getLogger(__name__)
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING: LOGISTIC REGRESSION")
    logger.info("=" * 70)
    
    params = config['models']['logistic_regression']
    
    model = LogisticRegression(
        max_iter=params['max_iter'],
        class_weight='balanced',
        random_state=params['random_state'],
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    logger.info("Logistic Regression trained successfully")
    
    return model


def train_random_forest(X_train, y_train, class_weights, config):
    """Train Random Forest model."""
    logger = logging.getLogger(__name__)
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING: RANDOM FOREST")
    logger.info("=" * 70)
    
    params = config['models']['random_forest']
    
    model = RandomForestClassifier(
        n_estimators=params['n_estimators'],
        max_depth=params['max_depth'],
        min_samples_split=params['min_samples_split'],
        class_weight='balanced',
        random_state=params['random_state'],
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    logger.info("Random Forest trained successfully")
    
    return model


def train_lightgbm(X_train, y_train, class_weights, config):
    """Train LightGBM model."""
    logger = logging.getLogger(__name__)
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING: LIGHTGBM")
    logger.info("=" * 70)
    
    params = config['models']['lightgbm']
    
    model = lgb.LGBMClassifier(
        n_estimators=params['n_estimators'],
        learning_rate=params['learning_rate'],
        max_depth=params['max_depth'],
        num_leaves=params['num_leaves'],
        class_weight='balanced',
        random_state=params['random_state'],
        verbosity=-1,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    logger.info("LightGBM trained successfully")
    
    return model


def train_xgboost(X_train, y_train, class_weights, config):
    """Train XGBoost model."""
    logger = logging.getLogger(__name__)
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING: XGBOOST")
    logger.info("=" * 70)
    
    params = config['models']['xgboost']
    
    # Convert class weights to sample weights
    sample_weights = np.array([class_weights[y] for y in y_train])
    
    model = xgb.XGBClassifier(
        n_estimators=params['n_estimators'],
        learning_rate=params['learning_rate'],
        max_depth=params['max_depth'],
        random_state=params['random_state'],
        n_jobs=-1,
        tree_method='hist'
    )
    
    model.fit(X_train, y_train, sample_weight=sample_weights)
    logger.info("XGBoost trained successfully")
    
    return model


def save_artifacts(model, preprocessor, model_name, config, metrics, feature_names):
    """Save trained model and metadata."""
    logger = logging.getLogger(__name__)
    
    # Create artifacts directory
    model_dir = f"ml/artifacts/models/{model_name}"
    os.makedirs(model_dir, exist_ok=True)
    
    # Save model
    model_path = os.path.join(model_dir, 'model.pkl')
    joblib.dump(model, model_path)
    logger.info(f"Saved model to {model_path}")
    
    # Save preprocessor
    preprocessor_path = os.path.join(model_dir, 'preprocessor.pkl')
    joblib.dump(preprocessor, preprocessor_path)
    logger.info(f"Saved preprocessor to {preprocessor_path}")
    
    # Save metadata
    metadata = {
        'model_name': model_name,
        'timestamp': datetime.now().isoformat(),
        'config': config,
        'metrics': {k: float(v) for k, v in metrics.items()},
        'n_features': len(feature_names),
        'feature_names': feature_names
    }
    
    metadata_path = os.path.join(model_dir, 'metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Saved metadata to {metadata_path}")


def main():
    """Main training pipeline."""
    # Parse arguments
    parser = argparse.ArgumentParser(description='Train classification models')
    parser.add_argument('--config', type=str, default='ml/config/model_config.yaml',
                        help='Path to config file')
    parser.add_argument('--data_source', type=str, default='csv',
                        choices=['csv', 'supabase'],
                        help='Data source: csv or supabase')
    parser.add_argument('--csv_path', type=str, default='classification_dataset.csv',
                        help='Path to CSV file (if data_source=csv)')
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging()
    logger.info("=" * 70)
    logger.info("STOCK MARKET CLASSIFICATION MODEL - TRAINING PIPELINE")
    logger.info("=" * 70)
    logger.info(f"Data source: {args.data_source}")
    logger.info(f"Config: {args.config}")
    
    # Load config
    config = load_config(args.config)
    
    # Load data
    logger.info("\n" + "=" * 70)
    logger.info("LOADING DATA")
    logger.info("=" * 70)
    
    if args.data_source == 'csv':
        df = load_from_csv(args.csv_path)
    else:
        df = load_from_supabase()
    
    # Create time-based splits
    splits = create_time_splits(
        df,
        train_start=config['data']['train_start'],
        train_end=config['data']['train_end'],
        val_start=config['data']['val_start'],
        val_end=config['data']['val_end'],
        test_start=config['data']['test_start'],
        test_end=config['data']['test_end']
    )
    
    # Prepare X, y for each split
    X_train, y_train = prepare_X_y(splits['train'])
    X_val, y_val = prepare_X_y(splits['val'])
    X_test, y_test = prepare_X_y(splits['test'])
    
    # Fit preprocessor on TRAINING data only
    logger.info("\n" + "=" * 70)
    logger.info("PREPROCESSING")
    logger.info("=" * 70)
    
    preprocessor = TimeSeriesPreprocessor(
        drop_features_threshold=config['preprocessing']['drop_features_threshold'],
        imputation_strategy=config['preprocessing']['imputation_strategy'],
        scaling=config['preprocessing']['scaling']
    )
    
    X_train_processed = preprocessor.fit_transform(X_train)
    X_val_processed = preprocessor.transform(X_val, split_name='val')
    X_test_processed = preprocessor.transform(X_test, split_name='test')
    
    feature_names = preprocessor.get_feature_names()
    logger.info(f"\nFinal feature count: {len(feature_names)}")
    
    # Compute class weights
    class_weights = compute_class_weights(y_train)
    
    # Train models
    models = {}
    all_results = {}
    
    target_names = ['Sell (-1)', 'Hold (0)', 'Buy (1)']
    
    # Logistic Regression
    if 'logistic_regression' in config['models']:
        model_name = 'logistic_regression'
        model = train_logistic_regression(X_train_processed, y_train, class_weights, config)
        models[model_name] = model
        
        # Evaluate
        train_metrics = evaluate_model(
            model, X_train_processed, y_train, 'train',
            target_names=target_names,
            save_dir='ml/artifacts/figures'
        )
        val_metrics = evaluate_model(
            model, X_val_processed, y_val, 'val',
            target_names=target_names,
            save_dir='ml/artifacts/figures'
        )
        test_metrics = evaluate_model(
            model, X_test_processed, y_test, 'test',
            target_names=target_names,
            save_dir='ml/artifacts/figures'
        )
        
        # Store results
        all_results[model_name] = {
            'train_accuracy': train_metrics['accuracy'],
            'train_f1_macro': train_metrics['f1_macro'],
            'val_accuracy': val_metrics['accuracy'],
            'val_f1_macro': val_metrics['f1_macro'],
            'test_accuracy': test_metrics['accuracy'],
            'test_f1_macro': test_metrics['f1_macro']
        }
        
        # Save artifacts
        save_artifacts(model, preprocessor, model_name, config, val_metrics, feature_names)
    
    # Random Forest
    if 'random_forest' in config['models']:
        model_name = 'random_forest'
        model = train_random_forest(X_train_processed, y_train, class_weights, config)
        models[model_name] = model
        
        train_metrics = evaluate_model(
            model, X_train_processed, y_train, 'train',
            target_names=target_names,
            save_dir='ml/artifacts/figures'
        )
        val_metrics = evaluate_model(
            model, X_val_processed, y_val, 'val',
            target_names=target_names,
            save_dir='ml/artifacts/figures'
        )
        test_metrics = evaluate_model(
            model, X_test_processed, y_test, 'test',
            target_names=target_names,
            save_dir='ml/artifacts/figures'
        )
        
        all_results[model_name] = {
            'train_accuracy': train_metrics['accuracy'],
            'train_f1_macro': train_metrics['f1_macro'],
            'val_accuracy': val_metrics['accuracy'],
            'val_f1_macro': val_metrics['f1_macro'],
            'test_accuracy': test_metrics['accuracy'],
            'test_f1_macro': test_metrics['f1_macro']
        }
        
        save_artifacts(model, preprocessor, model_name, config, val_metrics, feature_names)
    
    # LightGBM
    if 'lightgbm' in config['models']:
        model_name = 'lightgbm'
        model = train_lightgbm(X_train_processed, y_train, class_weights, config)
        models[model_name] = model
        
        train_metrics = evaluate_model(
            model, X_train_processed, y_train, 'train',
            target_names=target_names,
            save_dir='ml/artifacts/figures'
        )
        val_metrics = evaluate_model(
            model, X_val_processed, y_val, 'val',
            target_names=target_names,
            save_dir='ml/artifacts/figures'
        )
        test_metrics = evaluate_model(
            model, X_test_processed, y_test, 'test',
            target_names=target_names,
            save_dir='ml/artifacts/figures'
        )
        
        all_results[model_name] = {
            'train_accuracy': train_metrics['accuracy'],
            'train_f1_macro': train_metrics['f1_macro'],
            'val_accuracy': val_metrics['accuracy'],
            'val_f1_macro': val_metrics['f1_macro'],
            'test_accuracy': test_metrics['accuracy'],
            'test_f1_macro': test_metrics['f1_macro']
        }
        
        save_artifacts(model, preprocessor, model_name, config, val_metrics, feature_names)
    
    # XGBoost
    if 'xgboost' in config['models']:
        model_name = 'xgboost'
        model = train_xgboost(X_train_processed, y_train, class_weights, config)
        models[model_name] = model
        
        train_metrics = evaluate_model(
            model, X_train_processed, y_train, 'train',
            target_names=target_names,
            save_dir='ml/artifacts/figures'
        )
        val_metrics = evaluate_model(
            model, X_val_processed, y_val, 'val',
            target_names=target_names,
            save_dir='ml/artifacts/figures'
        )
        test_metrics = evaluate_model(
            model, X_test_processed, y_test, 'test',
            target_names=target_names,
            save_dir='ml/artifacts/figures'
        )
        
        all_results[model_name] = {
            'train_accuracy': train_metrics['accuracy'],
            'train_f1_macro': train_metrics['f1_macro'],
            'val_accuracy': val_metrics['accuracy'],
            'val_f1_macro': val_metrics['f1_macro'],
            'test_accuracy': test_metrics['accuracy'],
            'test_f1_macro': test_metrics['f1_macro']
        }
        
        save_artifacts(model, preprocessor, model_name, config, val_metrics, feature_names)
    
    # Compare models
    logger.info("\n" + "=" * 70)
    logger.info("FINAL COMPARISON")
    logger.info("=" * 70)
    compare_models(all_results, save_path='ml/artifacts/figures/model_comparison.png')
    
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING COMPLETE")
    logger.info("=" * 70)
    logger.info("Artifacts saved to ml/artifacts/")


if __name__ == '__main__':
    main()
