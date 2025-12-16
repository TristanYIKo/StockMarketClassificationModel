"""
Clear all data from Supabase tables to prepare for full regeneration.
"""

from dotenv import load_dotenv
load_dotenv()

from etl.supabase_client import SupabaseDB

def clear_all_data():
    db = SupabaseDB()
    
    tables_to_clear = [
        'labels_daily',
        'features_daily',
        'daily_bars',
        'model_predictions_classification',
        'macro_daily',
        'events_calendar'
    ]
    
    print("🗑️  Clearing all data from Supabase tables...\n")
    
    for table in tables_to_clear:
        try:
            print(f"Clearing {table}...")
            # Delete all rows
            result = db.client.table(table).delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
            print(f"  ✅ Cleared {table}")
        except Exception as e:
            print(f"  ⚠️  Error clearing {table}: {e}")
    
    print("\n✅ All tables cleared! Ready for full regeneration.")
    print("\nNext step: Run ETL with full historical range:")
    print("  python -m etl.main --start 2020-01-01 --end 2025-12-15")

if __name__ == '__main__':
    response = input("⚠️  This will DELETE ALL DATA from Supabase. Are you sure? (type 'yes' to confirm): ")
    if response.lower() == 'yes':
        clear_all_data()
    else:
        print("Cancelled.")
