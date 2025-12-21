# Stock Market Classification Pipeline

An automated machine learning pipeline that predicts short term stock market direction using daily market and macroeconomic data.

## What It Does

- Pulls daily market price data
- Fetches macroeconomic indicators
- Engineers features and labels
- Runs classification models
- Stores predictions in a database

The entire pipeline runs automatically with no manual intervention.

## How It Runs

- Scheduled GitHub Actions workflow runs once per day
- Data is processed and predictions are generated
- Results are saved for analysis or dashboards

## Tech Stack

- Python
- GitHub Actions
- Yahoo Finance
- FRED API
- Supabase (Postgres)
- scikit learn and XGBoost

## Models

- Classification models trained on historical data
- Separate models for different prediction horizons
- Time based validation to avoid data leakage

## Automation

- Daily scheduled runs
- Manual trigger available
- Fully automated once configured
