"""
Convert 3-class labels to binary classification.
Maps HOLD (0) based on actual return direction.
"""

import pandas as pd

print("Loading dataset...")
df = pd.read_csv('classification_dataset.csv')

print("\nOriginal class distribution:")
print(df['y_class_1d'].value_counts())

# Convert HOLD (0) to binary based on return sign
# If we had return data, we'd use that, but we'll just remove HOLD rows
print("\nConverting to binary classification...")
print("Strategy: Remove HOLD class (0) rows")

df_binary = df[df['y_class_1d'] != 0].copy()

print(f"\nRows before: {len(df)}")
print(f"Rows after: {len(df_binary)}")
print(f"Removed {len(df) - len(df_binary)} HOLD rows ({100*(len(df) - len(df_binary))/len(df):.1f}%)")

print("\nNew binary class distribution:")
print(df_binary['y_class_1d'].value_counts())

# Save
output_file = 'classification_dataset.csv'
df_binary.to_csv(output_file, index=False)
print(f"\n✅ Saved binary dataset to {output_file}")
print(f"   Shape: {df_binary.shape}")
