"""Check date ranges in Supabase tables."""
import os
from etl.supabase_client import SupabaseDB

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

db = SupabaseDB()

# Check labels_daily
print("Checking labels_daily table...")
result = db.client.table('labels_daily').select('date').order('date', desc=True).limit(5).execute()
if result.data:
    print(f"  Latest dates: {[row['date'] for row in result.data]}")
    
result = db.client.table('labels_daily').select('date').order('date').limit(1).execute()
if result.data:
    print(f"  Earliest date: {result.data[0]['date']}")

# Check features_daily
print("\nChecking features_daily table...")
result = db.client.table('features_daily').select('date').order('date', desc=True).limit(5).execute()
if result.data:
    print(f"  Latest dates: {[row['date'] for row in result.data]}")

# Check view
print("\nChecking v_classification_dataset_1d view...")
result = db.client.from_('v_classification_dataset_1d').select('date').order('date', desc=True).limit(5).execute()
if result.data:
    print(f"  Latest dates: {[row['date'] for row in result.data]}")
else:
    print("  No data or view doesn't exist")
