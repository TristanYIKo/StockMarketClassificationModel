
import os
from supabase import create_client

def test_access():
    # 1. Read frontend credentials manually
    url = None
    key = None
    try:
        with open('web/.env.local', 'r') as f:
            for line in f:
                if 'NEXT_PUBLIC_SUPABASE_URL=' in line:
                    url = line.split('=')[1].strip()
                if 'NEXT_PUBLIC_SUPABASE_KEY=' in line:
                    key = line.split('=')[1].strip()
    except Exception as e:
        print(f"Error reading .env.local: {e}")
        return

    if not url or not key:
        print("Could not find URL or KEY in web/.env.local")
        return

    print(f"Testing access with Key: {key[:10]}...")
    
    # 2. Try to connect
    try:
        client = create_client(url, key)
        
        # 3. Try to fetch predictions
        print("\nAttempting to select top 1 from model_predictions_classification...")
        res = client.table('model_predictions_classification').select('symbol').limit(1).execute()
        print(f"Predictions Result: {res.data}")
        
        # 4. Try to fetch assets
        print("\nAttempting to select top 1 from assets...")
        res_assets = client.table('assets').select('symbol').limit(1).execute()
        print(f"Assets Result: {res_assets.data}")
        
    except Exception as e:
        print(f"\n❌ ACCESS FAILED: {e}")

if __name__ == "__main__":
    test_access()
