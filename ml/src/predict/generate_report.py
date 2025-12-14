"""
Generate markdown report comparing horizons.
"""

import pandas as pd
from pathlib import Path


def generate_markdown_report():
    """Generate markdown report from summary CSV."""
    summary_path = Path('ml/artifacts/reports/summary_by_horizon.csv')
    
    if not summary_path.exists():
        print(f"Summary file not found: {summary_path}")
        return
    
    df = pd.read_csv(summary_path)
    
    # Generate markdown
    md = []
    md.append("# Multi-Horizon Classification Model Comparison\n")
    md.append(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    md.append("---\n")
    
    # By horizon
    for horizon in ['1d', '5d']:
        horizon_df = df[df['horizon'] == horizon]
        if len(horizon_df) == 0:
            continue
        
        md.append(f"\n## {horizon.upper()} Horizon\n")
        md.append(f"Predicting {horizon} ahead\n\n")
        
        # Validation metrics
        md.append("### Validation Metrics\n")
        md.append("| Model | Accuracy | F1 Macro | F1 Action | Trade Rate | Conf Thresh | Margin Thresh |")
        md.append("|-------|----------|----------|-----------|------------|-------------|---------------|")
        
        for _, row in horizon_df.iterrows():
            md.append(f"| {row['model']} | {row['val_accuracy']:.4f} | {row['val_f1_macro']:.4f} | "
                     f"{row['val_f1_action']:.4f} | {row['val_trade_rate']:.2%} | "
                     f"{row['conf_thresh']:.2f} | {row['margin_thresh']:.2f} |")
        md.append("")
        
        # Test metrics
        md.append("### Test Metrics\n")
        md.append("| Model | Accuracy | F1 Macro | F1 Action | Trade Rate |")
        md.append("|-------|----------|----------|-----------|------------|")
        
        for _, row in horizon_df.iterrows():
            md.append(f"| {row['model']} | {row['test_accuracy']:.4f} | {row['test_f1_macro']:.4f} | "
                     f"{row['test_f1_action']:.4f} | {row['test_trade_rate']:.2%} |")
        md.append("")
    
    # Cross-horizon comparison
    md.append("\n## Cross-Horizon Comparison\n")
    md.append("Best model per horizon:\n\n")
    
    for horizon in ['1d', '5d']:
        horizon_df = df[df['horizon'] == horizon]
        if len(horizon_df) == 0:
            continue
        
        best = horizon_df.loc[horizon_df['test_f1_macro'].idxmax()]
        md.append(f"**{horizon.upper()}**: {best['model']} - "
                 f"{best['test_accuracy']:.2%} accuracy, "
                 f"{best['test_f1_macro']:.4f} F1 macro, "
                 f"{best['test_trade_rate']:.2%} trade rate\n")
    
    md.append("\n---\n")
    md.append("\n## Key Insights\n")
    
    if len(df) >= 2:
        horizon_1d = df[df['horizon'] == '1d']
        horizon_5d = df[df['horizon'] == '5d']
        
        if len(horizon_1d) > 0 and len(horizon_5d) > 0:
            avg_acc_1d = horizon_1d['test_accuracy'].mean()
            avg_acc_5d = horizon_5d['test_accuracy'].mean()
            improvement = ((avg_acc_5d - avg_acc_1d) / avg_acc_1d) * 100
            
            md.append(f"- **5-day models perform {improvement:+.1f}% better on average**\n")
            md.append(f"- 1d average accuracy: {avg_acc_1d:.2%}\n")
            md.append(f"- 5d average accuracy: {avg_acc_5d:.2%}\n")
            md.append(f"- Random baseline (3-class): 33.3%\n")
    
    # Write to file
    md_path = Path('ml/artifacts/reports/summary_by_horizon.md')
    md_path.write_text('\n'.join(md))
    print(f"Generated report: {md_path}")


if __name__ == '__main__':
    generate_markdown_report()
