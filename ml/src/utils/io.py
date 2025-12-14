"""
Data loading utilities for classification model training.
Supports both CSV and Supabase data sources.
"""

import os
import pandas as pd
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def load_from_csv(csv_path: str) -> pd.DataFrame:
    """
    Load classification dataset from CSV file.
    
    Args:
        csv_path: Path to CSV file
        
    Returns:
        DataFrame with columns: symbol, date, y_class_1d, features...
    """
    logger.info(f"Loading data from CSV: {csv_path}")
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    df = pd.read_csv(csv_path)
    
    # Parse date column
    df['date'] = pd.to_datetime(df['date'])
    
    # Sort by symbol and date (critical for time-series)
    df = df.sort_values(['symbol', 'date']).reset_index(drop=True)
    
    logger.info(f"Loaded {len(df):,} rows, {len(df.columns)} columns")
    logger.info(f"Date range: {df['date'].min()} to {df['date'].max()}")
    logger.info(f"Symbols: {sorted(df['symbol'].unique())}")
    
    # Validate required columns
    required_cols = ['symbol', 'date', 'y_class_1d']
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    return df


def load_from_supabase(
    query: Optional[str] = None,
    url: Optional[str] = None,
    key: Optional[str] = None
) -> pd.DataFrame:
    """
    Load classification dataset from Supabase.
    
    Args:
        query: SQL query (optional, uses default if None)
        url: Supabase URL (reads from env if None)
        key: Supabase service role key (reads from env if None)
        
    Returns:
        DataFrame with columns: symbol, date, y_class_1d, features...
    """
    logger.info("Loading data from Supabase...")
    
    # Get credentials
    url = url or os.getenv("SUPABASE_URL")
    key = key or os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        raise ValueError(
            "Supabase credentials not found. Set SUPABASE_URL and SUPABASE_KEY "
            "environment variables or pass them as arguments."
        )
    
    # Import here to avoid requiring supabase if using CSV
    try:
        from supabase import create_client
    except ImportError:
        raise ImportError(
            "supabase package not installed. Install with: pip install supabase"
        )
    
    # Default query
    if query is None:
        query = """
        select * 
        from public.v_classification_dataset_1d 
        order by symbol, date
        """
    
    # Create client and fetch data
    client = create_client(url, key)
    
    # For large datasets, we need to paginate
    all_data = []
    batch_size = 1000
    offset = 0
    
    logger.info("Fetching data in batches...")
    while True:
        result = client.table('v_classification_dataset_1d')\
            .select('*')\
            .order('symbol')\
            .order('date')\
            .range(offset, offset + batch_size - 1)\
            .execute()
        
        if not result.data:
            break
        
        all_data.extend(result.data)
        offset += batch_size
        
        if len(result.data) < batch_size:
            break
        
        if offset % 5000 == 0:
            logger.info(f"  Fetched {offset:,} rows...")
    
    df = pd.DataFrame(all_data)
    
    # Parse date column
    df['date'] = pd.to_datetime(df['date'])
    
    # Sort (should already be sorted, but ensure)
    df = df.sort_values(['symbol', 'date']).reset_index(drop=True)
    
    logger.info(f"Loaded {len(df):,} rows, {len(df.columns)} columns")
    logger.info(f"Date range: {df['date'].min()} to {df['date'].max()}")
    logger.info(f"Symbols: {sorted(df['symbol'].unique())}")
    
    # Validate required columns
    required_cols = ['symbol', 'date', 'y_class_1d']
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    return df


def save_to_parquet(df: pd.DataFrame, output_path: str):
    """
    Save DataFrame to parquet for faster loading in future runs.
    
    Args:
        df: DataFrame to save
        output_path: Path to save parquet file
    """
    logger.info(f"Saving data to parquet: {output_path}")
    df.to_parquet(output_path, index=False, compression='snappy')
    logger.info(f"Saved {len(df):,} rows to {output_path}")


def load_from_parquet(parquet_path: str) -> pd.DataFrame:
    """
    Load DataFrame from parquet file.
    
    Args:
        parquet_path: Path to parquet file
        
    Returns:
        DataFrame
    """
    logger.info(f"Loading data from parquet: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    logger.info(f"Loaded {len(df):,} rows, {len(df.columns)} columns")
    return df
