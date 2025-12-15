
import os
import sys
from dotenv import load_dotenv

# Add root to path
sys.path.insert(0, os.getcwd())

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

print(f"URL: {url}")
print(f"KEY: {key}")
