"""
Look-ahead test for the ETL feature pipeline. READ-ONLY against Supabase.

    python validate_no_lookahead.py              # SPY and IWM, 13 cutoff days each
    python validate_no_lookahead.py QQQ DIA      # other symbols
    python validate_no_lookahead.py --control    # plant a leak; the test must catch it

For each cutoff day T, the features are rebuilt twice with the exact ETL
transforms -- once from the full stored history, once from history truncated at
T -- and the row for T is compared column by column. A feature whose value at T
changes when later dates are removed is using information from after T.

What this does NOT cover: data that is stamped with a date before it was
published (FRED observations). Those are handled by a publication lag in
ml/src/data/features.py, because no amount of recomputation can reveal them.

Exit code 1 if any column differs (or, with --control, if the planted leak is
missed).
"""

import os
import sys
import warnings

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
from dotenv import load_dotenv

warnings.filterwarnings("ignore")
load_dotenv(os.path.join(os.getcwd(), ".env"))

import etl.transform_features as tf_module  # noqa: E402
from etl.build_events import build_events_calendar  # noqa: E402
from etl.config import ETLConfig  # noqa: E402
from etl.extract_fred import compute_fred_derived_features  # noqa: E402
from etl.extract_proxies import (PROXY_TICKERS, compute_proxy_features,  # noqa: E402
                                 compute_relative_strength_features)
from etl.supabase_client import SupabaseDB  # noqa: E402
from etl.transform_features_context import (forward_fill_macro_conservative,  # noqa: E402
                                            merge_context_features)
from etl.transform_lags import apply_lags  # noqa: E402
from etl.transform_regimes import compute_all_regimes  # noqa: E402

ETFS = list(ETLConfig.symbols)
CONTROL = "--control" in sys.argv
compute_features = tf_module.compute_features

if CONTROL:
    _real = compute_features

    def compute_features(bars):  # noqa: F811 -- deliberate leak for the control run
        out = _real(bars)
        out["PLANTED_tomorrow_close"] = bars["close"].shift(-1).values[: len(out)]
        return out


def fetch_all(db, table, cols, key, value):
    out, start = [], 0
    while True:
        r = (db.client.table(table).select(cols).eq(key, value)
             .order("date").range(start, start + 999).execute())
        out += r.data or []
        if len(r.data or []) < 1000:
            return out
        start += 1000


def load_inputs(db):
    ids = db.get_asset_id_map()

    def bars(sym):
        df = pd.DataFrame(fetch_all(db, "daily_bars", "date,open,high,low,close,adj_close,volume",
                                    "asset_id", ids[sym]))
        df["date"] = pd.to_datetime(df["date"])
        for c in ["open", "high", "low", "close", "adj_close", "volume"]:
            df[c] = pd.to_numeric(df[c])
        return df.sort_values("date").reset_index(drop=True)

    etf = {s: bars(s) for s in ETFS}
    proxies = {s: bars(s) for s in PROXY_TICKERS if s in ids}
    mids = db.get_macro_series_id_map()
    macro = {}
    for sid in ETLConfig.__dataclass_fields__["fred_series"].default_factory():
        if sid in mids:
            m = pd.DataFrame(fetch_all(db, "macro_daily", "date,value", "series_id", mids[sid]))
            if not m.empty:
                m["date"] = pd.to_datetime(m["date"])
                m["value"] = pd.to_numeric(m["value"])
                macro[sid] = m
    return etf, proxies, macro


def build(sym, etf, proxies, macro, events, cutoff=None):
    """The ETL feature pipeline (etl/main.py step 7), on inputs cut at `cutoff`."""
    def cut(d):
        return d[d["date"] <= cutoff].copy() if cutoff is not None else d.copy()
    e = {s: cut(d) for s, d in etf.items()}
    p = {s: cut(d) for s, d in proxies.items()}
    mac = {s: cut(d) for s, d in macro.items()}
    f = compute_features(e[sym])
    f = merge_context_features(f, compute_fred_derived_features(mac),
                               compute_proxy_features({**p, "SPY": e["SPY"]}),
                               compute_relative_strength_features(e), events)
    f = forward_fill_macro_conservative(f, max_gap_days=5)
    f = compute_all_regimes(f)
    f = apply_lags(f)
    f["date"] = pd.to_datetime(f["date"])
    return f.set_index("date")


def differs(x, y) -> bool:
    try:
        x, y = float(x), float(y)
    except (TypeError, ValueError):
        return str(x) != str(y)
    if np.isnan(x) and np.isnan(y):
        return False
    return np.isnan(x) != np.isnan(y) or abs(x - y) > 1e-9 * max(1.0, abs(x))


def main() -> int:
    syms = [a for a in sys.argv[1:] if not a.startswith("--")] or (["SPY"] if CONTROL else ["SPY", "IWM"])
    db = SupabaseDB()
    print("Loading stored inputs from Supabase (read-only) ...", flush=True)
    etf, proxies, macro = load_inputs(db)
    events = build_events_calendar(mcal.get_calendar("NYSE"), "2000-01-01",
                                   (pd.Timestamp.today() + pd.Timedelta(days=30)).date().isoformat())

    failed = False
    for sym in syms:
        dates = etf[sym]["date"]
        rng = np.random.default_rng(7)
        picks = list(rng.choice(dates[dates > "2004-01-01"].values, 10, replace=False))
        month_end = dates[dates.dt.month != dates.shift(-1).dt.month].iloc[-3]
        wednesday = dates[dates.dt.dayofweek == 2].iloc[-40]   # weekly WALCL
        cutoffs = sorted(set(pd.to_datetime(picks + [month_end, wednesday, dates.iloc[-30]])))

        print(f"\n{sym}: comparing {len(cutoffs)} cutoff days ...", flush=True)
        full = build(sym, etf, proxies, macro, events)
        bad = {}
        for T in cutoffs:
            trunc = build(sym, etf, proxies, macro, events, T)
            if T not in full.index or T not in trunc.index:
                continue
            for col in full.columns.intersection(trunc.columns):
                if differs(full.at[T, col], trunc.at[T, col]):
                    bad.setdefault(col, []).append((T.date(), full.at[T, col], trunc.at[T, col]))

        if not bad:
            print(f"  PASS: all {full.shape[1]} columns identical at every cutoff -- "
                  f"no feature uses later dates")
        else:
            failed = True
            print(f"  {len(bad)} of {full.shape[1]} columns CHANGED when later dates were removed:")
            for col, hits in sorted(bad.items()):
                d, x, y = hits[0]
                print(f"    {col:<32} differs on {len(hits)}/{len(cutoffs)} days  "
                      f"e.g. {d}: full={x} truncated={y}")

    if CONTROL:
        print("\nCONTROL: the planted leak " + ("was caught. The test works." if failed
                                                else "was MISSED. The test is broken."))
        return 0 if failed else 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
