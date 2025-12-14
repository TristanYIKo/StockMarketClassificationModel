"""
Preprocessing utilities with strict time-series safety.
CRITICAL: All transformers (imputers, scalers) are fit ONLY on training data.
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from typing import Tuple, Dict, List
import logging

logger = logging.getLogger(__name__)


class TimeSeriesPreprocessor:
    """
    Preprocessor for time-series classification data.
    Ensures no data leakage by fitting only on training data.
    """
    
    def __init__(
        self,
        drop_features_threshold: float = 0.30,
        imputation_strategy: str = 'median',
        scaling: bool = True
    ):
        """
        Args:
            drop_features_threshold: Drop features with >this fraction missing in train
            imputation_strategy: 'median', 'mean', or 'most_frequent'
            scaling: Whether to apply StandardScaler
        """
        self.drop_features_threshold = drop_features_threshold
        self.imputation_strategy = imputation_strategy
        self.scaling = scaling
        
        self.dropped_features_ = []
        self.kept_features_ = []
        self.imputer_ = None
        self.scaler_ = None
        self.fitted_ = False
    
    def fit(self, X_train: pd.DataFrame) -> 'TimeSeriesPreprocessor':
        """
        Fit preprocessing pipeline on TRAINING data only.
        
        Args:
            X_train: Training features DataFrame
            
        Returns:
            self
        """
        logger.info("=" * 70)
        logger.info("FITTING PREPROCESSOR (TRAINING DATA ONLY)")
        logger.info("=" * 70)
        
        # Step 1: Drop features with too many missing values
        missing_pct = X_train.isnull().mean()
        to_drop = missing_pct[missing_pct > self.drop_features_threshold].index.tolist()
        self.dropped_features_ = to_drop
        self.kept_features_ = [c for c in X_train.columns if c not in to_drop]
        
        logger.info(f"\n1. DROPPING FEATURES (>{100*self.drop_features_threshold:.0f}% missing in train):")
        if to_drop:
            logger.info(f"   Dropped {len(to_drop)} features:")
            for feat in sorted(to_drop):
                logger.info(f"     - {feat} ({100*missing_pct[feat]:.1f}% missing)")
        else:
            logger.info("   No features dropped (all below threshold)")
        
        logger.info(f"\n   Kept {len(self.kept_features_)} features")
        
        # Step 2: Fit imputer on kept features
        X_train_kept = X_train[self.kept_features_]
        self.imputer_ = SimpleImputer(strategy=self.imputation_strategy)
        self.imputer_.fit(X_train_kept)
        
        # Check how many values will be imputed
        n_imputed = X_train_kept.isnull().sum().sum()
        total_vals = X_train_kept.size
        pct_imputed = 100 * n_imputed / total_vals
        
        logger.info(f"\n2. FITTING IMPUTER:")
        logger.info(f"   Strategy: {self.imputation_strategy}")
        logger.info(f"   Will impute {n_imputed:,} values ({pct_imputed:.2f}% of train data)")
        
        # Step 3: Fit scaler (if enabled)
        if self.scaling:
            X_train_imputed = self.imputer_.transform(X_train_kept)
            self.scaler_ = StandardScaler()
            self.scaler_.fit(X_train_imputed)
            logger.info(f"\n3. FITTING SCALER:")
            logger.info(f"   StandardScaler fit on {X_train_imputed.shape[0]:,} rows")
        else:
            logger.info(f"\n3. SCALING: Disabled")
        
        self.fitted_ = True
        logger.info("=" * 70)
        return self
    
    def transform(self, X: pd.DataFrame, split_name: str = "") -> np.ndarray:
        """
        Transform features using fitted preprocessing pipeline.
        
        Args:
            X: Features DataFrame
            split_name: Name for logging (e.g., 'train', 'val', 'test')
            
        Returns:
            Transformed numpy array
        """
        if not self.fitted_:
            raise RuntimeError("Must call fit() before transform()")
        
        if split_name:
            logger.info(f"\nTRANSFORMING {split_name.upper()}:")
        
        # Step 1: Drop features
        X_kept = X[self.kept_features_]
        
        # Step 2: Impute
        X_imputed = self.imputer_.transform(X_kept)
        n_imputed = np.isnan(X_kept.values).sum()
        if split_name:
            logger.info(f"  Imputed {n_imputed:,} missing values")
        
        # Step 3: Scale
        if self.scaling:
            X_scaled = self.scaler_.transform(X_imputed)
            return X_scaled
        else:
            return X_imputed
    
    def fit_transform(self, X_train: pd.DataFrame) -> np.ndarray:
        """
        Fit on training data and transform it.
        
        Args:
            X_train: Training features DataFrame
            
        Returns:
            Transformed training data
        """
        self.fit(X_train)
        return self.transform(X_train, split_name='train')
    
    def get_feature_names(self) -> List[str]:
        """Get list of features after dropping high-missing features."""
        if not self.fitted_:
            raise RuntimeError("Must call fit() before get_feature_names()")
        return self.kept_features_


def compute_class_weights(y_train: pd.Series) -> Dict[int, float]:
    """
    Compute balanced class weights for imbalanced data.
    
    Args:
        y_train: Training labels
        
    Returns:
        Dict mapping class label to weight
    """
    from sklearn.utils.class_weight import compute_class_weight
    
    classes = np.unique(y_train)
    weights = compute_class_weight('balanced', classes=classes, y=y_train)
    
    weight_dict = dict(zip(classes, weights))
    
    logger.info("\nCLASS WEIGHTS (for imbalanced data):")
    for cls in sorted(weight_dict.keys()):
        count = (y_train == cls).sum()
        pct = 100 * count / len(y_train)
        logger.info(f"  Class {cls:2d}: weight={weight_dict[cls]:.3f} (n={count:,}, {pct:.1f}%)")
    
    return weight_dict
