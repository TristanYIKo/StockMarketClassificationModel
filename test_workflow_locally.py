"""
Test the workflow locally before running on GitHub Actions.
This simulates what GitHub Actions will do.
"""
import subprocess
import sys
import os

def run_command(cmd, description):
    """Run a command and print results."""
    print("\n" + "="*70)
    print(f"Running: {description}")
    print("="*70)
    print(f"Command: {cmd}")
    print()
    
    result = subprocess.run(cmd, shell=True, capture_output=False)
    
    if result.returncode == 0:
        print("\n✅ Success")
        return True
    else:
        print(f"\n❌ Failed with exit code {result.returncode}")
        return False

def main():
    """Test workflow steps."""
    print("="*70)
    print("Testing GitHub Actions Workflow Locally")
    print("="*70)
    print("\nThis will test the exact commands that GitHub Actions will run.")
    print("Make sure you have set SUPABASE_URL, SUPABASE_KEY, and FRED_API_KEY")
    print("in your .env file.\n")
    
    # Check environment
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'FRED_API_KEY']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("Add them to your .env file and try again.")
        return False
    
    print("✅ All environment variables are set\n")
    
    # Test Step 1: ETL
    if not run_command("python run_etl.py --mode incremental", 
                      "ETL Pipeline (update to latest trading day)"):
        return False
    
    # Test Step 2: Predictions
    if not run_command("python quick_add_predictions_all_symbols.py", 
                      "Generate Predictions (next trading day)"):
        return False
    
    # Test Step 3: Verification
    if not run_command("python verify_all_predictions.py", 
                      "Verify Predictions"):
        return False
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED!")
    print("="*70)
    print("\nYour workflow is ready for GitHub Actions!")
    print("Next steps:")
    print("  1. Commit changes: git add . && git commit -m 'Update workflow'")
    print("  2. Push to GitHub: git push origin main")
    print("  3. Go to Actions tab and re-run the workflow")
    print("="*70)
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
