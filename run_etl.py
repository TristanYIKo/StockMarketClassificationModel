#!/usr/bin/env python3
"""
Run the ETL pipeline. Entry point for both local runs and GitHub Actions.

    python run_etl.py                       # incremental, auto-detect start
    python run_etl.py --start 2026-01-05    # explicit start
    python run_etl.py --mode backfill --start 2001-01-01

Deliberately does NOT generate predictions. It used to, which meant a bad model
load could fail an otherwise healthy data run, and a fallback path quietly wrote
placeholder "55% UP" rows into the same table real predictions live in. Loading
data and scoring models are separate concerns and separate workflow steps:

    python -m ml.src.predict.predict --latest
"""
import argparse
import sys
from datetime import date, datetime


def _force_utf8_stdout():
    """
    Windows consoles default to cp1252, which cannot encode the box-drawing and
    emoji characters this pipeline logs; printing one raises UnicodeEncodeError
    and kills the run before any data is written.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


_force_utf8_stdout()

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from etl.main import run_etl  # noqa: E402


def is_weekend(check_date) -> bool:
    if isinstance(check_date, str):
        check_date = datetime.fromisoformat(check_date).date()
    return check_date.weekday() >= 5


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ETL pipeline")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD). Omit to auto-detect from the DB.")
    parser.add_argument("--end", help="End date (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--mode", choices=["backfill", "incremental"], default="incremental")
    parser.add_argument("--force", action="store_true", help="Run even on a weekend")
    args = parser.parse_args()

    end_date = args.end or date.today().isoformat()

    if not args.force and not args.start and is_weekend(date.today()):
        print("Markets are closed at the weekend; nothing to load. Use --force to override.")
        return 0

    print("=" * 70)
    print("ETL pipeline - SPY, QQQ, DIA, IWM")
    print(f"  mode:  {args.mode}")
    print(f"  start: {args.start or 'auto-detect'}")
    print(f"  end:   {end_date}")
    print("=" * 70)

    try:
        run_etl(args.start, end_date, args.mode)
    except Exception as exc:
        print(f"\nETL pipeline FAILED: {exc}", file=sys.stderr)
        return 1

    print("\nETL pipeline completed successfully.")
    print("Next: python -m ml.src.predict.predict --latest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
