"""
Training script for 1-day classification models.
Predicts stock movements 1 trading day ahead using y_class_1d target.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Import and run with 1-day target
from ml.src.train import train_models
from ml.src.utils import splits

# Monkey-patch the prepare_X_y and create_time_splits to use y_class_1d
_original_prepare_X_y = splits.prepare_X_y
_original_create_time_splits = splits.create_time_splits

def prepare_X_y_1d(df):
    return _original_prepare_X_y(df, target_col='y_class_1d')

def create_time_splits_1d(df, train_start, train_end, val_start, val_end, test_start, test_end):
    return _original_create_time_splits(
        df, train_start, train_end, val_start, val_end, test_start, test_end,
        target_col='y_class_1d'
    )

splits.prepare_X_y = prepare_X_y_1d
splits.create_time_splits = create_time_splits_1d

# Run training
if __name__ == '__main__':
    # Inject arguments for 1d training
    if '--suffix' not in sys.argv:
        sys.argv.extend(['--suffix', '_1d'])
    if '--csv_path' not in sys.argv:
        sys.argv.extend(['--csv_path', 'classification_dataset.csv'])
        
    train_models.main()
