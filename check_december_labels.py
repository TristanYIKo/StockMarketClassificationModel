"""Check labels in detail."""
from etl.supabase_client import SupabaseDB
from dotenv import load_dotenv
import pandas as pd

load_dotenv()
db = SupabaseDB()

# Get all labels for December 2025, ordered by date
result = db.client.table('labels_daily').select('*, assets!inner(symbol)').gte('date', '2025-12-01').order('date').execute()

if result.data:
    df = pd.DataFrame(result.data)
    print("Labels in December 2025:")
    print(df[['date', 'assets', 'y_class_1d', 'y_class_5d']].to_string())
    print(f"\nTotal rows: {len(df)}")
    print(f"\nDates present: {sorted(df['date'].unique())}")
else:
    print("No labels found for December 2025")
