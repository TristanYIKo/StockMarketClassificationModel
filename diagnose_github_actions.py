"""
Diagnose why GitHub Actions ETL might not be updating Supabase
"""
from datetime import datetime, date
import pytz
from dotenv import load_dotenv
import os

load_dotenv()

print("=" * 70)
print("GitHub Actions ETL Diagnostic")
print("=" * 70)

# Current date/time
now_utc = datetime.now(pytz.UTC)
now_est = now_utc.astimezone(pytz.timezone('US/Eastern'))

print(f"\nCurrent time:")
print(f"  UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print(f"  EST: {now_est.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print(f"  Day of week: {now_est.strftime('%A')} ({now_est.weekday()})")

# Scheduled time
print(f"\nGitHub Actions Schedule:")
print(f"  Cron: '0 22 * * 1-5'")
print(f"  Runs at: 10:00 PM UTC / 5:00 PM EST")
print(f"  Days: Monday-Friday (1-5)")

# Check if today is a trading day
today = date.today()
is_weekend = today.weekday() >= 5
print(f"\nToday's Status:")
print(f"  Date: {today}")
print(f"  Is weekend: {is_weekend}")
print(f"  Should run: {not is_weekend}")

# Check last DB update
from etl.supabase_client import SupabaseDB
db = SupabaseDB()

print(f"\nDatabase Status:")
for table in ['daily_bars', 'features_daily', 'labels_daily']:
    result = db.client.table(table).select('date').order('date', desc=True).limit(5).execute()
    if result.data:
        latest_dates = [row['date'] for row in result.data]
        print(f"  {table}: {latest_dates[0]} (latest)")

# Check predictions
try:
    result = db.client.table('model_predictions_classification').select('pred_date').order('pred_date', desc=True).limit(5).execute()
    if result.data:
        latest_dates = list(set([row['pred_date'] for row in result.data]))
        latest_dates.sort(reverse=True)
        print(f"  predictions: {latest_dates[0]} (latest target date)")
except Exception as e:
    print(f"  predictions: Error checking - {e}")

print("\n" + "=" * 70)
print("Possible Issues:")
print("=" * 70)
print("""
1. GitHub Actions runs at 5 PM EST, but market data may not be available yet
   - Markets close at 4 PM EST
   - Yahoo Finance may take time to update
   - Solution: Workflow is correctly scheduled after market close

2. Weekend runs are skipped (by design)
   - The workflow checks if it's a weekend and exits
   - This is correct behavior

3. The ETL ran successfully but no new trading days
   - If the last run was recent, there may be no new data
   - Check if GitHub Actions is running on non-trading days (holidays)

4. Secrets might not be set correctly
   - SUPABASE_URL, SUPABASE_KEY, FRED_API_KEY
   - Check GitHub repository settings > Secrets and variables > Actions

5. The workflow might be failing silently
   - Check the GitHub Actions logs
   - Look for errors in the "Run ETL Pipeline" step

6. Date range might be incorrect
   - The auto-detect might not find new data
   - Try running manually with explicit dates
""")

print("\n" + "=" * 70)
print("Recommendations:")
print("=" * 70)
print("""
1. Check GitHub Actions logs at:
   https://github.com/YOUR_USERNAME/StockMarketClassificationModel/actions

2. Verify secrets are set correctly in GitHub

3. The workflow runs on weekdays at 5 PM EST
   - If today is Saturday (Jan 4, 2026), it won't run until Monday
   
4. Local ETL just ran successfully and updated to 2026-01-02
   - GitHub Actions should catch up on next weekday run

5. Consider adding more detailed logging to the workflow
   - Add date checks and market status verification
""")
