"""Fetch a long-history adjusted-close snapshot for every ticker the dashboard
needs, so the cloud app can render even when Yahoo rate-limits it."""
import sys
import pandas as pd
import yfinance as yf

TICKERS = [
    "SPY", "AOA", "AOR",
    "GLD", "EMXC", "DXJ", "QQQ", "IWM", "DX-Y.NYB", "TLT", "CL=F", "BTC-USD",
    "BIL", "HGER", "IBIT",
    # Every other ticker held since inception (October 22, 2026), for the
    # What Drove the Month and Rebalance Log sections, plus BTAL for Risk vs. Return.
    "BTAL", "BITO", "COPX", "EZU", "GBTC", "LBNOX", "LOLDX",
]

# Pick up any ticker held since inception automatically, so a new holding is in
# the snapshot without editing this list. CUSIPs and money-market sweeps are skipped.
try:
    import re
    _hv = pd.read_csv("holdings_daily_values.csv", parse_dates=["date"]).set_index("date")
    _hv = _hv[_hv.index >= "2023-12-20"]
    for _t in _hv.columns[(_hv.fillna(0) > 1).any()]:
        if re.fullmatch(r"[A-Z][A-Z.\-]{0,9}", _t) and _t not in TICKERS and _t != "SPAXX":
            TICKERS.append(_t)
except Exception as _e:
    print("holdings scan skipped:", _e)

START = "2014-01-01"

frames = {}
failed = []
for t in TICKERS:
    try:
        raw = yf.download(t, start=START, auto_adjust=True, progress=False, threads=False)
    except Exception as e:
        print("FAIL", t, type(e).__name__, e)
        failed.append(t)
        continue
    if raw is None or raw.empty:
        print("EMPTY", t)
        failed.append(t)
        continue
    if isinstance(raw.columns, pd.MultiIndex):
        s = raw["Close"].iloc[:, 0]
    else:
        s = raw["Close"]
    s.index = pd.to_datetime(s.index).tz_localize(None)
    frames[t] = s.sort_index()
    print("OK", t, len(s), str(s.index[0].date()), str(s.index[-1].date()))

if not frames:
    print("NOTHING FETCHED")
    sys.exit(1)

df = pd.DataFrame(frames)
df.index.name = "date"
df = df.sort_index()
df.to_csv("price_snapshot.csv", float_format="%.6f")
print("WROTE price_snapshot.csv rows=%d cols=%d last=%s" % (len(df), df.shape[1], str(df.index[-1].date())))
if failed:
    print("FAILED TICKERS:", ",".join(failed))
