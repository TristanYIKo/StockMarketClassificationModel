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
        probs: (N, 3) array of [p_sell, p_hold, p_buy]
        
    Returns:
        pred_class_raw: (N,) array of {-1, 0, 1}
        confidence: (N,) max probability
        margin: (N,) difference between top two probabilities
    """
    # Map indices to classes
    index_to_class = {0: -1, 1: 0, 2: 1}
    
    # Raw prediction (argmax)
    pred_idx = np.argmax(probs, axis=1)
    pred_class_raw = np.array([index_to_class[idx] for idx in pred_idx])
    
    # Confidence (max prob)
    confidence = np.max(probs, axis=1)
    
    # Margin (top1 - top2)
    sorted_probs = np.sort(probs, axis=1)
    margin = sorted_probs[:, -1] - sorted_probs[:, -2]
    
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
    
    Rule:
    - If pred_class_raw == 0 → pred_class_final = 0
    - If pred_class_raw in {-1, 1}:
        if confidence >= conf_thresh AND margin >= margin_thresh:
            pred_class_final = pred_class_raw
        else:
            pred_class_final = 0
    
    Args:
        pred_class_raw: Raw predictions {-1, 0, 1}
        confidence: Max probability
        margin: Top1 - top2 probability
        conf_thresh: Confidence threshold
        margin_thresh: Margin threshold
        
    Returns:
        pred_class_final: Gated predictions {-1, 0, 1}
    """
    pred_class_final = pred_class_raw.copy()
    
    # For non-hold predictions, apply gating
    action_mask = (pred_class_raw != 0)
    low_conf_mask = (confidence < conf_thresh) | (margin < margin_thresh)
    
    # Set to hold if confidence/margin too low
    pred_class_final[action_mask & low_conf_mask] = 0
    
    return pred_class_final


def evaluate_gating(
    y_true: np.ndarray,
    pred_class_final: np.ndarray
) -> Dict:
    """
    Evaluate gated predictions.
    
    Args:
        y_true: True labels {-1, 0, 1}
        pred_class_final: Gated predictions {-1, 0, 1}
        
    Returns:
        metrics: Dict with accuracy, F1 scores, trade rate
    """
    # Overall metrics
    acc = accuracy_score(y_true, pred_class_final)
    f1_macro = f1_score(y_true, pred_class_final, average='macro', labels=[-1, 0, 1])
    
    # Action-only F1 (exclude hold from both y_true and y_pred)
    action_mask = (y_true != 0) & (pred_class_final != 0)
    if action_mask.sum() > 0:
        f1_action = f1_score(
            y_true[action_mask],
            pred_class_final[action_mask],
            average='macro',
            labels=[-1, 1]
        )
    else:
        f1_action = 0.0
    
    # Trade rate (% predictions that are not hold)
    trade_rate = (pred_class_final != 0).mean()
    
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
    Tune confidence and margin thresholds on validation set.
    
    Objective: Maximize macro-F1 and action-F1
    Constraint: Trade rate within reasonable bounds
    
    Args:
        probs_val: Calibrated validation probabilities
        y_val: Validation labels
        horizon: '1d' or '5d' (affects trade rate bounds)
        conf_range: (min, max) for confidence threshold
        margin_range: (min, max) for margin threshold
        step: Grid search step size
        
    Returns:
        best_thresholds: Dict with conf_thresh, margin_thresh, and metrics
    """
    logger.info("=" * 70)
    logger.info(f"THRESHOLD TUNING ({horizon} horizon)")
    logger.info("=" * 70)
    
    # Trade rate bounds by horizon
    if horizon == '1d':
        trade_rate_min, trade_rate_max = 0.20, 0.70
    else:  # 5d
        trade_rate_min, trade_rate_max = 0.15, 0.60
    
    # Compute prediction features
    pred_class_raw, confidence, margin = compute_pred_features(probs_val)
    
    # Grid search
    conf_values = np.arange(conf_range[0], conf_range[1] + step, step)
    margin_values = np.arange(margin_range[0], margin_range[1] + step, step)
    
    best_score = -1
    best_thresholds = None
    
    logger.info(f"Searching {len(conf_values)} x {len(margin_values)} = {len(conf_values) * len(margin_values)} combinations...")
    
    for conf_thresh in conf_values:
        for margin_thresh in margin_values:
            # Apply gating
            pred_final = apply_gating(pred_class_raw, confidence, margin, conf_thresh, margin_thresh)
            
            # Evaluate
            metrics = evaluate_gating(y_val, pred_final)
            
            # Check trade rate constraint
            if not (trade_rate_min <= metrics['trade_rate'] <= trade_rate_max):
                continue
            
            # Combined score (weighted average)
            score = 0.6 * metrics['f1_macro'] + 0.4 * metrics['f1_action']
            
            if score > best_score:
                best_score = score
                best_thresholds = {
                    'conf_thresh': float(conf_thresh),
                    'margin_thresh': float(margin_thresh),
                    'score': float(score),
                    **{k: float(v) for k, v in metrics.items()}
                }
    
    if best_thresholds is None:
        logger.warning("No thresholds found within trade rate constraints! Using defaults.")
        best_thresholds = {
            'conf_thresh': 0.40,
            'margin_thresh': 0.05,
            'score': 0.0,
            'accuracy': 0.0,
            'f1_macro': 0.0,
            'f1_action': 0.0,
            'trade_rate': 0.0
        }
    
    logger.info(f"\nBest thresholds:")
    logger.info(f"  Confidence: {best_thresholds['conf_thresh']:.2f}")
    logger.info(f"  Margin:     {best_thresholds['margin_thresh']:.2f}")
    logger.info(f"  Accuracy:   {best_thresholds['accuracy']:.4f}")
    logger.info(f"  F1 Macro:   {best_thresholds['f1_macro']:.4f}")
    logger.info(f"  F1 Action:  {best_thresholds['f1_action']:.4f}")
    logger.info(f"  Trade Rate: {best_thresholds['trade_rate']:.2%}")
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
