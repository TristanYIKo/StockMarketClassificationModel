"""Check what bar dates we have."""
from etl.supabase_client import SupabaseDB
from dotenv import load_dotenv

load_dotenv()
db = SupabaseDB()

# Check daily_bars for December
result = db.client.table('daily_bars').select('*, assets!inner(symbol)').gte('date', '2025-12-06').order('date').execute()

if result.data:
    dates = sorted(set([row['date'] for row in result.data]))
    print(f"Bar dates from Dec 6 onwards: {dates}")
    print(f"Latest bar date: {max(dates)}")
else:
    print("No bars found from Dec 6 onwards")
