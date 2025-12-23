"""
Apply database migration 015 - Add outcome price columns
"""

from etl.supabase_client import SupabaseDB
from dotenv import load_dotenv

load_dotenv()

db = SupabaseDB()

# Read migration SQL
with open('migrations/015_add_outcome_prices.sql', 'r') as f:
    migration_sql = f.read()

print("Applying migration 015_add_outcome_prices.sql...")
print("=" * 60)

try:
    # Split the SQL into individual statements (skip begin/commit)
    statements = [
        stmt.strip() 
        for stmt in migration_sql.split(';') 
        if stmt.strip() and 'begin' not in stmt.lower() and 'commit' not in stmt.lower()
    ]
    
    for stmt in statements:
        if stmt:
            print(f"\nExecuting: {stmt[:100]}...")
            # Execute via RPC or direct SQL if your client supports it
            # For Supabase, you typically need to run DDL through the dashboard
            print("⚠️  This statement needs to be run in Supabase SQL Editor:")
            print(f"{stmt};")
            print()
    
    print("\n" + "=" * 60)
    print("✅ Migration statements generated.")
    print("\n📋 NEXT STEPS:")
    print("1. Copy the SQL statements above")
    print("2. Go to Supabase Dashboard > SQL Editor")
    print("3. Paste and run the SQL")
    print("4. Come back and run the ETL")
    
except Exception as e:
    print(f"❌ Error: {e}")
