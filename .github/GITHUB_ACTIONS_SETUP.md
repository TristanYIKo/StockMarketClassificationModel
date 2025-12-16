# GitHub Actions Setup for Daily ETL and Predictions

This repository includes an automated workflow that runs daily at 5 PM to update all data and generate predictions.

## Workflow File

**Location**: [.github/workflows/daily_etl_and_predictions.yml](.github/workflows/daily_etl_and_predictions.yml)

## What It Does

The daily workflow automatically:

1. **Fetches Latest Market Data**: Downloads OHLCV data from Yahoo Finance for all configured symbols
2. **Updates Macroeconomic Data**: Pulls latest FRED data (economic indicators)
3. **Computes Features**: Calculates technical indicators, lags, and regime features
4. **Generates Labels**: Creates classification targets for model training
5. **Runs Predictions**: Generates predictions for the next trading day using trained models (both 1-day and 5-day horizons)
6. **Stores Results**: Saves all data and predictions to your Supabase database

## Required GitHub Secrets

Before the workflow can run, you need to configure these secrets in your GitHub repository:

### How to Add Secrets:

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each of these secrets:

| Secret Name | Description | Where to Get It |
|------------|-------------|-----------------|
| `SUPABASE_URL` | Your Supabase project URL | Supabase Dashboard → Settings → API → Project URL |
| `SUPABASE_KEY` | Your Supabase service role key | Supabase Dashboard → Settings → API → Service Role Key |
| `FRED_API_KEY` | FRED API key for economic data | Register at https://fred.stlouisfed.org/docs/api/api_key.html |

⚠️ **Important**: Use the **service_role** key from Supabase, not the anon/public key, as the workflow needs full database access.

## Schedule

- **Default**: Runs every day at **10:00 PM UTC** (5:00 PM EST / 2:00 PM PST)
- **Note**: GitHub Actions uses UTC time. Adjust the cron schedule in the workflow file if you need a different time.

### Cron Schedule Format
```yaml
- cron: '0 22 * * *'  # 10 PM UTC = 5 PM EST
```

Common timezone conversions:
- 5 PM EST = 22:00 UTC
- 5 PM EDT = 21:00 UTC  
- 5 PM PST = 01:00 UTC (next day)
- 5 PM PDT = 00:00 UTC (next day)

## Manual Triggering

You can also run the workflow manually:

1. Go to **Actions** tab in GitHub
2. Select **Daily ETL and Predictions**
3. Click **Run workflow**
4. Optionally specify custom start/end dates
5. Click **Run workflow**

### Manual Run Options:
- **No inputs**: Runs incremental update from latest DB date to today
- **Start date only**: Updates from specified date to today
- **Start and end dates**: Updates specific date range

## Monitoring

### View Workflow Runs:
1. Go to **Actions** tab in your repository
2. Click on **Daily ETL and Predictions**
3. See history of all runs with status indicators

### Check Logs:
- Click on any workflow run to see detailed logs
- Each step shows console output
- Failed steps are highlighted in red

### Notifications:
By default, GitHub will:
- Email you if a scheduled workflow fails
- Show status badges you can add to README
- Send notifications to your GitHub notifications

## Troubleshooting

### Workflow Doesn't Start
- **Check**: Secrets are configured correctly
- **Check**: Repository is not private or has Actions enabled
- **Note**: First scheduled run may take 15-60 minutes after workflow file is added

### API Rate Limits
- **Yahoo Finance**: Free tier has rate limits; workflow runs once daily to avoid issues
- **FRED API**: Free tier allows 120 requests/minute
- **Supabase**: Check your plan's API limits

### Failed ETL
- Check logs in Actions tab
- Common issues:
  - Missing or invalid API keys
  - Network timeouts (retry workflow)
  - Market holidays (no new data available)
  - Database connection issues

### Failed Predictions
- Ensure trained models exist in `ml/artifacts/models/`
- Models must be committed to repository or stored in Supabase
- Check `ml/config/model_registry.yaml` is up to date

## Workflow Components

### Jobs:
1. **etl-and-predict**: Single job that runs all steps sequentially

### Steps:
1. **Checkout repository**: Gets latest code
2. **Set up Python**: Installs Python 3.11
3. **Install dependencies**: Installs packages from requirements.txt
4. **Set up environment**: Verifies all secrets are present
5. **Run ETL Pipeline**: Executes `python -m etl.main`
6. **Generate Predictions**: Executes `python -m src.predict.predict_and_store`
7. **Verify Data**: Runs validation checks
8. **Summary**: Reports job status

## Customization

### Change Schedule
Edit the cron expression in [daily_etl_and_predictions.yml](.github/workflows/daily_etl_and_predictions.yml):

```yaml
on:
  schedule:
    - cron: '0 22 * * *'  # Modify this line
```

### Add Notifications
Add a notification step (e.g., Slack, Discord, email):

```yaml
- name: Notify on failure
  if: failure()
  run: |
    # Add your notification logic here
```

### Run on Different Events
Add more triggers:

```yaml
on:
  schedule:
    - cron: '0 22 * * *'
  push:
    branches: [ main ]  # Run on push to main
  pull_request:
    branches: [ main ]  # Run on PRs
```

## Cost Considerations

- **GitHub Actions**: Free tier includes 2,000 minutes/month for private repos
- **Daily run**: Uses approximately 5-15 minutes per run
- **Monthly cost**: ~150-450 minutes/month = within free tier
- **Supabase**: Monitor your database usage and API calls
- **FRED API**: Free tier with rate limits

## Local Testing

Before relying on the automated workflow, test locally:

```bash
# Test ETL
python -m etl.main --mode incremental

# Test predictions
cd ml
python -m src.predict.predict_and_store --data_source supabase --horizons 1d 5d --store_supabase

# Test verification
python check_db_dates.py
```

## Security Best Practices

✅ **DO**:
- Use GitHub Secrets for all sensitive data
- Use service role key for database access
- Review workflow logs for exposed credentials
- Rotate API keys periodically

❌ **DON'T**:
- Commit API keys or secrets to repository
- Use anon keys for automated workflows
- Share your FRED or Supabase credentials
- Store secrets in code or comments

## Getting Help

If you encounter issues:

1. Check the Actions logs for error messages
2. Verify all secrets are correctly configured
3. Test the ETL and prediction scripts locally
4. Check Supabase database for connectivity
5. Review FRED API status and quotas

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Cron Expression Generator](https://crontab.guru/)
- [Supabase Documentation](https://supabase.io/docs)
- [FRED API Documentation](https://fred.stlouisfed.org/docs/api/)
