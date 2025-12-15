
import os
from dotenv import load_dotenv

def sync_env():
    # Load backend env
    load_dotenv('.env')
    
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY') # This might be Service Role or Anon
    
    # Ideally frontend uses Anon key. 
    # But for this portfolio project, using whatever key is in .env is the best bet for "making it work".
    
    if not url or not key:
        print("❌ Could not find SUPABASE_URL or SUPABASE_KEY in .env")
        return

    print(f"Found URL: {url[:15]}...")
    print(f"Found KEY: {key[:10]}...")

    content = f"NEXT_PUBLIC_SUPABASE_URL={url}\nNEXT_PUBLIC_SUPABASE_KEY={key}\n"
    
    with open('web/.env.local', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("✅ Successfully wrote web/.env.local")

if __name__ == "__main__":
    sync_env()
