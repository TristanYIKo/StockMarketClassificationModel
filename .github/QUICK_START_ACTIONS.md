# Quick Reference: Automated Daily Updates

## ⏰ Schedule
Runs automatically every day at **5 PM EST** (10 PM UTC)

## 🔧 Setup Checklist

- [ ] Add `SUPABASE_URL` to GitHub Secrets
- [ ] Add `SUPABASE_KEY` to GitHub Secrets (use service_role key)
- [ ] Add `FRED_API_KEY` to GitHub Secrets
- [ ] Commit workflow file to repository
- [ ] Enable GitHub Actions in repository settings

## 📍 Where to Find Things

| Item | Location |
|------|----------|
| Workflow file | `.github/workflows/daily_etl_and_predictions.yml` |
| Setup guide | `.github/GITHUB_ACTIONS_SETUP.md` |
| Add secrets | GitHub Repo → Settings → Secrets and variables → Actions |
| View runs | GitHub Repo → Actions tab |

## 🚀 Manual Run

1. Go to **Actions** tab
2. Select **Daily ETL and Predictions**
3. Click **Run workflow**
4. (Optional) Enter custom dates
5. Click green **Run workflow** button

## 📊 What Gets Updated

✅ Yahoo Finance stock data (OHLCV)  
✅ FRED economic indicators  
✅ Technical features & indicators  
✅ Regime classifications  
✅ Classification labels  
✅ Model predictions (1d & 5d horizons)  

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Workflow doesn't run | Check secrets are configured |
| ETL fails | Verify API keys are valid |
| No new data | May be weekend/market holiday |
| Prediction fails | Check if models exist in repo |

## 💡 Tips

- Workflows may take 15-60 minutes for first scheduled run
- Failed runs will email you automatically
- Check Actions tab for detailed logs
- Free tier: 2,000 minutes/month (plenty for daily runs)
