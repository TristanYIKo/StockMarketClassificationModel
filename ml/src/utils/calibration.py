"""
Probability calibration for multi-class classification.
Uses One-vs-Rest strategy with isotonic regression.

CRITICAL: Calibrators are fit on VAL only, then applied to VAL and TEST.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss
import joblib
import logging

logger = logging.getLogger(__name__)


class MulticlassCalibrator:
    """
    One-vs-Rest calibration for 3-class classification.
    Fits separate calibrators for each class.
    """
    
    def __init__(self):
        self.calibrators = {}  # {class: IsotonicRegression}
        self.classes = [-1, 0, 1]
        
    def fit(self, probs: np.ndarray, y_true: np.ndarray):
        """
        Fit calibrators on validation data.
        
        Args:
            probs: (N, 3) array of [p_sell, p_hold, p_buy]
            y_true: (N,) array of true labels in {-1, 0, 1}
        """
        logger.info("Fitting OvR calibrators...")
        
        for i, cls in enumerate(self.classes):
            # Binary target: 1 if y==cls, else 0
            y_binary = (y_true == cls).astype(int)
            p_class = probs[:, i]
            
            # Fit isotonic regression
            cal = IsotonicRegression(out_of_bounds='clip')
            cal.fit(p_class, y_binary)
            self.calibrators[cls] = cal
            
            logger.info(f"  Calibrator for class {cls}: fitted")
        
        return self
    
    def transform(self, probs: np.ndarray) -> np.ndarray:
        """
        Apply calibration and renormalize.
        
        Args:
            probs: (N, 3) array of [p_sell, p_hold, p_buy]
            
        Returns:
            calibrated_probs: (N, 3) array, renormalized to sum to 1
        """
        N = probs.shape[0]
        calibrated = np.zeros((N, 3))
        
        for i, cls in enumerate(self.classes):
            p_class = probs[:, i]
            calibrated[:, i] = self.calibrators[cls].predict(p_class)
        
        # Renormalize to sum to 1
        row_sums = calibrated.sum(axis=1, keepdims=True)
        row_sums = np.maximum(row_sums, 1e-9)  # Avoid division by zero
        calibrated = calibrated / row_sums
        
        return calibrated
    
    def fit_transform(self, probs: np.ndarray, y_true: np.ndarray) -> np.ndarray:
        """Fit and transform in one step."""
        self.fit(probs, y_true)
        return self.transform(probs)


def calibrate_probabilities(
    probs_val: np.ndarray,
    y_val: np.ndarray,
    probs_test: np.ndarray,
    y_test: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, MulticlassCalibrator, Dict]:
    """
    Calibrate probabilities using VAL set, apply to both VAL and TEST.
    
    Args:
        probs_val: (N_val, 3) validation probabilities
        y_val: (N_val,) validation labels
        probs_test: (N_test, 3) test probabilities
        y_test: (N_test,) test labels
        
    Returns:
        probs_val_cal: Calibrated validation probabilities
        probs_test_cal: Calibrated test probabilities
        calibrator: Fitted calibrator object
        metrics: Dict with Brier scores
    """
    logger.info("=" * 70)
    logger.info("PROBABILITY CALIBRATION (One-vs-Rest)")
    logger.info("=" * 70)
    
    # Fit calibrator on VAL only
    calibrator = MulticlassCalibrator()
    probs_val_cal = calibrator.fit_transform(probs_val, y_val)
    
    # Apply to TEST
    probs_test_cal = calibrator.transform(probs_test)
    
    # Compute Brier scores (before and after)
    metrics = {}
    class_names = ['sell', 'hold', 'buy']
    
    for i, (cls, name) in enumerate(zip([-1, 0, 1], class_names)):
        y_val_binary = (y_val == cls).astype(int)
        y_test_binary = (y_test == cls).astype(int)
        
        # Before calibration
        brier_val_before = brier_score_loss(y_val_binary, probs_val[:, i])
        brier_test_before = brier_score_loss(y_test_binary, probs_test[:, i])
        
        # After calibration
        brier_val_after = brier_score_loss(y_val_binary, probs_val_cal[:, i])
        brier_test_after = brier_score_loss(y_test_binary, probs_test_cal[:, i])
        
        metrics[f'brier_{name}_val_before'] = brier_val_before
        metrics[f'brier_{name}_val_after'] = brier_val_after
        metrics[f'brier_{name}_test_before'] = brier_test_before
        metrics[f'brier_{name}_test_after'] = brier_test_after
        
        logger.info(f"\nClass {cls} ({name}):")
        logger.info(f"  VAL Brier:  {brier_val_before:.4f} → {brier_val_after:.4f}")
        logger.info(f"  TEST Brier: {brier_test_before:.4f} → {brier_test_after:.4f}")
    
    logger.info("=" * 70)
    
    return probs_val_cal, probs_test_cal, calibrator, metrics


def save_calibrator(calibrator: MulticlassCalibrator, path: str):
    """Save calibrator to disk."""
    joblib.dump(calibrator, path)
    logger.info(f"Saved calibrator to {path}")


def load_calibrator(path: str) -> MulticlassCalibrator:
    """Load calibrator from disk."""
    calibrator = joblib.load(path)
    logger.info(f"Loaded calibrator from {path}")
    return calibrator
