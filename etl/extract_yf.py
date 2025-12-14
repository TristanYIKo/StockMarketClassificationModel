from datetime import datetime
from typing import Tuple, Dict
import pandas as pd
import yfinance as yf

US_TZ = "UTC"  # store in UTC, yfinance returns naive dates for daily


def download_ohlcv(symbol: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(symbol, start=start, end=end, interval="1d", auto_adjust=False, progress=False)
    if df.empty:
        return df
    
    # Handle MultiIndex columns (yfinance returns this for single symbols)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    
    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    })
    df.index = pd.to_datetime(df.index).tz_localize(US_TZ).date
    df = df.reset_index().rename(columns={"index": "date"})
    return df[["date", "open", "high", "low", "close", "adj_close", "volume"]]


def download_actions(symbol: str, start: str, end: str) -> pd.DataFrame:
    t = yf.Ticker(symbol)
    div = t.dividends
    splits = t.splits
    df = pd.DataFrame({"date": pd.Series([], dtype='object'), "dividend": pd.Series([], dtype='float64'), "split_ratio": pd.Series([], dtype='float64')})
    if div is not None and not div.empty:
        d = div.loc[(div.index >= start) & (div.index <= end)]
        df_div = d.to_frame(name="dividend")
        # Handle timezone - convert if aware, localize if naive
        if df_div.index.tz is None:
            df_div.index = pd.to_datetime(df_div.index).tz_localize(US_TZ).date
        else:
            df_div.index = pd.to_datetime(df_div.index).tz_convert(US_TZ).date
        df_div_reset = df_div.reset_index().rename(columns={"index": "date"})
        df_div_reset['date'] = df_div_reset['date'].astype(str)
        df['date'] = df['date'].astype(str)
        df = pd.merge(df, df_div_reset, on="date", how="outer")
    if splits is not None and not splits.empty:
        s = splits.loc[(splits.index >= start) & (splits.index <= end)]
        df_s = s.to_frame(name="split_ratio")
        # Handle timezone - convert if aware, localize if naive
        if df_s.index.tz is None:
            df_s.index = pd.to_datetime(df_s.index).tz_localize(US_TZ).date
        else:
            df_s.index = pd.to_datetime(df_s.index).tz_convert(US_TZ).date
        df_s_reset = df_s.reset_index().rename(columns={"index": "date"})
        df_s_reset['date'] = df_s_reset['date'].astype(str)
        if df.empty:
            df = df_s_reset
        else:
            df['date'] = df['date'].astype(str)
            df = pd.merge(df, df_s_reset, on="date", how="outer")
    if df.empty:
        return pd.DataFrame({"date": pd.Series([], dtype='object'), "dividend": pd.Series([], dtype='float64'), "split_ratio": pd.Series([], dtype='float64')})
    df = df.sort_values("date").fillna(0.0)
    return df


def download_macro_series(series_key: str, ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end, interval="1d", progress=False)
    if df.empty:
        return pd.DataFrame({"date": [], "value": []})
    close = df["Close"].copy()
    close.index = pd.to_datetime(close.index).tz_localize(US_TZ).date
    out = close.reset_index().rename(columns={"index": "date", "Close": "value"})
    return out[["date", "value"]]
