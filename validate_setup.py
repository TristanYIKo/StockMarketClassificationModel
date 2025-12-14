"""
Quick validation script to check environment setup before running full ETL.
"""

import os
import sys

def check_env_vars():
    """Check required environment variables."""
    print("Checking environment variables...")
    
    db_url = os.getenv("SUPABASE_DB_URL")
    fred_key = os.getenv("FRED_API_KEY")
    
    if not db_url:
        print("  ❌ SUPABASE_DB_URL not set")
        return False
    else:
        print("  ✓ SUPABASE_DB_URL set")
    
    if not fred_key:
        print("  ❌ FRED_API_KEY not set")
        return False
    else:
        print("  ✓ FRED_API_KEY set")
    
    return True


def check_imports():
    """Check required Python packages."""
    print("\nChecking Python dependencies...")
    
    packages = [
        ("pandas", "pandas"),
        ("numpy", "numpy"),
        ("yfinance", "yfinance"),
        ("psycopg2", "psycopg2-binary"),
        ("fredapi", "fredapi"),
        ("pandas_market_calendars", "pandas-market-calendars"),
    ]
    
    all_ok = True
    for package, pip_name in packages:
        try:
            __import__(package)
            print(f"  ✓ {pip_name}")
        except ImportError:
            print(f"  ❌ {pip_name} not installed")
            all_ok = False
    
    return all_ok


def check_db_connection():
    """Test Supabase connection."""
    print("\nChecking database connection...")
    
    try:
        import psycopg2
        db_url = os.getenv("SUPABASE_DB_URL")
        
        if not db_url:
            print("  ❌ Cannot test connection (SUPABASE_DB_URL not set)")
            return False
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        conn.close()
        print(f"  ✓ Connected to Postgres: {version[0][:50]}...")
        return True
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        return False


def check_fred_api():
    """Test FRED API connection."""
    print("\nChecking FRED API...")
    
    try:
        from fredapi import Fred
        fred_key = os.getenv("FRED_API_KEY")
        
        if not fred_key:
            print("  ❌ Cannot test API (FRED_API_KEY not set)")
            return False
        
        fred = Fred(api_key=fred_key)
        # Try fetching one observation
        series = fred.get_series("DGS10", observation_start="2024-01-01", observation_end="2024-01-31")
        print(f"  ✓ FRED API working ({len(series)} observations fetched)")
        return True
    except Exception as e:
        print(f"  ❌ FRED API failed: {e}")
        return False


def main():
    print("=" * 60)
    print("Stock Market Classification Model - Environment Validation")
    print("=" * 60)
    
    checks = [
        check_env_vars(),
        check_imports(),
        check_db_connection(),
        check_fred_api(),
    ]
    
    print("\n" + "=" * 60)
    if all(checks):
        print("✓ All checks passed! Ready to run ETL.")
        print("\nNext steps:")
        print("  1. Apply migrations/001_init_schema.sql")
        print("  2. Apply migrations/002_add_context_data.sql")
        print("  3. Run: python -m etl.main --start 2000-01-01 --end 2025-12-12 --mode backfill")
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
