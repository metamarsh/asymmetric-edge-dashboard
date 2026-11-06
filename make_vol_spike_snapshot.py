"""Daily closes behind the Markets page's After a Volatility Spike section
(added November 5, 2026): the Cboe Volatility Index (^VIX) with the S&P 500
(^GSPC) since 1990, and the Cboe Nasdaq-100 Volatility Index (^VXN) with the
Nasdaq-100 (^NDX) since 2001. Price indexes, no dividends. The app reads this
file for history and tops it up from Yahoo for the most recent sessions, so a
stale snapshot only matters when Yahoo is unavailable.

    python make_vol_spike_snapshot.py      (inside ae-dashboard-deploy)
"""
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

TICKERS = {"^VIX": "1990-01-01", "^GSPC": "1989-12-01", "^VXN": "2001-01-01", "^NDX": "2000-12-01"}

frames, failed = {}, []
for t, start in TICKERS.items():
    try:
        raw = yf.download(t, start=start, auto_adjust=False, progress=False, threads=False)
    except Exception as e:
        print("FAIL", t, type(e).__name__, e)
        failed.append(t)
        continue
    if raw is None or raw.empty:
        print("EMPTY", t)
        failed.append(t)
        continue
    s = raw["Close"]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    s.index = pd.to_datetime(s.index).tz_localize(None)
    frames[t] = s.sort_index().dropna()
    print("OK", t, len(s), str(s.index[0].date()), str(s.index[-1].date()))

if failed:
    print("FAILED TICKERS:", ",".join(failed), "- snapshot not written")
    sys.exit(1)

df = pd.DataFrame(frames).sort_index()
# Keep completed sessions only: drop today's row before 4:15 p.m. Eastern.
now_et = datetime.now(ZoneInfo("America/New_York"))
if now_et.hour * 60 + now_et.minute < 16 * 60 + 15:
    df = df[df.index < pd.Timestamp(now_et.date())]
df.index.name = "date"
df.to_csv("vol_spike_snapshot.csv", float_format="%.4f")
print("WROTE vol_spike_snapshot.csv rows=%d last=%s" % (len(df), str(df.index[-1].date())))
