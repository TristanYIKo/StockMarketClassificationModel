"""
Decision logic with confidence gating for classification predictions.

CRITICAL: Thresholds are tuned on VAL only, then applied to TEST.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
from sklearn.metrics import f1_score, accuracy_score, confusion_matrix
import json
import logging

logger = logging.getLogger(__name__)


def compute_pred_features(probs: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute prediction features from probabilities.
    
    Args:
        probs: (N, 2) array of [p_down, p_up]
        
    Returns:
        pred_class_raw: (N,) array of {-1, 1}
        confidence: (N,) max probability
        margin: (N,) difference between top two probabilities
    """
    # Map indices to classes (binary: DOWN=-1, UP=1)
    index_to_class = {0: -1, 1: 1}
    
    # Raw prediction (argmax)
    pred_idx = np.argmax(probs, axis=1)
    pred_class_raw = np.array([index_to_class[idx] for idx in pred_idx])
    
    # Confidence (max prob)
    confidence = np.max(probs, axis=1)
    
    # Margin (difference between the two probabilities)
    margin = np.abs(probs[:, 0] - probs[:, 1])
    
    return pred_class_raw, confidence, margin


def apply_gating(
    pred_class_raw: np.ndarray,
    confidence: np.ndarray,
    margin: np.ndarray,
    conf_thresh: float,
    margin_thresh: float
) -> np.ndarray:
    """
    Apply confidence gating to predictions.
    
    For binary classification (UP/DOWN only), no gating is applied.
    This function is kept for API compatibility.
    
    Args:
        pred_class_raw: Raw predictions {-1, 1}
        confidence: Max probability
        margin: Probability difference
        conf_thresh: (Unused for binary)
        margin_thresh: (Unused for binary)
        
    Returns:
        pred_class_final: Same as raw predictions {-1, 1}
    """
    # For binary classification, always return the raw prediction
    # (No HOLD option to gate to)
    return pred_class_raw.copy()


def evaluate_gating(
    y_true: np.ndarray,
    pred_class_final: np.ndarray
) -> Dict:
    """
    Evaluate predictions (binary classification).
    
    Args:
        y_true: True labels {-1, 1}
        pred_class_final: Predictions {-1, 1}
        
    Returns:
        metrics: Dict with accuracy, F1 scores
    """
    # Overall metrics
    acc = accuracy_score(y_true, pred_class_final)
    f1_macro = f1_score(y_true, pred_class_final, average='macro', labels=[-1, 1])
    
    # For binary, f1_action is same as f1_macro
    f1_action = f1_macro
    
    # Trade rate is always 100% for binary (always making a prediction)
    trade_rate = 1.0
    
    return {
        'accuracy': acc,
        'f1_macro': f1_macro,
        'f1_action': f1_action,
        'trade_rate': trade_rate
    }


def tune_thresholds(
    probs_val: np.ndarray,
    y_val: np.ndarray,
    horizon: str,
    conf_range: Tuple[float, float] = (0.34, 0.75),
    margin_range: Tuple[float, float] = (0.00, 0.35),
    step: float = 0.01
) -> Dict:
    """
    For binary classification, thresholds are not used (no gating).
    This function returns dummy values for API compatibility.
    
    Args:
        probs_val: Calibrated validation probabilities
        y_val: Validation labels
        horizon: '1d' or '5d'
        conf_range: (Unused)
        margin_range: (Unused)
        step: (Unused)
        
    Returns:
        thresholds: Dict with dummy threshold values
    """
    logger.info("=" * 70)
    logger.info(f"THRESHOLD TUNING ({horizon} horizon) - SKIPPED FOR BINARY")
    logger.info("=" * 70)
    
    # Compute prediction features and evaluate (for logging purposes)
    pred_class_raw, confidence, margin = compute_pred_features(probs_val)
    metrics = evaluate_gating(y_val, pred_class_raw)
    
    logger.info("Binary classification uses all predictions (no gating)")
    logger.info(f"  Accuracy: {metrics['accuracy']:.4f}")
    logger.info(f"  F1 Macro: {metrics['f1_macro']:.4f}")
    
    # Return dummy thresholds (not used in binary classification)
    best_thresholds = {
        'conf_thresh': 0.0,
        'margin_thresh': 0.0,
        'score': float(metrics['f1_macro']),
        'accuracy': float(metrics['accuracy']),
        'f1_macro': float(metrics['f1_macro']),
        'f1_action': float(metrics['f1_action']),
        'trade_rate': float(metrics['trade_rate'])
    }
    
    logger.info("=" * 70)
    
    return best_thresholds


def save_thresholds(thresholds: Dict, path: str):
    """Save thresholds to JSON."""
    with open(path, 'w') as f:
        json.dump(thresholds, f, indent=2)
    logger.info(f"Saved thresholds to {path}")


def load_thresholds(path: str) -> Dict:
    """Load thresholds from JSON."""
    with open(path, 'r') as f:
        thresholds = json.load(f)
    logger.info(f"Loaded thresholds from {path}")
    return thresholds
