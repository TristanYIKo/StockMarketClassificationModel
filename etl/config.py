from dataclasses import dataclass, field
from datetime import date
from typing import List, Dict

@dataclass
class ETLConfig:
    symbols: List[str] = ("SPY", "QQQ", "DIA", "IWM")
    start: date = date(2000, 1, 1)
    end: date = date.today()
    mode: str = "backfill"  # backfill or incremental
    y_thresh: float = 0.002
    
    # FRED macro series
    fred_series: List[str] = field(default_factory=lambda: [
        "DGS2", "DGS10", "FEDFUNDS", "EFFR", "T10YIE",
        "BAMLH0A0HYM2", "WALCL", "RRPONTSYD", "SOFR"
    ])
    
    # Cross-asset proxies
    proxy_tickers: List[str] = field(default_factory=lambda: [
        "^VIX", "^VIX9D", "^VVIX",  # Volatility
        "UUP",  # Dollar
        "GLD", "USO",  # Commodities
        "HYG", "LQD", "TLT",  # Credit/Bonds
        "RSP"  # Breadth
    ])
    
    feature_windows: Dict[str, List[int]] = None
    supabase_url: str = ""
    supabase_key: str = ""
    fred_api_key: str = ""

    def __post_init__(self):
        if self.feature_windows is None:
            self.feature_windows = {
                "returns": [1, 5, 10, 20],
                "volatility": [5, 10, 20, 60],
                "sma": [5, 10, 20, 50, 200],
                "ema": [5, 10, 20, 50, 200],
                "drawdown": [20, 60]
            }
