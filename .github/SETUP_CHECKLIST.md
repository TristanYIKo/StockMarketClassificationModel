# 5-Minute Setup Checklist

Get your automated daily ETL and predictions running in 5 minutes.

## ⚡ Quick Setup

### 1. Get Your API Keys (2 minutes)

#### Supabase
- [ ] Go to [Supabase Dashboard](https://app.supabase.com/)
- [ ] Click your project
- [ ] Settings → API
- [ ] Copy **URL** (looks like: `https://xxxxx.supabase.co`)
- [ ] Copy **service_role key** (NOT anon key!)

#### FRED
- [ ] Go to [FRED API](https://fredaccount.stlouisfed.org/apikeys)
- [ ] Click "Request API Key" (free, instant)
- [ ] Copy your key (32 character string)

### 2. Add Secrets to GitHub (2 minutes)

- [ ] Go to your GitHub repo
- [ ] Click **Settings** tab
- [ ] Click **Secrets and variables** → **Actions**
- [ ] Click **New repository secret**

Add these three secrets:

| Name | Value |
|------|-------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Your service_role key |
| `FRED_API_KEY` | Your FRED API key |

### 3. Commit Workflow File (1 minute)

The workflow file is already created at:
```
.github/workflows/daily_etl_and_predictions.yml
```

- [ ] Commit this file to your repository
- [ ] Push to GitHub (main branch)

```bash
git add .github/
git commit -m "Add automated daily ETL and predictions workflow"
git push origin main
```

### 4. Test It! (1 minute)

- [ ] Go to **Actions** tab in GitHub
- [ ] Click **Daily ETL and Predictions**
- [ ] Click **Run workflow** button
- [ ] Click green **Run workflow** (leave dates empty)
- [ ] Watch it run! 🚀

## ✅ Verification

After workflow completes (5-15 minutes):

### Check Workflow Status
- [ ] Go to Actions tab
- [ ] See green checkmark ✅
- [ ] Click to view logs

### Verify Database
Run locally:
```bash
python check_db_dates.py
```

Should show today's date for latest data.

### Check Predictions
Query Supabase:
```sql
SELECT * FROM model_predictions_classification 
ORDER BY date DESC 
LIMIT 10;
```

Should see fresh predictions.

## 🎉 You're Done!

Your pipeline now runs automatically every day at 5 PM EST.

## 📋 What Happens Daily

Every day at 5 PM:
1. ✅ Fetches latest stock data (SPY, QQQ, IWM)
2. ✅ Updates macro indicators (VIX, rates, etc.)
3. ✅ Computes features and labels
4. ✅ Generates predictions for next day
5. ✅ Stores everything in Supabase

## ⚠️ Troubleshooting

### Workflow didn't start?
- Wait 15-60 minutes (GitHub has delays)
- Check secrets are set correctly
- Verify Actions are enabled in repo settings

### Workflow failed?
- Click on the failed run
- Read error message in logs
- Check [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md)

### Still stuck?
1. Test locally first:
   ```bash
   python -m etl.main --mode incremental
   ```
2. Check API keys are valid
3. Verify database connection

## 📚 Next Steps

- [ ] Add status badge to README ([STATUS_BADGES.md](STATUS_BADGES.md))
- [ ] Set up email/Slack notifications
- [ ] Customize schedule if needed
- [ ] Monitor usage in GitHub billing

## 🔗 Resources

- [Full Setup Guide](GITHUB_ACTIONS_SETUP.md) - Detailed documentation
- [Quick Reference](QUICK_START_ACTIONS.md) - One-page cheat sheet
- [Debugging Guide](DEBUGGING_GUIDE.md) - Troubleshooting help
- [Workflow Diagram](WORKFLOW_DIAGRAM.md) - Visual overview

## 💡 Pro Tips

1. **First run may take longer** - Be patient!
2. **Check on weekends/holidays** - Markets closed = no new data
3. **Monitor your quotas** - Free tier is generous but not unlimited
4. **Keep models updated** - Retrain periodically and commit updates
5. **Review logs occasionally** - Catch issues early

---

**Time to complete:** ~5 minutes  
**Difficulty:** Easy 🟢  
**Cost:** Free (within GitHub/Supabase free tiers)
