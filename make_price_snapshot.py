"""Fetch a long-history adjusted-close snapshot for every ticker the dashboard
needs, so the cloud app can render even when Yahoo rate-limits it."""
import sys
import pandas as pd
import yfinance as yf

TICKERS = [
    "SPY", "AOA", "AOR",
    "GLD", "EMXC", "DXJ", "QQQ", "IWM", "DX-Y.NYB", "TLT", "CL=F", "BTC-USD",
    "BIL", "HGER",
]

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
