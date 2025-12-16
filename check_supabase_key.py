"""
Help identify which Supabase key you're using.
"""
import os
from dotenv import load_dotenv
import jwt
from datetime import datetime

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

print("\n" + "="*70)
print("Supabase Key Analyzer")
print("="*70 + "\n")

if not url or not key:
    print("❌ Missing SUPABASE_URL or SUPABASE_KEY in .env file")
    exit(1)

print(f"SUPABASE_URL: {url}")
print(f"Key Preview: {key[:20]}...{key[-20:]}\n")

# Decode JWT to check role
try:
    # JWT tokens have 3 parts separated by dots
    # We can decode without verification to read the payload
    decoded = jwt.decode(key, options={"verify_signature": False})
    
    role = decoded.get('role', 'unknown')
    iss = decoded.get('iss', 'unknown')
    exp = decoded.get('exp', 0)
    
    exp_date = datetime.fromtimestamp(exp) if exp else None
    
    print("📋 Key Information:")
    print(f"  Role: {role}")
    print(f"  Issuer: {iss}")
    if exp_date:
        print(f"  Expires: {exp_date.strftime('%Y-%m-%d')}")
    
    print("\n" + "="*70)
    
    if role == 'anon':
        print("⚠️  WARNING: You are using an ANON key!")
        print("="*70)
        print("\nFor GitHub Actions, you NEED the SERVICE_ROLE key!")
        print("\n📝 How to get the correct key:")
        print("  1. Go to https://app.supabase.com/")
        print("  2. Select your project")
        print("  3. Settings → API")
        print("  4. Find 'service_role' key (secret)")
        print("  5. Copy it and add to GitHub Secrets as SUPABASE_KEY")
        print("\n⚠️  Do NOT use the anon/public key in GitHub Actions!")
        
    elif role == 'service_role':
        print("✅ CORRECT: You are using a SERVICE_ROLE key!")
        print("="*70)
        print("\nThis key is suitable for GitHub Actions.")
        print("Add it to GitHub Secrets as SUPABASE_KEY")
        
    else:
        print(f"❓ UNKNOWN ROLE: {role}")
        print("="*70)
        print("\nVerify this is the correct key from Supabase.")
    
    print("\n" + "="*70)
    print("Current .env values for GitHub Secrets:")
    print("="*70)
    print(f"\nSUPABASE_URL = {url}")
    print(f"SUPABASE_KEY = {key}")
    print(f"FRED_API_KEY = {os.getenv('FRED_API_KEY')}")
    print("\n" + "="*70)
    
except Exception as e:
    print(f"❌ Error decoding key: {e}")
    print("Make sure SUPABASE_KEY is a valid JWT token")
