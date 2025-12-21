#!/usr/bin/env python3
"""
Run ETL pipeline - wrapper script for GitHub Actions.
This ensures proper imports and paths work correctly.
"""
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import and run the ETL
from etl.main import run_etl
from datetime import date
import argparse

def is_weekend(check_date):
    """Check if the given date is a weekend (Saturday=5, Sunday=6)"""
    from datetime import datetime
    if isinstance(check_date, str):
        check_date = datetime.fromisoformat(check_date).date()
    return check_date.weekday() >= 5

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ETL pipeline")
    parser.add_argument("--start", type=str, required=False, 
                       help="Start date (YYYY-MM-DD). If omitted, auto-detects from DB.")
    parser.add_argument("--end", type=str, required=False, 
                       help="End date (YYYY-MM-DD). If omitted, defaults to today.")
    parser.add_argument("--mode", type=str, choices=["backfill", "incremental"], 
                       default="incremental", help="ETL mode")
    parser.add_argument("--force", action="store_true", 
                       help="Force ETL to run even on weekends")
    
    args = parser.parse_args()
    
    # Default end to today if not provided
    end_date = args.end if args.end else date.today().isoformat()
    
    # Check if today is a weekend (for scheduled runs)
    if not args.force and not args.start and is_weekend(date.today()):
        print("="*70)
        print("⏸️  ETL Pipeline skipped - Weekend detected")
        print("="*70)
        print("Stock markets are closed on weekends (Saturday and Sunday).")
        print("The ETL pipeline will run on the next trading day.")
        print("To force execution, use: python run_etl.py --force")
        print("="*70)
        sys.exit(0)
    
    print("="*70)
    print("ETL Pipeline - All Symbols (SPY, QQQ, IWM, DIA)")
    print("="*70)
    print(f"Mode: {args.mode}")
    print(f"Start: {args.start if args.start else 'Auto-detect'}")
    print(f"End: {end_date}")
    print("="*70)
    
    try:
        run_etl(args.start, end_date, args.mode)
        print("\n" + "="*70)
        print("✅ ETL Pipeline completed successfully!")
        print("="*70)
    except Exception as e:
        print("\n" + "="*70)
        print(f"❌ ETL Pipeline failed: {e}")
        print("="*70)
        sys.exit(1)
