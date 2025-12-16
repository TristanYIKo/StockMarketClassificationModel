# GitHub Actions Documentation

Automated daily ETL pipeline and prediction generation for the Stock Market Classification Model.

## 📑 Documentation Index

| Document | Description | When to Read |
|----------|-------------|--------------|
| **[SETUP_CHECKLIST.md](SETUP_CHECKLIST.md)** | 5-minute quick start guide | 👉 **START HERE** |
| [QUICK_START_ACTIONS.md](QUICK_START_ACTIONS.md) | One-page reference card | Quick lookups |
| [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md) | Complete setup guide | Detailed configuration |
| [WORKFLOW_DIAGRAM.md](WORKFLOW_DIAGRAM.md) | Visual flow diagrams | Understanding the pipeline |
| [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md) | Troubleshooting help | When things go wrong |
| [STATUS_BADGES.md](STATUS_BADGES.md) | GitHub status badges | Adding badges to README |

## 🚀 Quick Start

New to GitHub Actions? Follow these steps:

1. **[SETUP_CHECKLIST.md](SETUP_CHECKLIST.md)** - Get running in 5 minutes
2. **Test manually** via Actions tab
3. **Wait for first scheduled run** (daily at 5 PM EST)
4. **Monitor** via Actions tab and email notifications

## 📂 Files in This Directory

```
.github/
├── README.md                      ← You are here
├── SETUP_CHECKLIST.md            ← 5-minute setup
├── QUICK_START_ACTIONS.md        ← Quick reference
├── GITHUB_ACTIONS_SETUP.md       ← Detailed guide
├── WORKFLOW_DIAGRAM.md           ← Visual diagrams
├── DEBUGGING_GUIDE.md            ← Troubleshooting
├── STATUS_BADGES.md              ← Badge setup
└── workflows/
    └── daily_etl_and_predictions.yml  ← Main workflow
```

## ⚡ What This Does

Automatically runs **every day at 5 PM EST**:

1. 📊 Downloads latest market data (Yahoo Finance)
2. 📈 Fetches economic indicators (FRED API)
3. 🔧 Computes features and technical indicators
4. 🎯 Generates classification labels
5. 🤖 Runs ML models to predict next day's movements
6. 💾 Stores all data and predictions in Supabase

**Zero manual intervention required!**

## 🎯 Who This Is For

- ✅ Running the stock model in production
- ✅ Want automated daily updates
- ✅ Need fresh predictions every day
- ✅ Prefer "set it and forget it" automation

## 🔑 Requirements

Before you start:

- [x] GitHub account with repository
- [x] Supabase account with database
- [x] FRED API key (free)
- [x] 5 minutes of your time

## 📊 Free Tier Limits

All services have generous free tiers:

| Service | Free Tier | This Project Uses |
|---------|-----------|-------------------|
| GitHub Actions | 2,000 min/month | ~150-450 min/month ✅ |
| Supabase | 500MB database | Variable (check usage) |
| FRED API | 120 req/min | ~10-20 req/day ✅ |
| Yahoo Finance | Rate limited | 1 request/day ✅ |

**Cost: $0/month** (within free tiers)

## 🎓 Learning Path

### Beginner
1. Read [SETUP_CHECKLIST.md](SETUP_CHECKLIST.md)
2. Set up GitHub secrets
3. Run workflow manually to test
4. Check [QUICK_START_ACTIONS.md](QUICK_START_ACTIONS.md) for reference

### Intermediate
1. Read [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md)
2. Understand [WORKFLOW_DIAGRAM.md](WORKFLOW_DIAGRAM.md)
3. Customize schedule or notifications
4. Monitor usage and optimize

### Advanced
1. Review [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md)
2. Add custom steps to workflow
3. Implement error handling
4. Set up advanced monitoring

## 🆘 Getting Help

### Something not working?

1. **Check workflow logs** - Actions tab → Click run → Read error
2. **Common issues** - See [DEBUGGING_GUIDE.md](DEBUGGING_GUIDE.md)
3. **Test locally** - Run ETL and predictions on your machine
4. **Verify secrets** - Ensure all three secrets are set correctly

### Still stuck?

- Review error message carefully
- Search GitHub Actions documentation
- Check Supabase/FRED API status pages
- Test individual components (ETL, then predictions)

## 📈 Monitoring

### Check Status
- **Actions tab** - View all workflow runs
- **Email** - Automatic notifications on failure
- **Badge** - Add to README (see [STATUS_BADGES.md](STATUS_BADGES.md))

### View Data
```bash
# Check latest data
python check_db_dates.py

# View predictions
# Use Supabase dashboard or SQL query
```

## 🔒 Security

- ✅ All secrets stored in GitHub Secrets (encrypted)
- ✅ Never commit API keys to repository
- ✅ Use service_role key for database access
- ✅ Logs automatically mask secret values

## 🎨 Customization

### Change Schedule
Edit `.github/workflows/daily_etl_and_predictions.yml`:
```yaml
schedule:
  - cron: '0 22 * * *'  # 5 PM EST, modify as needed
```

### Add Notifications
Add steps for Slack, Discord, email, etc.
See [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md) for examples.

### Process More Data
Modify ETL scripts to add more symbols or features.
Workflow will automatically use updated code.

## 📚 Additional Resources

### GitHub Actions
- [Official Documentation](https://docs.github.com/en/actions)
- [Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Community Forum](https://github.community/c/actions/41)

### Related Tools
- [Cron Expression Helper](https://crontab.guru/)
- [YAML Validator](https://codebeautify.org/yaml-validator)
- [GitHub Status](https://www.githubstatus.com/)

### Project Documentation
- [Main README](../README.md) - Project overview
- [QUICKSTART.md](../QUICKSTART.md) - Local setup
- [PROJECT_SUMMARY.md](../PROJECT_SUMMARY.md) - Architecture

## ✨ Benefits

Why use automated workflows?

- ⏰ **Consistent** - Runs same time every day
- 🤖 **Reliable** - No manual steps to forget
- 📊 **Fresh data** - Always up-to-date predictions
- 💰 **Free** - Within GitHub free tier
- 🔧 **Easy** - Set up once, runs forever
- 📈 **Scalable** - Add more symbols/features easily

## 🎯 Success Checklist

Your automation is working if:

- [x] Workflow shows green ✅ in Actions tab
- [x] Database has today's date in latest records
- [x] Predictions exist for upcoming trading days
- [x] No error emails from GitHub
- [x] Status badge shows "passing"

## 🎉 What's Next?

After automation is running:

1. **Monitor** - Check occasionally to ensure it's working
2. **Optimize** - Fine-tune models as needed
3. **Expand** - Add more symbols or features
4. **Integrate** - Connect to trading platform or dashboard
5. **Share** - Show off your automated pipeline!

---

**Questions?** Check the documentation files listed above or review the workflow logs.

**Working well?** Consider adding a status badge to show off your automated pipeline!
