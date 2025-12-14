"""
Build events calendar with strict ET alignment.

PRUNED EVENT TYPES (high-ROI macro releases only):
- fomc: FOMC meeting days (8 per year)
- cpi_release: CPI release days (~12 per year)
- nfp_release: NFP release days (~12 per year)

DROPPED EVENT TYPES (low ROI):
- month_end: redundant with calendar features
- quarter_end: redundant with calendar features
- options_expiry_week: weak signal, high frequency noise

NO LEAKAGE: Event flags indicate the event occurs, NOT the outcome.
"""

from datetime import datetime, timedelta
import pandas as pd
from zoneinfo import ZoneInfo

ET_TZ = ZoneInfo("America/New_York")


def compute_month_end_events(nyse_calendar, start: str, end: str) -> pd.DataFrame:
    """Find last trading day of each month."""
    schedule = nyse_calendar.schedule(start_date=start, end_date=end)
    trading_days = schedule.index.date
    
    df = pd.DataFrame({"date": trading_days})
    df["year_month"] = pd.to_datetime(df["date"]).dt.to_period("M")
    
    # Last trading day per month
    month_ends = df.groupby("year_month")["date"].max().reset_index()
    month_ends["event_type"] = "month_end"
    month_ends["event_name"] = "Month End"
    month_ends["source"] = "NYSE calendar"
    
    return month_ends[["date", "event_type", "event_name", "source"]]


def compute_quarter_end_events(nyse_calendar, start: str, end: str) -> pd.DataFrame:
    """Find last trading day of each quarter."""
    schedule = nyse_calendar.schedule(start_date=start, end_date=end)
    trading_days = schedule.index.date
    
    df = pd.DataFrame({"date": trading_days})
    df["year_quarter"] = pd.to_datetime(df["date"]).dt.to_period("Q")
    
    # Last trading day per quarter
    quarter_ends = df.groupby("year_quarter")["date"].max().reset_index()
    quarter_ends["event_type"] = "quarter_end"
    quarter_ends["event_name"] = "Quarter End"
    quarter_ends["source"] = "NYSE calendar"
    
    return quarter_ends[["date", "event_type", "event_name", "source"]]


def compute_options_expiry_week(nyse_calendar, start: str, end: str) -> pd.DataFrame:
    """
    Find options expiry weeks (week containing 3rd Friday of month).
    
    Returns all trading days Mon-Fri of that week.
    """
    schedule = nyse_calendar.schedule(start_date=start, end_date=end)
    trading_days = schedule.index.date
    
    events = []
    
    # Iterate through each month
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    current = start_dt.replace(day=1)
    
    while current <= end_dt:
        # Find 3rd Friday
        fridays = []
        for day in range(1, 32):
            try:
                candidate = current.replace(day=day)
                if candidate.weekday() == 4:  # Friday
                    fridays.append(candidate)
            except ValueError:
                break
        
        if len(fridays) >= 3:
            third_friday = fridays[2]
            
            # Find Monday of that week
            monday = third_friday - timedelta(days=third_friday.weekday())
            
            # All trading days Mon-Fri of that week
            for d in range(7):
                check_date = (monday + timedelta(days=d)).date()
                if check_date in trading_days:
                    events.append({
                        "date": check_date,
                        "event_type": "options_expiry_week",
                        "event_name": f"Options Expiry Week {third_friday.strftime('%Y-%m')}",
                        "source": "computed"
                    })
        
        # Next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    
    return pd.DataFrame(events)


def load_fomc_dates() -> pd.DataFrame:
    """
    Load known FOMC meeting dates.
    
    Replace this with actual FOMC calendar data.
    For now, returns empty DataFrame.
    """
    # TODO: Populate with historical FOMC dates from Fed calendar
    # Example: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
    fomc_dates = [
        # 2024 dates (example)
        "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12",
        "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
        # 2025 dates (example - verify from Fed calendar)
        "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
        "2025-07-30", "2025-09-17", "2025-11-05", "2025-12-17",
    ]
    
    df = pd.DataFrame({
        "date": pd.to_datetime(fomc_dates).date,
        "event_type": "fomc",
        "event_name": "FOMC Meeting",
        "source": "Federal Reserve"
    })
    
    return df


def load_cpi_release_dates() -> pd.DataFrame:
    """
    Load known CPI release dates.
    
    CPI is typically released mid-month (around 13th-15th).
    Replace with actual BLS release calendar.
    """
    # TODO: Populate with historical CPI release dates from BLS
    # Example approach: CPI released ~13th of each month
    cpi_dates = [
        # 2024 (example)
        "2024-01-11", "2024-02-13", "2024-03-12", "2024-04-10",
        "2024-05-15", "2024-06-12", "2024-07-11", "2024-08-14",
        "2024-09-11", "2024-10-10", "2024-11-13", "2024-12-11",
        # 2025 (example - verify from BLS calendar)
        "2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10",
        "2025-05-13", "2025-06-11", "2025-07-11", "2025-08-13",
        "2025-09-10", "2025-10-10", "2025-11-12", "2025-12-10",
    ]
    
    df = pd.DataFrame({
        "date": pd.to_datetime(cpi_dates).date,
        "event_type": "cpi_release",
        "event_name": "CPI Release",
        "source": "BLS"
    })
    
    return df


def load_nfp_release_dates() -> pd.DataFrame:
    """
    Load known NFP (Non-Farm Payrolls) release dates.
    
    NFP is typically released first Friday of each month.
    Replace with actual BLS release calendar.
    """
    # TODO: Populate with historical NFP release dates from BLS
    # Typically first Friday of the month
    nfp_dates = [
        # 2024 (example)
        "2024-01-05", "2024-02-02", "2024-03-08", "2024-04-05",
        "2024-05-03", "2024-06-07", "2024-07-05", "2024-08-02",
        "2024-09-06", "2024-10-04", "2024-11-01", "2024-12-06",
        # 2025 (example - verify from BLS calendar)
        "2025-01-10", "2025-02-07", "2025-03-07", "2025-04-04",
        "2025-05-02", "2025-06-06", "2025-07-03", "2025-08-01",
        "2025-09-05", "2025-10-03", "2025-11-07", "2025-12-05",
    ]
    
    df = pd.DataFrame({
        "date": pd.to_datetime(nfp_dates).date,
        "event_type": "nfp_release",
        "event_name": "NFP Release",
        "source": "BLS"
    })
    
    return df


def build_events_calendar(nyse_calendar, start: str, end: str) -> pd.DataFrame:
    """
    Build PRUNED events calendar with only high-ROI macro releases.
    
    Returns DataFrame with columns: date, event_type, event_name, source
    
    ONLY includes:
    - FOMC meeting days
    - CPI release days
    - NFP release days
    
    REMOVED (low ROI):
    - month_end, quarter_end, options_expiry_week
    """
    events = []
    
    # Known event dates (high ROI macro releases only)
    fomc = load_fomc_dates()
    cpi = load_cpi_release_dates()
    nfp = load_nfp_release_dates()
    
    # Filter to date range
    start_date = pd.to_datetime(start).date()
    end_date = pd.to_datetime(end).date()
    
    for df in [fomc, cpi, nfp]:
        if not df.empty:
            df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
            events.append(df)
    
    # Combine all
    all_events = pd.concat([e for e in events if not e.empty], ignore_index=True)
    
    return all_events
