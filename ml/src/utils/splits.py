"""
Time-series safe train/val/test splits.
CRITICAL: No random splits - only chronological splits.
"""

import pandas as pd
from typing import Tuple, Dict
import logging

logger = logging.getLogger(__name__)


def create_time_splits(
    df: pd.DataFrame,
    train_start: str,
    train_end: str,
    val_start: str,
    val_end: str,
    test_start: str,
    test_end: str
) -> Dict[str, pd.DataFrame]:
    """
    Create time-based train/val/test splits.
    
    CRITICAL: Splits are based on date, not random sampling.
    All symbols are included in each split.
    
    Args:
        df: Full dataset with 'date' column
        train_start, train_end: Training period
        val_start, val_end: Validation period
        test_start, test_end: Test period
        
    Returns:
        Dict with keys 'train', 'val', 'test'
    """
    # Convert dates to datetime
    train_start = pd.to_datetime(train_start)
    train_end = pd.to_datetime(train_end)
    val_start = pd.to_datetime(val_start)
    val_end = pd.to_datetime(val_end)
    test_start = pd.to_datetime(test_start)
    test_end = pd.to_datetime(test_end)
    
    # Validate no overlap
    if train_end >= val_start:
        raise ValueError("Train and val periods overlap!")
    if val_end >= test_start:
        raise ValueError("Val and test periods overlap!")
    
    # Create splits
    train_df = df[(df['date'] >= train_start) & (df['date'] <= train_end)].copy()
    val_df = df[(df['date'] >= val_start) & (df['date'] <= val_end)].copy()
    test_df = df[(df['date'] >= test_start) & (df['date'] <= test_end)].copy()
    
    # Log split info
    logger.info("=" * 70)
    logger.info("TIME-BASED SPLITS (NO RANDOM SAMPLING)")
    logger.info("=" * 70)
    
    logger.info(f"\nTRAIN: {train_start.date()} to {train_end.date()}")
    logger.info(f"  Rows: {len(train_df):,}")
    logger.info(f"  Symbols: {sorted(train_df['symbol'].unique())}")
    logger.info(f"  Class distribution:")
    for cls, count in train_df['y_class_1d'].value_counts().sort_index().items():
        pct = 100 * count / len(train_df)
        logger.info(f"    {cls:2d}: {count:5d} ({pct:5.2f}%)")
    
    logger.info(f"\nVAL:   {val_start.date()} to {val_end.date()}")
    logger.info(f"  Rows: {len(val_df):,}")
    logger.info(f"  Symbols: {sorted(val_df['symbol'].unique())}")
    logger.info(f"  Class distribution:")
    for cls, count in val_df['y_class_1d'].value_counts().sort_index().items():
        pct = 100 * count / len(val_df)
        logger.info(f"    {cls:2d}: {count:5d} ({pct:5.2f}%)")
    
    logger.info(f"\nTEST:  {test_start.date()} to {test_end.date()}")
    logger.info(f"  Rows: {len(test_df):,}")
    logger.info(f"  Symbols: {sorted(test_df['symbol'].unique())}")
    logger.info(f"  Class distribution:")
    for cls, count in test_df['y_class_1d'].value_counts().sort_index().items():
        pct = 100 * count / len(test_df)
        logger.info(f"    {cls:2d}: {count:5d} ({pct:5.2f}%)")
    
    logger.info("=" * 70)
    
    # Validate non-empty
    if len(train_df) == 0:
        raise ValueError("Train split is empty!")
    if len(val_df) == 0:
        raise ValueError("Val split is empty!")
    if len(test_df) == 0:
        raise ValueError("Test split is empty!")
    
    return {
        'train': train_df,
        'val': val_df,
        'test': test_df
    }


def get_feature_columns(df: pd.DataFrame) -> list:
    """
    Get list of feature columns (exclude metadata and target).
    
    Args:
        df: DataFrame with all columns
        
    Returns:
        List of feature column names
    """
    exclude_cols = ['symbol', 'date', 'y_class_1d']
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    return feature_cols


def prepare_X_y(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Split DataFrame into features (X) and target (y).
    
    Args:
        df: DataFrame with features and target
        
    Returns:
        (X, y) where X is features DataFrame and y is target Series
    """
    feature_cols = get_feature_columns(df)
    X = df[feature_cols].copy()
    y = df['y_class_1d'].copy()
    return X, y
