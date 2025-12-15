
import os
import sys
import json
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from etl.supabase_client import SupabaseDB

load_dotenv()

def verify():
    db = SupabaseDB()
    print("Fetching last 5 rows from model_predictions_classification...")
    
    response = db.client.table("model_predictions_classification")\
        .select("*")\
        .order("date", desc=True)\
        .limit(5)\
        .execute()
        
    if not response.data:
        print("No data found.")
        return
        
    print(f"Found {len(response.data)} rows.")
    first_row = response.data[0]
    print("Columns found:", list(first_row.keys()))
    
    print("\nSample Data (Probabilities):")
    print(f"Symbol: {first_row.get('symbol')}")
    print(f"p_buy: {first_row.get('p_buy')}")
    print(f"p_sell: {first_row.get('p_sell')}")
    print(f"p_hold: {first_row.get('p_hold')}")
    print(f"confidence: {first_row.get('confidence')}")

if __name__ == "__main__":
    verify()
