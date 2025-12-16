# GitHub Actions Troubleshooting: Exit Code 1

## Problem
Your workflow failed with "Process completed with exit code 1"

## Most Common Causes

### 1. Missing or Incorrect GitHub Secrets ⚠️

The workflow needs these three secrets configured:

| Secret Name | Where to Get It | Format |
|------------|-----------------|--------|
| `SUPABASE_URL` | Supabase Dashboard → Settings → API → Project URL | `https://xxxxx.supabase.co` |
| `SUPABASE_KEY` | Supabase Dashboard → Settings → API → **service_role key** | Long JWT token starting with `eyJ...` |
| `FRED_API_KEY` | https://fred.stlouisfed.org/docs/api/api_key.html | 32-character hex string |

**⚠️ CRITICAL:** You MUST use the **service_role key** from Supabase, NOT the anon key!

### How to Add/Update Secrets:

1. Go to your GitHub repository
2. Click **Settings** (top menu)
3. Click **Secrets and variables** → **Actions** (left sidebar)
4. Click **New repository secret** (or edit existing ones)
5. Add each secret with EXACT names above

### 2. Using Your .env File Values

Based on your .env file, here are the values you should use:

```
SUPABASE_URL: https://lvyiqjyezdopetefijvj.supabase.co
SUPABASE_KEY: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx2eWlxanllemRvcGV0ZWZpanZqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjU2NTc4MjgsImV4cCI6MjA4MTIzMzgyOH0.5KEmgP8lue-bsZRw5oemxziRKCPqKhIMypmxW4oraAc
FRED_API_KEY: ac719bdb58926b100c7cbf979f677037
```

**⚠️ WARNING:** The key in your .env appears to be the "anon" key. For GitHub Actions, you need the **service_role** key instead!

### Get Your Service Role Key:

1. Go to [Supabase Dashboard](https://app.supabase.com/)
2. Select your project (lvyiqjyezdopetefijvj)
3. Settings → API
4. Scroll down to "Project API keys"
5. Copy the **service_role** key (not anon/public)
6. Add it as `SUPABASE_KEY` secret in GitHub

## Quick Fix Steps

### Step 1: Add the Correct Service Role Key

```
1. Supabase Dashboard → Your Project
2. Settings → API → Service Role Key (secret)
3. Copy the entire key
4. GitHub Repo → Settings → Secrets → Add SUPABASE_KEY
5. Paste the service_role key
```

### Step 2: Verify All Three Secrets

Go to: **Settings → Secrets and variables → Actions**

You should see:
- ✅ SUPABASE_URL
- ✅ SUPABASE_KEY (service_role)
- ✅ FRED_API_KEY

### Step 3: Re-run the Workflow

1. Go to **Actions** tab
2. Click on the failed workflow run
3. Click **Re-run jobs** → **Re-run all jobs**

## What the Workflow Does

When properly configured, the workflow will:

1. ✅ Update market data for **all symbols** (SPY, QQQ, IWM, DIA)
2. ✅ Fetch FRED economic indicators
3. ✅ Compute features for all symbols
4. ✅ Generate predictions for all symbols (both 1d and 5d horizons)
5. ✅ Store everything in Supabase

## Testing Locally First

Before relying on GitHub Actions, test locally:

```bash
# Test ETL (all symbols)
python etl/main.py --mode incremental

# Test predictions (all symbols)
python quick_add_predictions_all_symbols.py

# Verify results
python verify_all_predictions.py
```

If these work locally but GitHub Actions fails, it's definitely a secrets issue.

## Common Error Messages

### "SUPABASE_URL is not set"
→ Add SUPABASE_URL secret in GitHub

### "SUPABASE_KEY is not set"  
→ Add SUPABASE_KEY secret in GitHub

### "FRED_API_KEY environment variable not set"
→ Add FRED_API_KEY secret in GitHub

### "Permission denied" or "Authentication failed"
→ You're using anon key instead of service_role key

### "Could not find table"
→ Database schema issue (run migrations first)

## After Fixing

Once secrets are properly configured:
- Workflow will run automatically daily at 5 PM EST
- Updates all 4 symbols (SPY, QQQ, IWM, DIA)
- Generates predictions for all symbols
- Your website will show latest data for all symbols

## Need Help?

1. Check the workflow logs in GitHub Actions for specific error messages
2. Compare your secrets with the required format above
3. Verify locally that your credentials work
4. Ensure you're using service_role key, not anon key
