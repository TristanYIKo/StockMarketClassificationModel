# GitHub Actions Debugging Guide

Common issues and solutions when running automated ETL and predictions.

## 🔍 Checking Workflow Status

### View Logs
1. Go to **Actions** tab in GitHub
2. Click on the workflow run
3. Click on the job name (`etl-and-predict`)
4. Click on any step to see detailed output
5. Look for red ❌ marks indicating failures

### Download Logs
- Click the ⚙️ gear icon in top-right of workflow run
- Select **Download log archive**
- Unzip and search through logs locally

## ❌ Common Errors

### Error: "SUPABASE_URL is not set"

**Cause**: Missing GitHub secret

**Solution**:
1. Go to Settings → Secrets and variables → Actions
2. Add `SUPABASE_URL` secret with your Supabase project URL
3. Format: `https://your-project.supabase.co`

### Error: "SUPABASE_KEY is not set"

**Cause**: Missing GitHub secret

**Solution**:
1. Get your service_role key from Supabase Dashboard → Settings → API
2. Add `SUPABASE_KEY` secret in GitHub
3. ⚠️ Use **service_role** key, NOT anon/public key

### Error: "FRED_API_KEY environment variable not set"

**Cause**: Missing FRED API key

**Solution**:
1. Register at https://fred.stlouisfed.org/docs/api/api_key.html
2. Add `FRED_API_KEY` secret in GitHub

### Error: "No module named 'etl'"

**Cause**: Python path issue or missing installation

**Solution**:
- Check that `requirements.txt` includes all dependencies
- Workflow should install both root and `ml/requirements.txt`
- Verify project structure is intact

### Error: Rate limit exceeded

**Cause**: Too many API requests

**Solution**:
- **Yahoo Finance**: Reduce frequency or number of symbols
- **FRED**: Free tier is 120 requests/minute (usually sufficient)
- Add delays between requests if needed

### Error: "No such file or directory: model.pkl"

**Cause**: Trained models not in repository

**Solution**:
1. Train models locally: `python train_models_1d.py`
2. Commit models from `ml/artifacts/models/` to git
3. Or store models in Supabase and modify prediction script to download them

### Error: Workflow runs but no data updates

**Cause**: Market closed (weekend/holiday) or incremental mode finding no new data

**Solution**:
- Check if it's a trading day
- Manually trigger with specific dates to test
- Check logs for "No new data" messages

## 🐞 Advanced Debugging

### Test Locally First

Before debugging in GitHub Actions, test locally:

```bash
# Set environment variables
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your-service-role-key"
export FRED_API_KEY="your-fred-key"

# Test ETL
python -m etl.main --mode incremental

# Test predictions
cd ml
python -m src.predict.predict_and_store --data_source supabase --horizons 1d 5d --store_supabase
```

### Add Debug Output

Modify workflow to add more logging:

```yaml
- name: Debug Environment
  run: |
    echo "Python version:"
    python --version
    echo "Installed packages:"
    pip list
    echo "Current directory:"
    pwd
    echo "Directory contents:"
    ls -la
```

### Enable Debug Logging

GitHub Actions supports debug logging:

1. Go to Settings → Secrets and variables → Actions
2. Add secret: `ACTIONS_STEP_DEBUG` = `true`
3. Re-run workflow to see detailed logs

### Check Python Path

Add to workflow:

```yaml
- name: Check Python Path
  run: |
    python -c "import sys; print('\n'.join(sys.path))"
    python -c "import etl; print(etl.__file__)"
```

## 🕐 Timing Issues

### Workflow Doesn't Run on Schedule

**Possible causes**:
1. GitHub Actions has delays (15-60 min after scheduled time is normal)
2. Repository is archived or Actions disabled
3. Workflow file has syntax errors

**Check**:
- Validate YAML syntax: https://codebeautify.org/yaml-validator
- Check repository Actions settings are enabled
- Ensure workflow file is on default branch (main/master)

### Timeout Errors

**Default timeout**: 360 minutes (6 hours)

**If workflow times out**:
- ETL may be processing too much data
- Network issues with external APIs
- Consider splitting into separate jobs

**Set custom timeout**:
```yaml
jobs:
  etl-and-predict:
    timeout-minutes: 60  # 1 hour max
```

## 📊 Monitoring Best Practices

### Add Status Checks

```yaml
- name: Verify Update Success
  run: |
    python -c "
    from etl.supabase_client import SupabaseDB
    import sys
    db = SupabaseDB()
    result = db.client.table('daily_bars').select('date').order('date', desc=True).limit(1).execute()
    if not result.data:
        print('Error: No data in database')
        sys.exit(1)
    print(f'Latest data date: {result.data[0][\"date\"]}')
    "
```

### Set Up Notifications

**Slack notification on failure**:
```yaml
- name: Notify Slack on Failure
  if: failure()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

**Email is automatic** - GitHub emails you on workflow failure by default.

## 🔒 Security Issues

### Leaked Secrets in Logs

**Prevention**:
- Never `echo` or `print` secret values
- GitHub auto-masks secrets, but be careful
- Review logs before sharing

**If secret leaked**:
1. Immediately rotate the API key/secret
2. Update GitHub secret
3. Review who has access to repository

### Permissions Errors

**Database access denied**:
- Ensure using service_role key, not anon key
- Check Supabase RLS policies if enabled
- Verify key hasn't been revoked

## 💰 Usage and Costs

### Check GitHub Actions Minutes

1. Go to Settings → Billing
2. View Actions usage
3. Each workflow run counts against monthly quota

**Free tier**: 2,000 minutes/month (private repos)

### Optimize Runtime

**Reduce duration**:
- Use caching for Python dependencies (workflow already does this)
- Process only necessary data
- Skip redundant steps

**Example caching**:
```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    cache: 'pip'  # Caches pip dependencies
```

## 🆘 Getting Help

### GitHub Community
- [GitHub Actions Community Forum](https://github.community/c/actions/41)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

### Project-Specific Help
1. Check workflow logs first
2. Test commands locally
3. Verify all secrets are set correctly
4. Review ETL and prediction script outputs

### Create an Issue
When reporting problems, include:
- Workflow run link
- Error message
- Relevant log excerpts
- Steps to reproduce locally

## 📚 Useful Resources

- [GitHub Actions Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Cron Expression Editor](https://crontab.guru/)
- [YAML Validator](https://codebeautify.org/yaml-validator)
- [GitHub Actions Marketplace](https://github.com/marketplace?type=actions)
