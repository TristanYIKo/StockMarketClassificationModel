"""
Evaluation metrics for multiclass classification.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    confusion_matrix,
    classification_report
)
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """
    Compute comprehensive multiclass classification metrics.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        
    Returns:
        Dict of metric name -> value
    """
    metrics = {
        'accuracy': accuracy_score(y_true, y_pred),
        'f1_macro': f1_score(y_true, y_pred, average='macro'),
        'f1_weighted': f1_score(y_true, y_pred, average='weighted'),
        'precision_macro': precision_score(y_true, y_pred, average='macro', zero_division=0),
        'recall_macro': recall_score(y_true, y_pred, average='macro', zero_division=0)
    }
    
    # Per-class F1 scores
    f1_per_class = f1_score(y_true, y_pred, average=None, zero_division=0)
    classes = np.unique(np.concatenate([y_true, y_pred]))
    for i, cls in enumerate(classes):
        metrics[f'f1_class_{cls}'] = f1_per_class[i]
    
    return metrics


def print_classification_report(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    target_names: list = None
):
    """
    Print detailed classification report.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        target_names: Names for each class (e.g., ['Sell', 'Hold', 'Buy'])
    """
    if target_names is None:
        target_names = [f"Class {c}" for c in np.unique(y_true)]
    
    report = classification_report(y_true, y_pred, target_names=target_names, zero_division=0)
    print(report)


def plot_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    target_names: list = None,
    save_path: str = None,
    title: str = "Confusion Matrix"
):
    """
    Plot confusion matrix heatmap.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        target_names: Names for each class
        save_path: Path to save figure (optional)
        title: Plot title
    """
    cm = confusion_matrix(y_true, y_pred)
    
    if target_names is None:
        classes = np.unique(y_true)
        target_names = [f"Class {c}" for c in classes]
    
    # Normalize to percentages
    cm_pct = 100 * cm / cm.sum(axis=1, keepdims=True)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Plot heatmap
    sns.heatmap(
        cm_pct,
        annot=True,
        fmt='.1f',
        cmap='Blues',
        xticklabels=target_names,
        yticklabels=target_names,
        cbar_kws={'label': 'Percentage (%)'},
        ax=ax
    )
    
    ax.set_title(title, fontsize=14, pad=20)
    ax.set_xlabel('Predicted Label', fontsize=12)
    ax.set_ylabel('True Label', fontsize=12)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        logger.info(f"Saved confusion matrix to {save_path}")
    
    plt.close()


def evaluate_model(
    model,
    X: np.ndarray,
    y: np.ndarray,
    split_name: str,
    target_names: list = None,
    save_dir: str = None
) -> Dict[str, float]:
    """
    Comprehensive model evaluation with metrics and plots.
    
    Args:
        model: Trained classifier
        X: Features
        y: True labels
        split_name: Name of split (e.g., 'train', 'val', 'test')
        target_names: Names for each class
        save_dir: Directory to save plots
        
    Returns:
        Dict of metrics
    """
    # Predict
    y_pred = model.predict(X)
    
    # Compute metrics
    metrics = compute_metrics(y, y_pred)
    
    # Log metrics
    logger.info(f"\n{split_name.upper()} METRICS:")
    logger.info(f"  Accuracy:        {metrics['accuracy']:.4f}")
    logger.info(f"  F1 (macro):      {metrics['f1_macro']:.4f}")
    logger.info(f"  F1 (weighted):   {metrics['f1_weighted']:.4f}")
    logger.info(f"  Precision (macro): {metrics['precision_macro']:.4f}")
    logger.info(f"  Recall (macro):  {metrics['recall_macro']:.4f}")
    
    # Per-class F1
    classes = np.unique(y)
    logger.info(f"  F1 per class:")
    for cls in classes:
        f1_cls = metrics.get(f'f1_class_{cls}', 0)
        logger.info(f"    Class {cls}: {f1_cls:.4f}")
    
    # Print classification report
    print_classification_report(y, y_pred, target_names=target_names)
    
    # Plot confusion matrix
    if save_dir:
        import os
        cm_path = os.path.join(save_dir, f'confusion_matrix_{split_name}.png')
        plot_confusion_matrix(
            y, y_pred,
            target_names=target_names,
            save_path=cm_path,
            title=f"Confusion Matrix - {split_name.upper()}"
        )
    
    return metrics


def compare_models(results: Dict[str, Dict[str, float]], save_path: str = None):
    """
    Create comparison table and plot for multiple models.
    
    Args:
        results: Dict of {model_name: {metric: value}}
        save_path: Path to save comparison plot
    """
    # Create DataFrame
    df = pd.DataFrame(results).T
    
    # Sort by validation F1 (macro)
    if 'val_f1_macro' in df.columns:
        df = df.sort_values('val_f1_macro', ascending=False)
    
    # Print table
    logger.info("\n" + "=" * 100)
    logger.info("MODEL COMPARISON")
    logger.info("=" * 100)
    print(df.to_string())
    logger.info("=" * 100)
    
    # Create bar plot
    if save_path:
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        
        metrics_to_plot = [
            ('train_accuracy', 'Train Accuracy'),
            ('val_accuracy', 'Val Accuracy'),
            ('test_accuracy', 'Test Accuracy')
        ]
        
        for ax, (metric, title) in zip(axes, metrics_to_plot):
            if metric in df.columns:
                df[metric].plot(kind='bar', ax=ax, color='steelblue')
                ax.set_title(title, fontsize=12)
                ax.set_ylabel('Score', fontsize=10)
                ax.set_xlabel('Model', fontsize=10)
                ax.set_ylim([0, 1])
                ax.grid(axis='y', alpha=0.3)
                ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        logger.info(f"\nSaved model comparison to {save_path}")
        plt.close()
