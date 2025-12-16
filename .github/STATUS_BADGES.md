# GitHub Actions Status Badges

Add these badges to your main README.md to show the status of your automated workflows.

## Daily ETL and Predictions Badge

```markdown
![Daily ETL and Predictions](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME/actions/workflows/daily_etl_and_predictions.yml/badge.svg)
```

**Replace**:
- `YOUR_USERNAME` with your GitHub username
- `YOUR_REPO_NAME` with your repository name

## Example

If your repo is at `https://github.com/johndoe/stock-model`, use:

```markdown
![Daily ETL and Predictions](https://github.com/johndoe/stock-model/actions/workflows/daily_etl_and_predictions.yml/badge.svg)
```

## Badge Shows

- ✅ Green "passing" = Last workflow run succeeded
- ❌ Red "failing" = Last workflow run failed  
- ⚪ Gray "no status" = Workflow hasn't run yet

## Add to README

Typically placed near the top of your README.md:

```markdown
# Stock Market Classification Model

![Daily ETL and Predictions](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME/actions/workflows/daily_etl_and_predictions.yml/badge.svg)

Your project description here...
```

## Multiple Badges

You can add multiple badges for different workflows:

```markdown
![Daily ETL](https://github.com/USER/REPO/actions/workflows/daily_etl_and_predictions.yml/badge.svg)
![Tests](https://github.com/USER/REPO/actions/workflows/tests.yml/badge.svg)
![Deploy](https://github.com/USER/REPO/actions/workflows/deploy.yml/badge.svg)
```

## Custom Badge Text

Want custom text? Use shields.io:

```markdown
[![ETL Status](https://img.shields.io/github/actions/workflow/status/YOUR_USERNAME/YOUR_REPO_NAME/daily_etl_and_predictions.yml?label=Daily%20Update)](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME/actions/workflows/daily_etl_and_predictions.yml)
```
