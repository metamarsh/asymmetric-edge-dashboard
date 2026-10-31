import streamlit as st
import pandas as pd
from pandas.tseries.holiday import (
    AbstractHolidayCalendar, Holiday, GoodFriday, USLaborDay,
    USMartinLutherKingJr, USMemorialDay, USPresidentsDay, USThanksgivingDay,
    nearest_workday, sunday_to_monday,
)
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta
import os
import json
import re
import textwrap
import time

# ---------- Page config ----------
st.set_page_config(
    page_title="Asymmetric Edge Dashboard",
    page_icon="ðŸ“ˆ",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- Brand tokens ----------
TEXT_PRIMARY = "#484848"
TEXT_SECONDARY = "#666677"
TEXT_MUTED = "#777788"
BRAND_PURPLE = "#3A0CA3"
BRAND_TEAL = "#30C7B5"
GAIN_GREEN = "#1F8A4C"
LOSS_RED = "#C0392B"
GRID_COLOR = "#eeeeee"
ZERO_LINE = "#dddddd"

# ---------- Custom CSS ----------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

    /* Hide Streamlit chrome */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stDeployButton"] {display: none;}

    .stApp {
        background-color: #ffffff;
    }

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
        color: """ + TEXT_PRIMARY + """;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1100px;
    }

    h2 {
        font-weight: 700 !important;
        font-size: 1.35rem !important;
        color: """ + TEXT_PRIMARY + """ !important;
        margin-top: 0 !important;
        margin-bottom: 0.25rem !important;
        letter-spacing: -0.01em;
    }

    /* Header */
    .brand-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.25rem;
    }
    .brand-header .brand-name {
        font-size: 1.6rem;
        font-weight: 700;
        color: """ + TEXT_PRIMARY + """;
        letter-spacing: -0.02em;
    }
    .brand-header .brand-tag {
        font-size: 0.85rem;
        color: """ + TEXT_MUTED + """;
        margin-left: 0.5rem;
        border-left: 2px solid """ + BRAND_PURPLE + """;
        padding-left: 0.5rem;
    }
    .brand-sub {
        font-size: 0.82rem;
        color: """ + TEXT_SECONDARY + """;
        margin-bottom: 2rem;
    }

    .footer-text {
        font-size: 0.72rem;
        color: """ + TEXT_MUTED + """;
        line-height: 1.6;
        margin-top: 0.75rem;
    }

    /* Streamlit caption */
    [data-testid="stCaptionContainer"] {
        color: """ + TEXT_MUTED + """;
    }

    /* Dividers */
    hr {
        border-color: #e8e8ee !important;
        margin: 2.5rem 0 !important;
    }
    /* Pills styling */
    button[data-testid="stBaseButton-pills"] {
        border: 1px solid #ddd !important;
        border-radius: 8px !important;
        color: """ + TEXT_SECONDARY + """ !important;
        background-color: #ffffff !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        padding: 0.3rem 0.9rem !important;
        transition: all 0.15s ease !important;
    }
    button[data-testid="stBaseButton-pills"]:hover {
        border-color: #bbb !important;
        background-color: #f5f5f8 !important;
    }
    button[data-testid="stBaseButton-pills"][aria-checked="true"] {
        background-color: #f0edf8 !important;
        border-color: """ + BRAND_PURPLE + """ !important;
        color: """ + BRAND_PURPLE + """ !important;
        font-weight: 600 !important;
    }

    /* Center toggle widgets (used by the Portfolio Growth legend) */
    div[data-testid="stToggle"] {
        display: flex !important;
        justify-content: center !important;
        margin-top: 0.25rem;
    }
</style>
""", unsafe_allow_html=True)

# ---------- Brand colors from design spec ----------
SERIES_COLORS = {
    "AsymEdge": "#3A0CA3",  # Brand purple, hero color
    "S&P 500":         "#9CA3AF",  # Neutral gray, contextual reference (sits outside the gradient family)
    "80/20":           "#4361EE",  # Brand blue, primary benchmark
    "60/40":           "#4CC9F0",  # Brand cyan, secondary balanced benchmark
}

# Bar-chart variant of the series palette. Bars at full opacity in the brand
# colors read as overwhelming and flatten the visual hierarchy, so for bar
# charts we use a softer AE purple and benchmark hues desaturated by ~20%.
# Line charts continue to use SERIES_COLORS so the brand identity stays
# intact in the time-series views.
BAR_SERIES_COLORS = {
    "AsymEdge": "#4F2DB8",  # Softer AE purple (lighter, less saturated than brand)
    "S&P 500":         "#C5CAD3",  # Lighter cool gray so the benchmark recedes behind the AE bar
    "80/20":           "#5575DD",  # Brand blue with ~20% saturation removed
    "60/40":           "#5BC4E1",  # Brand cyan with ~20% saturation removed
}

SERIES_OPACITY = {
    "AsymEdge": 1.0,
    "S&P 500":         0.30,
    "80/20":           0.70,
    "60/40":           0.50,
}

BENCHMARK_TICKERS = {
    "S&P 500": "SPY",
    "80/20": "AOA",
    "60/40": "AOR",
}

ASSET_CLASS_TICKERS = {
    "Gold": "GLD",
    "Emerging Mkts": "EMXC",
    "Japan": "DXJ",
    "S&P 500": "SPY",
    "Nasdaq-100": "QQQ",
    "Russell 2000": "IWM",
    "U.S. Dollar": "DX-Y.NYB",
    "LT Treasuries": "TLT",
    "Bitcoin": "IBIT",
    "Commodities": "HGER",
}

# Plain-language footnote notes for Asset Class Returns, keyed by ticker so a
# note appears only while its ticker is on the chart. {label} is filled with
# that ticker's label from ASSET_CLASS_TICKERS.
ASSET_CLASS_FOOTNOTES = {
    "EMXC": "{label} uses EMXC, which holds emerging-market stocks but excludes China.",
    "DXJ": "{label} uses DXJ, which hedges out the yen, so its return reflects Japanese stocks without currency swings.",
    "DX-Y.NYB": "The U.S. Dollar Index (DX-Y.NYB) is a price index with no income, so its bar is price return only.",
}

SERIES_ORDER = ["AsymEdge", "80/20", "60/40", "S&P 500"]


def series_label(name):
    """Name a series as subscribers see it. "AsymEdge" stays the key in code;
    every legend, header and toggle shows the full brand name."""
    return "Asymmetric Edge" if name == "AsymEdge" else name

# Palette for the Total Return Comparison chart. The first four swatches mirror
# the four chart series colors (per the design spec rule) so users can easily
# pick a color that matches the rest of the dashboard. The remaining entries
# are broader brand-adjacent options.
COMPARE_PALETTE = [
    "#3A0CA3",  # Brand purple (Asymmetric Edge)
    "#4361EE",  # Brand blue (80/20)
    "#4CC9F0",  # Brand cyan (60/40)
    "#9CA3AF",  # Neutral gray (S&P 500)
    "#30C7B5",  # Brand teal
    "#6A9BAD",  # Steel blue-green
    "#F4D35E",  # Gold
    "#E07A5F",  # Terracotta
    "#D62828",  # Red
    "#F77F00",  # Orange
    "#4895EF",  # Sky blue
    "#2D6A4F",  # Forest green
    "#9B5DE5",  # Lavender purple
]

# Common layout settings for all Plotly charts. Backgrounds are solid white
# (rather than transparent) so the "Download plot as png" button produces an
# image with a solid white background suitable for embedding in the newsletter,
# rather than a transparent PNG that disappears against dark UIs.
DARK_LAYOUT = dict(
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
    font=dict(family="DM Sans, sans-serif", size=13, color=TEXT_SECONDARY),
)

# Chart-interaction tools that don't apply to static, table-style charts.
# Removing them leaves the toolbar focused on the download button.
STATIC_CHART_TOOLS_REMOVED = [
    "zoom2d", "pan2d", "select2d", "lasso2d",
    "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d",
    "toggleSpikelines", "hoverClosestCartesian", "hoverCompareCartesian",
]


LOCAL_TZ_NAME = "America/Denver"


def local_now() -> datetime:
    """Wall-clock time in the dashboard's home timezone.

    Streamlit Community Cloud containers run on UTC, which rolls the calendar
    date over at 6 p.m. Mountain. Left alone that makes every "today" default
    on the page a day early all evening, including the as-of date used for the
    partial-month extension. Everything user-facing goes through this instead
    of datetime.now().
    """
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(LOCAL_TZ_NAME)).replace(tzinfo=None)
    except Exception:
        return datetime.now()


def format_clock(moment: datetime, with_year: bool = False) -> str:
    """Format a timestamp with lowercase a.m./p.m., house style."""
    pattern = "%b %d, %Y %I:%M %p" if with_year else "%b %d, %I:%M %p"
    return moment.strftime(pattern).replace("AM", "a.m.").replace("PM", "p.m.")


def chart_config(chart_name, static=False):
    """Build the shared Plotly config for a chart.

    scale=3 renders the "Download plot as a png" button output at 3x
    resolution, giving a crisp image suitable for slides, reports, and print.

    chart_name becomes the downloaded PNG's filename with the date and time
    appended, e.g. "Portfolio Growth 2026-07-06 2.35 PM.png", instead of
    Plotly's default "newplot.png". The timestamp is captured when the page
    renders. Streamlit reruns the script on every interaction, so this is
    effectively when the snapshot is taken.

    Pass static=True for table-style charts to hide the zoom/pan tools that
    don't apply to a static layout.
    """
    now = local_now()
    stamp = f"{now:%Y-%m-%d} {now.hour % 12 or 12}.{now:%M} {now:%p}"
    config = {
        "displaylogo": False,
        "toImageButtonOptions": {
            "format": "png",
            "scale": 3,
            "filename": f"{chart_name} {stamp}",
        },
    }
    if static:
        config["modeBarButtonsToRemove"] = list(STATIC_CHART_TOOLS_REMOVED)
    return config


# ---------- Data loading ----------
@st.cache_data(ttl=3600)
def load_portfolio_data():
    """Load the Fidelity-anchored portfolio series produced by the pipeline.

    Looks first in the pipeline reconstruction folder (the canonical output
    location), then falls back to a local copy in the dashboard folder.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pipeline_dir = os.path.join(os.path.dirname(script_dir), "Portfolio Hist Val Reconstruction")
    primary = os.path.join(pipeline_dir, "asymmetric_edge_series.csv")
    fallback = os.path.join(script_dir, "asymmetric_edge_series.csv")
    if os.path.exists(primary):
        path = primary
    elif os.path.exists(fallback):
        path = fallback
    else:
        st.error(
            "Portfolio series CSV not found. Run the pipeline to generate "
            "'asymmetric_edge_series.csv', or place a copy in the dashboard folder."
        )
        st.stop()
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.rename(columns={"value": "portfolio_value"})
    df = df[["date", "portfolio_value"]].copy()
    df = df.sort_values("date").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600)
def load_reconstruction_data():
    """Load the close-only daily reconstruction produced by portfolio_valuation.py.

    This is the un-anchored, Yahoo-based daily valuation used to give the
    open month a realistic daily shape. The dashboard reads this in addition
    to the anchored series so the partial-month extender can interpolate
    daily values across the open month rather than drawing a straight line
    from the last closed-month value to the MTD endpoint.

    Returns a DataFrame with columns ['date', 'portfolio_value'] sorted by
    date, or None if the file is not found or the schema is unrecognized.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pipeline_dir = os.path.join(os.path.dirname(script_dir), "Portfolio Hist Val Reconstruction")
    primary = os.path.join(pipeline_dir, "reconstructed_account_value.csv")
    fallback = os.path.join(script_dir, "reconstructed_account_value.csv")
    if os.path.exists(primary):
        path = primary
    elif os.path.exists(fallback):
        path = fallback
    else:
        return None
    try:
        df = pd.read_csv(path, parse_dates=["date"])
    except Exception:
        return None
    # Accept either 'portfolio_value' (canonical) or 'value' as the value column
    if "portfolio_value" not in df.columns and "value" in df.columns:
        df = df.rename(columns={"value": "portfolio_value"})
    if "portfolio_value" not in df.columns or "date" not in df.columns:
        return None
    df = df[["date", "portfolio_value"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Resilient price fetching
#
# On shared hosts (Streamlit Community Cloud in particular) Yahoo Finance
# regularly answers with YFRateLimitError for some or all tickers, because the
# request comes from an IP shared with hundreds of other apps. Every price
# fetch therefore goes through _fetch_closes(), which assembles a series from
# three sources in descending order of preference:
#
#   1. Yahoo, with one batch attempt followed by per-ticker retries.
#   2. price_snapshot.csv, a committed long-history snapshot of adjusted
#      closes regenerated on the PC whenever the pipeline runs.
#   3. Yahoo's chart endpoint hit directly with a browser-impersonating
#      client, a different code path from the library call that often answers
#      when yf.download has been throttled.
#
# Nothing in this layer raises, and nothing calls st.stop(). A ticker that
# cannot be resolved is simply absent from the result and its chart line is
# skipped, which is always preferable to taking the whole dashboard down.
# ---------------------------------------------------------------------------

PRICE_SNAPSHOT_NAME = "price_snapshot.csv"


@st.cache_data(ttl=86400)
def load_price_snapshot() -> pd.DataFrame:
    """Committed adjusted-close history, used whenever Yahoo is unavailable."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, PRICE_SNAPSHOT_NAME),
        os.path.join(os.path.dirname(script_dir), "Portfolio Hist Val Reconstruction", PRICE_SNAPSHOT_NAME),
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_csv(path, parse_dates=["date"], index_col="date")
        except Exception:
            continue
        try:
            df.index = pd.to_datetime(df.index)
            if getattr(df.index, "tz", None) is not None:
                df.index = df.index.tz_localize(None)
        except Exception:
            continue
        return df.sort_index()
    return pd.DataFrame()


def _clean_series(values) -> pd.Series:
    s = pd.to_numeric(values, errors="coerce").dropna()
    s = s[s > 0]
    return s.sort_index()


def _yahoo_closes(tickers, fetch_start, fetch_end, attempts: int = 3) -> dict:
    """Best-effort Yahoo close prices. Returns {ticker: Series}; never raises."""
    tickers = list(dict.fromkeys(tickers))
    collected = {}

    def _absorb(raw, expected):
        if raw is None or len(raw) == 0:
            return
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                if "Close" not in raw.columns.get_level_values(0):
                    return
                close = raw["Close"].copy()
            else:
                if "Close" not in raw.columns:
                    return
                close = raw[["Close"]].copy()
                close.columns = [expected[0]]
            close.index = pd.to_datetime(close.index)
            if getattr(close.index, "tz", None) is not None:
                close.index = close.index.tz_localize(None)
        except Exception:
            return
        for col in close.columns:
            name = str(col)
            if name in collected:
                continue
            s = _clean_series(close[col])
            if len(s):
                collected[name] = s

    # One batch attempt first: cheapest path when Yahoo is behaving.
    try:
        _absorb(
            yf.download(tickers, start=fetch_start, end=fetch_end,
                        auto_adjust=True, progress=False, threads=False),
            tickers,
        )
    except Exception:
        pass

    # Then retry only the stragglers, one at a time, with a little backoff.
    for attempt in range(attempts):
        missing = [t for t in tickers if t not in collected]
        if not missing:
            break
        if attempt:
            time.sleep(1.0 + attempt)
        for t in missing:
            try:
                _absorb(
                    yf.download(t, start=fetch_start, end=fetch_end,
                                auto_adjust=True, progress=False, threads=False),
                    [t],
                )
            except Exception:
                continue

    return collected


# Yahoo's public chart endpoint, hit directly with a browser-impersonating
# client. This is a different code path from yf.download (no cookie/crumb
# handshake, no batch endpoint), so it frequently answers on a host where the
# library call has been rate limited. Used only to top up a series' tail.
_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/%s"
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


def _http_json(url, params):
    """GET JSON, preferring curl_cffi's browser impersonation when available."""
    try:
        from curl_cffi import requests as cffi_requests
        r = cffi_requests.get(url, params=params, impersonate="chrome", timeout=20)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    try:
        import requests as _requests
        r = _requests.get(url, params=params, timeout=20,
                          headers={"User-Agent": _BROWSER_UA})
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _fallback_closes(tickers, fetch_start, fetch_end) -> dict:
    """Second-chance adjusted closes straight from Yahoo's chart endpoint."""
    collected = {}
    p1 = int(pd.Timestamp(fetch_start).timestamp())
    p2 = int((pd.Timestamp(fetch_end) + timedelta(days=1)).timestamp())
    for t in dict.fromkeys(tickers):
        data = _http_json(_CHART_URL % t, {
            "period1": p1, "period2": p2, "interval": "1d",
            "events": "div,splits", "includeAdjustedClose": "true",
        })
        try:
            result = data["chart"]["result"][0]
            stamps = result["timestamp"]
            indicators = result["indicators"]
            adj = indicators.get("adjclose")
            values = adj[0]["adjclose"] if adj else indicators["quote"][0]["close"]
            idx = pd.to_datetime(pd.Series(stamps), unit="s").dt.normalize()
            s = _clean_series(pd.Series(values, index=idx))
        except Exception:
            continue
        if len(s):
            collected[t] = s[~s.index.duplicated(keep="last")]
    return collected


def _chain_onto(base: pd.Series, extra: pd.Series, ratio_link: bool) -> pd.Series:
    """Extend ``base`` with the part of ``extra`` that falls after base's end.

    With ratio_link=True the two series sit on different adjustment bases
    (an unadjusted feed, for instance), so ``extra`` is converted into a
    return chain off its overlapping value rather than used at face value.
    """
    base = base.dropna()
    extra = extra.dropna()
    if base.empty:
        return extra
    if extra.empty:
        return base
    last_dt = base.index[-1]
    tail = extra[extra.index > last_dt]
    if tail.empty:
        return base
    if ratio_link:
        overlap = extra.index[extra.index <= last_dt]
        if len(overlap) == 0:
            return base
        anchor = float(extra.loc[overlap[-1]])
        if not np.isfinite(anchor) or anchor <= 0:
            return base
        tail = tail / anchor * float(base.iloc[-1])
    return pd.concat([base, tail]).sort_index()


def _fetch_closes(tickers, start_date: str, end_date: str,
                  lead_days: int = 7, trail_days: int = 3) -> pd.DataFrame:
    """Adjusted closes for ``tickers`` over the requested window.

    Yahoo is preferred; the committed snapshot backfills whatever Yahoo will
    not return, and the direct chart endpoint tops up the most recent days
    when the library call is rate limited. Returns an empty DataFrame rather than raising if all three fail.
    """
    tickers = [t for t in dict.fromkeys(tickers) if t]
    if not tickers:
        return pd.DataFrame()

    fetch_start = (pd.Timestamp(start_date) - timedelta(days=lead_days)).strftime("%Y-%m-%d")
    fetch_end = (pd.Timestamp(end_date) + timedelta(days=trail_days)).strftime("%Y-%m-%d")
    lo, hi = pd.Timestamp(fetch_start), pd.Timestamp(fetch_end)

    snap = load_price_snapshot()
    snap_series = {}
    for t in tickers:
        if t in snap.columns:
            s = _clean_series(snap[t])
            s = s[(s.index >= lo) & (s.index <= hi)]
            if len(s):
                snap_series[t] = s

    live = _yahoo_closes(tickers, fetch_start, fetch_end)

    series = {}
    for t in tickers:
        y = live.get(t)
        s = snap_series.get(t)
        if y is not None and s is not None:
            # If Yahoo returned the full window, trust it outright; otherwise
            # keep the snapshot's history and append Yahoo's newer rows.
            if y.index[0] <= s.index[0] + timedelta(days=5):
                series[t] = y
            else:
                series[t] = _chain_onto(s, y, ratio_link=False)
        elif y is not None:
            series[t] = y
        elif s is not None:
            series[t] = s

    # Anything the library would not return gets a direct chart-endpoint
    # top-up, so the most recent session is not missing just because the batch
    # call was throttled.
    stale = [t for t in tickers if t not in live]
    if stale:
        for t, s in _fallback_closes(stale, fetch_start, fetch_end).items():
            if t in series:
                series[t] = _chain_onto(series[t], s, ratio_link=False)
            else:
                series[t] = s

    # If the committed snapshot runs past everything Yahoo and the chart
    # endpoint returned, append the snapshot's newer rows. This covers the
    # case where Yahoo leaves the latest session's close blank for hours
    # (September 29, 2026) and the snapshot was filled from another source.
    for t, s in snap_series.items():
        cur = series.get(t)
        if cur is not None and len(cur) and s.index[-1] > cur.index[-1]:
            series[t] = pd.concat([cur, s[s.index > cur.index[-1]]]).sort_index()

    if not series:
        return pd.DataFrame()

    df = pd.DataFrame(series).sort_index()
    df = df[(df.index >= lo) & (df.index <= hi)]
    return df


@st.cache_data(ttl=3600)
def load_benchmark_data(start_date: str, end_date: str):
    return _fetch_closes(list(BENCHMARK_TICKERS.values()), start_date, end_date)


@st.cache_data(ttl=3600)
def load_asset_class_data(tickers: tuple, start_date: str, end_date: str):
    # tickers is an argument (not read from the global) so it is part of the
    # cache key: editing ASSET_CLASS_TICKERS invalidates the cached download
    # instead of serving the old ticker set for up to an hour.
    return _fetch_closes(list(tickers), start_date, end_date)


@st.cache_data(ttl=3600)
def load_bil_data(start_date: str, end_date: str):
    """Fetch BIL daily prices and resample to monthly returns for the Sortino risk-free rate.

    BIL (SPDR Bloomberg 1-3 Month T-Bill ETF) launched in May 2007. Months that
    fall outside BIL's history are treated as 0% risk-free by the caller via
    reindex + fillna.
    """
    frame = _fetch_closes(["BIL"], start_date, end_date)
    if frame.empty or "BIL" not in frame.columns:
        return None
    close = frame["BIL"].dropna()
    if len(close) < 2:
        return None
    monthly = close.resample("ME").last().pct_change().dropna()
    return monthly


@st.cache_data(ttl=3600)
def load_bil_daily(start_date: str, end_date: str):
    """BIL daily adjusted closes, the risk-free leg of the rolling 12-month
    Sortino ratio. None when no prices load; the caller then treats the
    risk-free rate as zero."""
    frame = _fetch_closes(["BIL"], start_date, end_date)
    if frame.empty or "BIL" not in frame.columns:
        return None
    close = frame["BIL"].dropna()
    return close if len(close) >= 2 else None


def normalize_to_10k(series: pd.Series) -> pd.Series:
    """Rebase a price series to 10,000 at its first observation.

    Returns an empty series when there is nothing to rebase, so a benchmark
    that failed to download drops out of the chart instead of raising.
    """
    clean = series.dropna()
    if clean.empty:
        return pd.Series(dtype="float64")
    first_val = float(clean.iloc[0])
    if not np.isfinite(first_val) or first_val == 0:
        return pd.Series(dtype="float64")
    return series / first_val * 10000


def compute_return(series: pd.Series, start_date, end_date):
    s = series.dropna()
    mask_start = s.index >= pd.Timestamp(start_date)
    mask_end = s.index <= pd.Timestamp(end_date)
    if mask_start.sum() == 0 or mask_end.sum() == 0:
        return None
    start_val = s[mask_start].iloc[0]
    end_val = s[mask_end].iloc[-1]
    return (end_val / start_val - 1) * 100


def compute_max_drawdown(series: pd.Series, start_date, end_date):
    s = series.dropna()
    mask = (s.index >= pd.Timestamp(start_date)) & (s.index <= pd.Timestamp(end_date))
    s = s[mask]
    if len(s) < 2:
        return 0
    rolling_max = s.cummax()
    drawdown = (s - rolling_max) / rolling_max * 100
    return drawdown.min()


def compute_summary_metrics(daily_series, rf_monthly=None, start_date=None, end_date=None):
    """Compute the full set of performance metrics for the Performance Summary table.

    Methodology mirrors compute_metrics in Adaptive Portfolio Dashboard.py:
      - Monthly-based metrics (CAGR, Sortino, Calmar, Vol, Best/Worst Year, Win Rate)
        resample the full daily series to month-end values, anchor on the
        prior month-end (or the first available daily value at inception), and
        compute returns from there. This ensures the first monthly return
        represents the start_date's calendar month rather than dropping it.
      - Daily-based metrics (Max DD Daily, Worst Single Day) use the daily
        series within the user's literal [start_date, end_date] range.
      - Total Return is the monthly cumulative product (matches Adaptive),
        so it includes the full calendar month of start_date.
      - Sortino uses BIL monthly returns as the risk-free rate when available.
    """
    s_full = daily_series.dropna()
    if len(s_full) < 2:
        return {}

    start_ts = pd.Timestamp(start_date) if start_date is not None else s_full.index[0]
    end_ts = pd.Timestamp(end_date) if end_date is not None else s_full.index[-1]

    # ---- Monthly returns with prior month-end anchor ----
    all_month_ends = s_full.resample("ME").last().dropna()
    if len(all_month_ends) < 1:
        return {}

    start_month_begin = pd.Timestamp(start_ts.year, start_ts.month, 1)
    prior_mask = all_month_ends.index < start_month_begin

    if prior_mask.any():
        # Standard case: anchor on the last month-end strictly before the
        # start month. The first monthly return is then start_month_close /
        # anchor_close - 1, which is the natural return for start_ts's month.
        anchor_date = all_month_ends.index[prior_mask][-1]
        anchor_val = all_month_ends.loc[anchor_date]
    else:
        # Inception case: no prior month-end exists. Use the first daily value
        # in range as a synthetic anchor so the start month's partial-month
        # return isn't lost.
        s_in_range = s_full[(s_full.index >= start_ts) & (s_full.index <= end_ts)]
        if len(s_in_range) == 0:
            return {}
        anchor_date = s_in_range.index[0]
        anchor_val = s_in_range.iloc[0]

    in_range = (all_month_ends.index >= start_month_begin) & (all_month_ends.index <= end_ts)
    month_ends_in_range = all_month_ends[in_range]

    # Skip an in-range month-end if it equals the synthetic anchor date (rare,
    # but possible if inception happened to fall on a month-end).
    if not prior_mask.any():
        month_ends_in_range = month_ends_in_range[month_ends_in_range.index > anchor_date]

    anchor_series = pd.Series([anchor_val], index=[anchor_date])
    monthly_values = pd.concat([anchor_series, month_ends_in_range])

    if len(monthly_values) < 2:
        return {}

    monthly_returns = monthly_values.pct_change().dropna()
    if len(monthly_returns) == 0:
        return {}

    # Total return measured against the literal end of the selected range, not
    # the last calendar month-end. The monthly resample above captures only
    # complete calendar months, so when end_ts falls mid-month (the typical
    # case when `data through` is May 15 and the May month-end label is May
    # 31), the monthly cumulative product stops at the prior month-end and
    # underreports the period's return. The other charts (Performance
    # Comparison, Portfolio Growth, Total Return Comparison) all measure
    # against end_ts directly, so the summary table needs to as well or its
    # Total Return and Growth of $10,000 will not tie to them.
    daily_in_range = s_full[(s_full.index >= anchor_date) & (s_full.index <= end_ts)]
    if len(daily_in_range) >= 2:
        end_val = float(daily_in_range.iloc[-1])
        total_return = end_val / float(anchor_val) - 1.0
        days_elapsed = (daily_in_range.index[-1] - anchor_date).days
        n_years = days_elapsed / 365.25 if days_elapsed > 0 else len(monthly_returns) / 12.0
    else:
        # Fallback to the legacy monthly-cumprod calculation if no daily
        # values exist in range (should not happen with valid inputs).
        total_return = (1 + monthly_returns).prod() - 1
        n_years = len(monthly_returns) / 12.0

    cagr = (1 + total_return) ** (1.0 / n_years) - 1.0 if n_years > 0 else 0.0
    ann_vol = monthly_returns.std() * np.sqrt(12)

    # Risk-free rate handling
    if rf_monthly is not None and len(rf_monthly) > 0:
        rf_aligned = rf_monthly.reindex(monthly_returns.index).fillna(0)
        excess = monthly_returns - rf_aligned
        rf_annual = (1 + rf_aligned).prod() ** (12.0 / len(rf_aligned)) - 1.0 if len(rf_aligned) > 0 else 0.0
    else:
        excess = monthly_returns
        rf_annual = 0.0

    excess_downside = np.minimum(excess.values, 0.0)
    downside_var = np.mean(excess_downside ** 2)
    downside_dev = np.sqrt(downside_var) * np.sqrt(12)
    sortino = (cagr - rf_annual) / downside_dev if downside_dev > 0 else 0.0

    # Max drawdown (monthly basis)
    wealth = (1 + monthly_returns).cumprod()
    peak = wealth.cummax()
    drawdown = (wealth - peak) / peak
    max_dd = drawdown.min()
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0.0

    # ---- Daily and weekly metrics over user's literal range ----
    # Day and week extremes come from the daily reconstruction within the
    # selected range. For AsymEdge these are approximations (the daily shape
    # is from a close-only reconstruction anchored to Fidelity's monthly
    # returns), the same caveat that applies to Max DD (Daily). Each extreme
    # also records the date it occurred so the table can show it.
    daily_segment = s_full[(s_full.index >= start_ts) & (s_full.index <= end_ts)]
    worst_day = best_day = np.nan
    worst_day_date = best_day_date = None
    worst_week = best_week = np.nan
    worst_week_date = best_week_date = None
    if len(daily_segment) >= 2:
        daily_peak = daily_segment.cummax()
        daily_drawdown = (daily_segment - daily_peak) / daily_peak
        max_dd_daily = daily_drawdown.min()
        daily_pct = daily_segment.pct_change().dropna()
        if len(daily_pct) > 0:
            worst_day = daily_pct.min()
            best_day = daily_pct.max()
            worst_day_date = daily_pct.idxmin()
            best_day_date = daily_pct.idxmax()
        # Weekly returns from week-ending (Friday) closes within the segment.
        weekly_vals = daily_segment.resample('W-FRI').last().dropna()
        weekly_pct = weekly_vals.pct_change().dropna()
        if len(weekly_pct) > 0:
            worst_week = weekly_pct.min()
            best_week = weekly_pct.max()
            worst_week_date = weekly_pct.idxmin()
            best_week_date = weekly_pct.idxmax()
    else:
        max_dd_daily = np.nan

    # Best/Worst Year (only years with at least 6 months of data)
    r_copy = monthly_returns.copy()
    r_copy.index = pd.to_datetime(r_copy.index)
    yearly = (1 + r_copy).resample("YE").prod() - 1
    months_per_year = r_copy.resample("YE").count()
    full_years = yearly[months_per_year >= 6]
    best_year = full_years.max() if len(full_years) > 0 else np.nan
    worst_year = full_years.min() if len(full_years) > 0 else np.nan

    win_rate = (monthly_returns > 0).sum() / len(monthly_returns)

    # Best/Worst Month from the anchored monthly returns. For AsymEdge these
    # tie to Fidelity's reported monthly time-weighted returns, so unlike the
    # daily/weekly extremes they are exact rather than approximations. The
    # index is month-end timestamps, so the recorded date labels the month.
    if len(monthly_returns) > 0:
        worst_month = monthly_returns.min()
        best_month = monthly_returns.max()
        worst_month_date = monthly_returns.idxmin()
        best_month_date = monthly_returns.idxmax()
    else:
        worst_month = best_month = np.nan
        worst_month_date = best_month_date = None

    period_label = (
        f"{start_ts.month}/{start_ts.day}/{start_ts.year} to "
        f"{end_ts.month}/{end_ts.day}/{end_ts.year}"
    )

    return {
        "Period": period_label,
        "Sortino Ratio": sortino,
        "CAGR": cagr,
        "Max Drawdown": max_dd,
        "Max Drawdown (Daily)": max_dd_daily,
        "Worst Day": worst_day,
        "Worst Day Date": worst_day_date,
        "Best Day": best_day,
        "Best Day Date": best_day_date,
        "Worst Week": worst_week,
        "Worst Week Date": worst_week_date,
        "Best Week": best_week,
        "Best Week Date": best_week_date,
        "Worst Month": worst_month,
        "Worst Month Date": worst_month_date,
        "Best Month": best_month,
        "Best Month Date": best_month_date,
        "Calmar Ratio": calmar,
        "Annualized Vol": ann_vol,
        "Downside Dev": downside_dev,
        "Risk-Free Annual": rf_annual,
        "Best Year": best_year,
        "Worst Year": worst_year,
        "Win Rate": win_rate,
        "Total Return": total_return,
        "Growth of $10,000": 10000 * (1 + total_return),
    }


def get_period_dates(latest_date, period_key, inception_date=None):
    end = pd.Timestamp(latest_date)
    if period_key == "YTD":
        start = pd.Timestamp(f"{end.year - 1}-12-31")
    elif period_key == "MTD":
        start = pd.Timestamp(f"{end.year}-{end.month:02d}-01") - timedelta(days=1)
    elif period_key == "1M":
        start = end - timedelta(days=30)
    elif period_key == "3M":
        start = end - timedelta(days=91)
    elif period_key == "6M":
        start = end - timedelta(days=182)
    elif period_key == "1Y":
        start = end - timedelta(days=365)
    elif period_key == "2024":
        start = pd.Timestamp("2023-12-31")
        end = pd.Timestamp("2024-12-31")
    elif period_key == "2025":
        start = pd.Timestamp("2024-12-31")
        end = min(end, pd.Timestamp("2025-12-31"))
    elif period_key == "Inception":
        start = pd.Timestamp(inception_date)
    else:
        start = pd.Timestamp(inception_date) if inception_date else end - timedelta(days=365)
    return start, end


def make_x_axis_labels(start_date, end_date):
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    span_days = (end - start).days
    dates = [start + timedelta(days=int(i * span_days / 6)) for i in range(7)]
    if span_days < 180:
        fmt = "%b %d"
    else:
        fmt = "%b '%y"
    return dates, [d.strftime(fmt) for d in dates]


# ---------- Chart builders ----------

def build_performance_chart(bar_df, series_names):
    fig = go.Figure()
    for name in series_names:
        subset = bar_df[bar_df["Series"] == name]
        fig.add_trace(go.Bar(
            x=subset["Period"],
            y=subset["Return"],
            name=series_label(name),
            marker=dict(
                color=BAR_SERIES_COLORS.get(name, "#999"),
                cornerradius=6,
            ),
            text=[f"{v:.1f}%" for v in subset["Return"]],
            textposition="outside",
            textfont=dict(size=14, color=TEXT_SECONDARY),
            cliponaxis=False,
        ))
    fig.update_layout(
        **DARK_LAYOUT,
        barmode="group",
        yaxis=dict(
            ticksuffix="%",
            gridcolor=GRID_COLOR,
            zeroline=True,
            zerolinecolor=ZERO_LINE,
            tickfont=dict(size=16, color=TEXT_MUTED),
        ),
        xaxis=dict(type="category", tickfont=dict(size=16, color=TEXT_SECONDARY, weight=700)),
        legend=dict(
            orientation="h", yanchor="top", y=-0.16,
            xanchor="center", x=0.5,
            font=dict(size=16, color=TEXT_SECONDARY, weight=500),
        ),
        margin=dict(t=30, b=80, l=50, r=30),
        height=430,
        bargap=0.28,
        bargroupgap=0.10,
        uniformtext=dict(mode="show", minsize=14),
    )
    return fig


def build_growth_chart(combined, series_names, start_g, end_g):
    fig = go.Figure()
    tick_dates, tick_labels = make_x_axis_labels(start_g, end_g)
    legend_items = []

    for name in series_names:
        if name not in combined.columns:
            continue
        s = combined[name].dropna()
        mask = (s.index >= start_g) & (s.index <= end_g)
        segment = s[mask]
        if len(segment) == 0:
            continue

        first_val = segment.iloc[0]
        normed = segment / first_val * 10000
        final_val = normed.iloc[-1]
        pct_return = (final_val - 10000) / 10000 * 100

        opacity = SERIES_OPACITY.get(name, 1.0)
        hex_color = SERIES_COLORS.get(name, "#999")
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        rgba = f"rgba({r},{g},{b},{opacity})"

        legend_items.append({
            "name": series_label(name),
            "value": final_val,
            "pct": pct_return,
            "color": rgba,
            "value_text": f"${final_val:,.0f} ({pct_return:.1f}%)",
        })

        fig.add_trace(go.Scatter(
            x=normed.index,
            y=normed.values,
            mode="lines",
            name=series_label(name),
            line=dict(color=rgba, width=4 if name == "AsymEdge" else 3),
            hovertemplate="%{x|%b %d, %Y}<br>$%{y:,.0f}<extra>" + series_label(name) + "</extra>",
            showlegend=False,
        ))

    # Reverse trace order so the series listed first in SERIES_ORDER renders
    # on top. Plotly draws traces in order (later additions paint over earlier
    # ones), so reversing fig.data here puts Asymmetric Edge last in the draw
    # order, which means it sits visually in front of every other line.
    fig.data = fig.data[::-1]

    # Build a two-row in-chart legend. The square marker is drawn as a Plotly
    # path shape using xsizemode/ysizemode="pixel", which guarantees a true
    # pixel-square marker regardless of the chart's actual rendered width.
    # The marker has a small rounded-corner radius for a softened look.
    # Layout uses pixel arithmetic for spacing, then converts to paper
    # coordinates only for positioning, so the visual gaps between items
    # stay even regardless of label length. Value text on the bottom row is
    # centered under the corresponding series name's center (not the full
    # square + name block).
    legend_shapes = []
    legend_annotations = []
    n_items = len(legend_items)
    if n_items > 0:
        SQ_PX = 14                # square marker side length, pixels
        SQ_HALF = SQ_PX / 2
        CORNER_PX = 3             # rounded corner radius, pixels
        SQ_GAP_PX = 9             # space between marker and series name
        ITEM_GAP_PX = 56          # space between adjacent legend items
        FIG_W_PX = 790            # chart width in Tyler's Firefox (about 795 px content column)
        NAME_CHAR_PX = 8.9        # 16pt DM Sans medium, average char width
        VALUE_CHAR_PX = 7.1       # 13pt DM Sans regular, average char width

        # Vertical positions in paper-y. y_name is further from the plot
        # than the prior version to leave a comfortable gap between the
        # x-axis date labels and the legend.
        y_name = -0.15
        y_value = -0.205

        # Path for the rounded square in pixel coords centered on (0, 0).
        # Used with xsizemode/ysizemode="pixel" so the marker is exactly
        # 14x14 pixels no matter how wide the chart renders.
        h, r = SQ_HALF, CORNER_PX
        sq_path = (
            f"M {-h+r},{-h} L {h-r},{-h} "
            f"Q {h},{-h} {h},{-h+r} L {h},{h-r} "
            f"Q {h},{h} {h-r},{h} L {-h+r},{h} "
            f"Q {-h},{h} {-h},{h-r} L {-h},{-h+r} "
            f"Q {-h},{-h} {-h+r},{-h} Z"
        )

        # Measure each item in pixels. The value text is centered under the
        # name's horizontal center, so for short names (like "60/40") the
        # value can overhang the [square + name] block on either side. The
        # item's visual bounds account for that overhang so adjacent items
        # don't collide.
        def measure(item):
            name_px = len(item["name"]) * NAME_CHAR_PX
            val_px = len(item["value_text"]) * VALUE_CHAR_PX
            # Name center, measured from the square's left edge
            name_center_offset = SQ_PX + SQ_GAP_PX + name_px / 2
            val_left = name_center_offset - val_px / 2
            val_right = name_center_offset + val_px / 2
            top_w_px = SQ_PX + SQ_GAP_PX + name_px
            left_bound = min(0, val_left)
            right_bound = max(top_w_px, val_right)
            return {
                "name_px": name_px,
                "name_center_offset": name_center_offset,
                "left_bound": left_bound,
                "right_bound": right_bound,
                "item_w_px": right_bound - left_bound,
            }

        geoms = [measure(it) for it in legend_items]
        total_w_px = sum(g["item_w_px"] for g in geoms) + (n_items - 1) * ITEM_GAP_PX
        start_x = 0.5 - (total_w_px / FIG_W_PX) / 2

        cursor = start_x
        for i, item in enumerate(legend_items):
            g = geoms[i]
            # If the value text overhangs the square's left edge (which
            # happens for short names like "60/40"), shift the square right
            # within the item slot so the value still fits in bounds.
            sq_shift_px = -g["left_bound"]   # >= 0
            sq_center_x = cursor + (sq_shift_px + SQ_HALF) / FIG_W_PX
            name_x = sq_center_x + (SQ_HALF + SQ_GAP_PX) / FIG_W_PX
            name_center_x = sq_center_x + (SQ_HALF + SQ_GAP_PX + g["name_px"] / 2) / FIG_W_PX

            # Rounded square marker, pixel-sized
            legend_shapes.append(dict(
                type="path", path=sq_path,
                xref="paper", yref="paper",
                xanchor=sq_center_x, yanchor=y_name,
                xsizemode="pixel", ysizemode="pixel",
                fillcolor=item["color"],
                line=dict(width=0),
            ))
            # Series name, left-anchored just to the right of the square
            legend_annotations.append(dict(
                xref="paper", yref="paper",
                x=name_x, y=y_name,
                text=item["name"],
                showarrow=False,
                font=dict(size=16, color=TEXT_SECONDARY,
                          family="DM Sans, sans-serif", weight=500),
                xanchor="left", yanchor="middle",
            ))
            # Value + percentage, centered horizontally under the name's center
            legend_annotations.append(dict(
                xref="paper", yref="paper",
                x=name_center_x, y=y_value,
                text=item["value_text"],
                showarrow=False,
                font=dict(size=13, color=TEXT_MUTED,
                          family="DM Sans, sans-serif"),
                xanchor="center", yanchor="middle",
            ))

            cursor += (g["item_w_px"] + ITEM_GAP_PX) / FIG_W_PX

    fig.update_layout(
        **DARK_LAYOUT,
        yaxis=dict(
            tickprefix="$", tickformat=",",
            gridcolor=GRID_COLOR,
            zeroline=False,
            tickfont=dict(size=16, color=TEXT_MUTED),
        ),
        xaxis=dict(
            tickmode="array",
            tickvals=tick_dates,
            ticktext=tick_labels,
            gridcolor="rgba(0,0,0,0)",
            tickfont=dict(size=16, color=TEXT_MUTED),
            range=[start_g - timedelta(days=2), end_g + timedelta(days=2)],
        ),
        margin=dict(t=15, b=125, l=70, r=30),
        height=560,
        hovermode="x unified",
        shapes=legend_shapes,
        annotations=legend_annotations,
    )
    return fig, legend_items


def build_drawdown_chart(bar_df, series_names):
    fig = go.Figure()
    for name in series_names:
        subset = bar_df[bar_df["Series"] == name]
        fig.add_trace(go.Bar(
            x=subset["Period"],
            y=subset["Drawdown"],
            name=series_label(name),
            marker=dict(
                color=BAR_SERIES_COLORS.get(name, "#999"),
                cornerradius=6,
            ),
            text=[f"{v:.1f}%" for v in subset["Drawdown"]],
            textposition="outside",
            textfont=dict(size=14, color=TEXT_SECONDARY),
            cliponaxis=False,
        ))
    fig.update_layout(
        **DARK_LAYOUT,
        barmode="group",
        yaxis=dict(
            ticksuffix="%",
            gridcolor=GRID_COLOR,
            zeroline=True,
            zerolinecolor=ZERO_LINE,
            tickfont=dict(size=16, color=TEXT_MUTED),
        ),
        xaxis=dict(type="category", tickfont=dict(size=16, color=TEXT_SECONDARY, weight=700)),
        legend=dict(
            orientation="h", yanchor="top", y=-0.16,
            xanchor="center", x=0.5,
            font=dict(size=16, color=TEXT_SECONDARY, weight=500),
        ),
        margin=dict(t=30, b=80, l=55, r=30),
        height=430,
        bargap=0.28,
        bargroupgap=0.10,
        uniformtext=dict(mode="show", minsize=14),
    )
    return fig


@st.cache_data(ttl=3600)
def load_custom_ticker_data(tickers_tuple, start_date: str, end_date: str):
    """Fetch adjusted close prices for a list of custom tickers."""
    tickers = list(tickers_tuple)
    if not tickers:
        return pd.DataFrame()
    return _fetch_closes(tickers, start_date, end_date)


def build_total_return_chart(series_dict, start_date, end_date, color_map):
    """
    Build a percentage-return line chart.
    series_dict: {label: pd.Series of prices}
    Returns a Plotly figure.
    """
    fig = go.Figure()
    tick_dates, tick_labels = make_x_axis_labels(start_date, end_date)
    annotations = []

    for i, (label, prices) in enumerate(series_dict.items()):
        s = prices.dropna()
        mask = (s.index >= pd.Timestamp(start_date)) & (s.index <= pd.Timestamp(end_date))
        segment = s[mask]
        if len(segment) < 2:
            continue

        first_val = segment.iloc[0]
        pct_return = (segment / first_val - 1) * 100

        color = color_map.get(label, "#999999")

        fig.add_trace(go.Scatter(
            x=pct_return.index,
            y=pct_return.values,
            mode="lines",
            name=label,
            line=dict(color=color, width=3),
            hovertemplate="%{x|%b %d, %Y}<br>%{y:+.2f}%<extra>" + label + "</extra>",
            showlegend=True,
            legendrank=i,
        ))

        # End-of-line annotation with final return value
        final_val = pct_return.iloc[-1]
        annotations.append(dict(
            x=pct_return.index[-1],
            y=final_val,
            text=f"<b>{final_val:+.2f}%</b>",
            showarrow=False,
            xanchor="left",
            xshift=8,
            font=dict(size=16, color=color, family="DM Sans, sans-serif"),
        ))

    # Reverse trace draw order so the first series in series_dict (typically
    # Asymmetric Edge) renders on top. The legendrank values set in the loop
    # above preserve the original ordering in the on-screen legend.
    fig.data = fig.data[::-1]

    fig.update_layout(
        **DARK_LAYOUT,
        yaxis=dict(
            ticksuffix="%",
            gridcolor=GRID_COLOR,
            zeroline=True,
            zerolinecolor=ZERO_LINE,
            zerolinewidth=1,
            tickfont=dict(size=16, color=TEXT_MUTED),
        ),
        xaxis=dict(
            tickmode="array",
            tickvals=tick_dates,
            ticktext=tick_labels,
            gridcolor="rgba(0,0,0,0)",
            tickfont=dict(size=16, color=TEXT_MUTED),
            range=[pd.Timestamp(start_date) - timedelta(days=2), pd.Timestamp(end_date) + timedelta(days=2)],
        ),
        legend=dict(
            orientation="h", yanchor="top", y=-0.14,
            xanchor="center", x=0.5,
            font=dict(size=22, color=TEXT_SECONDARY, weight=500),
        ),
        margin=dict(t=15, b=70, l=60, r=80),
        height=460,
        hovermode="x unified",
        showlegend=True,
        annotations=annotations,
    )
    return fig


def build_asset_class_chart(returns_dict, periods=None, selected_period=None):
    """Build the asset class horizontal bar chart.

    periods / selected_period: optional. When provided, a row of pill-style
    badges is rendered at the top of the figure (in the top-margin space)
    so the PNG export from Plotly's toolbar captures which time period the
    chart represents. The badges are visual only; the actual period
    selection still happens via the Streamlit pills above the chart.
    """
    sorted_items = sorted(returns_dict.items(), key=lambda x: x[1], reverse=True)
    names = [item[0] for item in sorted_items]
    values = [item[1] for item in sorted_items]
    colors = [GAIN_GREEN if v >= 0 else LOSS_RED for v in values]

    abs_values = [abs(v) for v in values]
    max_abs = max(abs_values) if abs_values else 1
    threshold = max_abs * 0.30

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=names,
        x=values,
        orientation="h",
        marker=dict(
            color=colors,
            cornerradius=5,
        ),
        cliponaxis=False,
        showlegend=False,
        hovertemplate="<b>%{y}</b><br>%{x:+.2f}%<extra></extra>",
    ))

    # Use manual annotations for full control over label placement.
    # Key fix: for a negative bar, Plotly's built-in "outside" position
    # places the label further to the LEFT of the bar tip, which collides
    # with the y-axis category label. Instead, for small negative bars we
    # place the label just to the right of the zero line (in the empty
    # positive area of that row).
    annotations = []
    for name, value in zip(names, values):
        text = f"<b>{value:+.2f}%</b>"
        fits_inside = abs(value) > threshold

        if value >= 0:
            if fits_inside:
                # Large positive: inside bar, anchored at right tip, white text
                annotations.append(dict(
                    x=value, y=name,
                    text=text,
                    showarrow=False,
                    xanchor="right",
                    xshift=-8,
                    font=dict(size=14, color="#ffffff"),
                ))
            else:
                # Small positive: just outside right of the bar tip
                annotations.append(dict(
                    x=value, y=name,
                    text=text,
                    showarrow=False,
                    xanchor="left",
                    xshift=6,
                    font=dict(size=14, color=TEXT_SECONDARY),
                ))
        else:
            if fits_inside:
                # Large negative: inside bar, anchored at left tip, white text
                annotations.append(dict(
                    x=value, y=name,
                    text=text,
                    showarrow=False,
                    xanchor="left",
                    xshift=8,
                    font=dict(size=14, color="#ffffff"),
                ))
            else:
                # Small negative: place label just to the right of the zero
                # line so it never collides with the y-axis category label.
                annotations.append(dict(
                    x=0, y=name,
                    text=text,
                    showarrow=False,
                    xanchor="left",
                    xshift=6,
                    font=dict(size=14, color=TEXT_SECONDARY),
                ))

    # Period badges in the top margin. Rendered as Plotly annotations so they
    # become part of the figure and are included in the PNG download. The
    # selected period mimics the Streamlit pill's active style (light purple
    # background, brand-purple border and text); the others use a muted
    # outline style. Positions are in paper coordinates so they hold their
    # place regardless of container width.
    if periods:
        badge_centers_x = [0.04, 0.14, 0.24, 0.34, 0.44, 0.54, 0.64, 0.74]
        for i, period in enumerate(periods):
            if i >= len(badge_centers_x):
                break
            is_selected = (period == selected_period)
            if is_selected:
                bg = "#f0edf8"
                border = BRAND_PURPLE
                txt_color = BRAND_PURPLE
                font_weight = 700
            else:
                bg = "#ffffff"
                border = "#dddddd"
                txt_color = TEXT_MUTED
                font_weight = 500
            annotations.append(dict(
                x=badge_centers_x[i], y=1.06,
                xref="paper", yref="paper",
                text=period,
                showarrow=False,
                bgcolor=bg,
                bordercolor=border,
                borderwidth=1,
                borderpad=7,
                font=dict(
                    size=13,
                    color=txt_color,
                    family="DM Sans, sans-serif",
                    weight=font_weight,
                ),
                xanchor="center", yanchor="middle",
            ))

    fig.update_layout(
        **DARK_LAYOUT,
        yaxis=dict(
            autorange="reversed",
            tickfont=dict(size=20, color=TEXT_PRIMARY, weight=600),
            showgrid=False,
        ),
        xaxis=dict(
            showticklabels=False,
            showgrid=False,
            zeroline=True,
            zerolinecolor=ZERO_LINE,
            zerolinewidth=1,
        ),
        margin=dict(t=60 if periods else 10, b=15, l=140, r=85),
        height=max(440, len(names) * 52) + (50 if periods else 0),
        showlegend=False,
        annotations=annotations,
    )
    return fig


def build_summary_table_html(metrics_by_series, series_order):
    """Build an HTML performance summary table styled to match the dashboard.

    metrics_by_series: {series_name: metrics_dict_from_compute_summary_metrics}
    series_order: list of series names in the desired column order
    """

    def _is_num(v):
        return isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v))

    def fmt_pct(v):
        return f"{v:.2%}" if _is_num(v) else "N/A"

    def fmt_ratio(v):
        return f"{v:.2f}" if _is_num(v) else "N/A"

    def fmt_dollar(v):
        return f"${v:,.0f}" if _is_num(v) else "N/A"

    def fmt_text(v):
        return v if isinstance(v, str) and v else "N/A"

    # Date-of-occurrence formatters. Each returns (inline_text, tooltip_text).
    # Days are not zero-padded (e.g. 'Mar 5, 2025'); cross-platform safe.
    def _fmt_day(ts):
        ts = pd.Timestamp(ts)
        d = f"{ts.strftime('%b')} {ts.day}, {ts.year}"
        return d, d

    def _fmt_week(ts):
        ts = pd.Timestamp(ts)
        d = f"{ts.strftime('%b')} {ts.day}, {ts.year}"
        return d, f"Week ending {d}"

    def _fmt_month(ts):
        ts = pd.Timestamp(ts)
        return ts.strftime("%b %Y"), ts.strftime("%B %Y")

    date_fmt_by_kind = {"day": _fmt_day, "week": _fmt_week, "month": _fmt_month}

    # (display_name, value_key, formatter, is_bold, date_key, date_kind)
    # date_key/date_kind are None for rows without an occurrence date. When
    # present, the cell shows the value with the date of occurrence beneath it
    # (and as a hover tooltip).
    rows = [
        ("Sortino Ratio",      "Sortino Ratio",        fmt_ratio,  True,  None,               None),
        ("CAGR",               "CAGR",                 fmt_pct,    True,  None,               None),
        ("Max Drawdown",       "Max Drawdown",         fmt_pct,    True,  None,               None),
        ("Max DD (Daily)",     "Max Drawdown (Daily)", fmt_pct,    True,  None,               None),
        ("Worst Single Day",   "Worst Day",            fmt_pct,    False, "Worst Day Date",   "day"),
        ("Best Single Day",    "Best Day",             fmt_pct,    False, "Best Day Date",    "day"),
        ("Worst Week",         "Worst Week",           fmt_pct,    False, "Worst Week Date",  "week"),
        ("Best Week",          "Best Week",            fmt_pct,    False, "Best Week Date",   "week"),
        ("Worst Month",        "Worst Month",          fmt_pct,    False, "Worst Month Date", "month"),
        ("Best Month",         "Best Month",           fmt_pct,    False, "Best Month Date",  "month"),
        ("Calmar Ratio",       "Calmar Ratio",         fmt_ratio,  False, None,               None),
        ("Annualized Vol",     "Annualized Vol",       fmt_pct,    False, None,               None),
        ("Best Year",          "Best Year",            fmt_pct,    False, None,               None),
        ("Worst Year",         "Worst Year",           fmt_pct,    False, None,               None),
        ("Win Rate",           "Win Rate",             fmt_pct,    False, None,               None),
        ("Total Return",       "Total Return",         fmt_pct,    False, None,               None),
        ("Growth of $10,000",  "Growth of $10,000",    fmt_dollar, False, None,               None),
        ("Period",             "Period",               fmt_text,   False, None,               None),
    ]

    header_cells = "".join(f"<th>{series_label(name)}</th>" for name in series_order)

    css = f"""
    <style>
    .perf-summary-table {{
        width: 100%;
        border-collapse: collapse;
        font-family: 'DM Sans', sans-serif;
        font-size: 14px;
        color: {TEXT_PRIMARY};
        margin: 0.5rem 0 1rem 0;
    }}
    .perf-summary-table thead th {{
        text-align: right;
        padding: 12px 14px;
        border-bottom: 2px solid {BRAND_PURPLE};
        background-color: #fafafa;
        font-weight: 600;
        font-size: 13px;
        color: {TEXT_PRIMARY};
        letter-spacing: 0.01em;
    }}
    .perf-summary-table thead th:first-child {{
        text-align: left;
    }}
    .perf-summary-table tbody td {{
        padding: 9px 14px;
        border-bottom: 1px solid #eeeeee;
        text-align: right;
        font-variant-numeric: tabular-nums;
    }}
    .perf-summary-table tbody td.metric-col {{
        text-align: left;
        color: {TEXT_SECONDARY};
        font-weight: 500;
    }}
    .perf-summary-table tbody tr:hover {{
        background-color: #f7f5fb;
    }}
    .perf-summary-table tbody tr.bold-row td {{
        font-weight: 700;
        color: {TEXT_PRIMARY};
    }}
    .perf-summary-table tbody tr.bold-row td.metric-col {{
        color: {TEXT_PRIMARY};
    }}
    /* Date of occurrence shown beneath an extreme value */
    .perf-summary-table tbody td .cell-date {{
        display: block;
        font-size: 11px;
        font-weight: 400;
        color: {TEXT_MUTED};
        margin-top: 2px;
        letter-spacing: 0.01em;
    }}
    .perf-summary-table tbody tr.bold-row td .cell-date {{
        font-weight: 400;
        color: {TEXT_MUTED};
    }}
    .perf-summary-table tbody td.has-date {{
        cursor: help;
    }}
    </style>
    """

    html_parts = [
        css,
        '<table class="perf-summary-table">',
        f'<thead><tr><th>Metric</th>{header_cells}</tr></thead>',
        '<tbody>',
    ]

    for display_name, key, fmt, is_bold, date_key, date_kind in rows:
        row_class = ' class="bold-row"' if is_bold else ""
        cells = []
        for s in series_order:
            m = metrics_by_series.get(s, {})
            if not m:
                cells.append("<td>N/A</td>")
                continue
            val_str = fmt(m.get(key))
            dt = m.get(date_key) if date_key else None
            has_dt = dt is not None and not (isinstance(dt, float) and np.isnan(dt))
            if has_dt:
                inline, tip = date_fmt_by_kind[date_kind](dt)
                cells.append(
                    f'<td class="has-date" title="{tip}">{val_str}'
                    f'<span class="cell-date">{inline}</span></td>'
                )
            else:
                cells.append(f"<td>{val_str}</td>")
        html_parts.append(
            f'<tr{row_class}><td class="metric-col">{display_name}</td>{"".join(cells)}</tr>'
        )

    html_parts.append('</tbody></table>')
    return "\n".join(html_parts)


# ---------- Allocation table ----------
# There is intentionally NO hardcoded current-allocation fallback. The Current
# Allocation table and Live Position Drift derive their weights from
# holdings_daily_values.csv at the most recent rebalance (see
# derive_current_allocation). If that data is missing, the dashboard shows an
# error instead of stale, hand-typed numbers.


def _pct1(value, signed=False):
    """Format a percent value for the allocation tables: one decimal place.

    Display only. The underlying weights stay at full precision (and the
    Current Allocation row strings stay at two decimals, because
    current_allocation_weights() parses them back into the weights that
    extend_reconstruction_via_yahoo uses). A value that rounds to zero prints
    as 0.0% with no sign, never -0.0% or +0.0%.
    """
    r = round(float(value), 1)
    if r == 0:
        r = 0.0
    text = f"{r:.1f}%"
    return "+" + text if signed and r > 0 else text


def _pct1_str(weight_str):
    """Reformat a stored weight string such as '21.49%' to one decimal."""
    try:
        return _pct1(str(weight_str).replace("%", "").strip())
    except (ValueError, TypeError):
        return weight_str


def build_allocation_table(rows):
    """Build a Plotly table figure for the current allocation so it can be
    exported as PNG via the toolbar download button.

    rows is the auto-derived current allocation (from actual holdings at the
    most recent rebalance). There is no hardcoded fallback, callers invoke this
    only when rows is available. Rows are listed largest weight first.
    """
    rows = sort_rows_by_weight(rows)
    header_values = ["Asset", "Ticker", "Weight", "Purpose"]
    assets = [f'{row["emoji"]}  {row["asset"]}' for row in rows]
    tickers = [row["ticker"] for row in rows]
    # Round from the full-precision weight_pct when present, exactly as the
    # Allocation Drift table's Month Start column does. Rounding the stored
    # two-decimal string a second time can land 0.1 off (33.847 -> 33.85 ->
    # 33.9 instead of 33.8).
    weights = [
        _pct1(row["weight_pct"]) if "weight_pct" in row else _pct1_str(row["weight"])
        for row in rows
    ]
    purposes = [row["purpose"] for row in rows]

    # Alternating row fills for readability
    n = len(rows)
    row_fills = ["#F9FAFB" if i % 2 == 1 else "#ffffff" for i in range(n)]

    fig = go.Figure(data=[go.Table(
        columnwidth=[220, 70, 80, 320],
        header=dict(
            values=[f"<b>{v}</b>" for v in header_values],
            fill_color="#F9FAFB",
            line_color="#E5E7EB",
            align=["left", "left", "right", "left"],
            font=dict(family="DM Sans, sans-serif", size=17, color=TEXT_PRIMARY),
            height=38,
        ),
        cells=dict(
            values=[assets, tickers, weights, purposes],
            fill_color=[row_fills],
            line_color="#E5E7EB",
            align=["left", "left", "right", "left"],
            font=dict(family="DM Sans, sans-serif", size=16, color=TEXT_PRIMARY),
            height=38,
        ),
    )])

    fig.update_layout(
        **DARK_LAYOUT,
        margin=dict(t=2, b=2, l=2, r=2),
        height=38 + 38 * n + 10,
        width=790,
    )
    return fig


# ---------- Asset catalog (for auto-populating allocation tables) ----------
# Maps ticker -> display name, emoji, and purpose. Used by the Next Allocation
# editor so that selecting a ticker auto-fills the other columns.
#
# The INSERTION ORDER of this dict is the canonical order: assets grouped by
# category, matching asset_universe.json (U.S. equities, then International,
# then Commodities, then Crypto, then Defensive). The allocation tables list
# their rows largest weight first (see weight_order) and use this order only
# to break exact ties. To add a new asset, insert it in the slot for its
# category.
ASSET_CATALOG = {
    # U.S. equities
    "QQQ":  {"asset": "Nasdaq-100",              "emoji": "\U0001F4BB", "purpose": "Growth via U.S. tech stocks"},
    "IWM":  {"asset": "Russell 2000",            "emoji": "\U0001F537", "purpose": "Upside from U.S. economic expansion"},
    # International
    "EMXC": {"asset": "Emerging Mkts",           "emoji": "\U0001F30F", "purpose": "Emerging-economy growth, ex-China"},
    "DXJ":  {"asset": "Japan",                   "emoji": "\u26E9\uFE0F", "purpose": "Developed-market growth, no yen risk"},
    # Commodities
    "GLD":  {"asset": "Gold",                    "emoji": "\U0001F7E8", "purpose": "Crisis hedge, store of value"},
    "HGER": {"asset": "Broad Commodities",      "emoji": "\U0001F3ED", "purpose": "Hedge against inflation and price spikes"},
    # Crypto
    "IBIT": {"asset": "Bitcoin",                 "emoji": "\U0001F7E0", "purpose": "High-upside, fixed-supply digital asset"},
    # Defensive
    "BIL":  {"asset": "Short-Term Treasuries",   "emoji": "\U0001F4B5", "purpose": "Cash reserve when risk assets weaken"},
    "TLT":  {"asset": "Long-Term Treasuries",    "emoji": "\U0001F3E6", "purpose": "Recession and falling-rate hedge"},
    "BTAL": {"asset": "Defensive Equity",        "emoji": "\U0001F6E1\uFE0F", "purpose": "Hedge against stock market sell-offs"},
}


def canonical_order(tickers):
    """Sort tickers by ASSET_CATALOG insertion order.

    Unknown tickers appear at the end in alphabetical order. The allocation
    tables sort largest weight first (weight_order) and fall back to this
    category-grouped order only to break exact ties.
    """
    catalog = list(ASSET_CATALOG.keys())
    known = [t for t in catalog if t in tickers]
    unknown = sorted([t for t in tickers if t not in catalog])
    return known + unknown


def _sort_weight(value):
    """Coerce a weight to a float for sorting. Missing, unparseable, or NaN
    values sort as zero so a bad cell can never break the table order."""
    try:
        v = float(str(value).replace("%", "").strip())
    except (ValueError, TypeError):
        return 0.0
    return 0.0 if v != v else v


def weight_order(weights, tiebreak=None):
    """Return the tickers in weights ordered largest weight first.

    This is the row order for every allocation table on the dashboard
    (Current Allocation, Live Position Drift, Next Allocation, Allocation
    Drift). weights maps ticker -> weight in any consistent unit. Exact ties
    fall back to tiebreak (ticker -> weight, larger first) when given, then
    to canonical_order, so the order never shuffles between reruns. Display
    only: no calculation depends on this order.
    """
    canon = {t: i for i, t in enumerate(canonical_order(list(weights)))}
    tiebreak = tiebreak or {}
    return sorted(
        weights,
        key=lambda t: (
            -_sort_weight(weights[t]),
            -_sort_weight(tiebreak.get(t, 0.0)),
            canon[t],
        ),
    )


def sort_rows_by_weight(rows):
    """Sort allocation-row dicts (each with a "ticker" and a weight string
    such as '21.49%') largest weight first, exact ties in canonical order."""
    canon = {t: i for i, t in enumerate(canonical_order([r.get("ticker", "") for r in rows]))}
    return sorted(
        rows,
        key=lambda r: (
            -_sort_weight(r.get("weight_pct", r.get("weight"))),
            canon.get(r.get("ticker", ""), len(canon)),
        ),
    )

NEXT_ALLOC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "next_allocation.json")


# ---------- Asset Allocation Over Time (allocation history chart) ----------
# Groups every ticker the strategy has ever held into a small set of asset
# classes and renders the month-by-month allocation as 100% stacked bars,
# in the spirit of the ARP ETF allocation history chart.
#
# The palette is the "quiet with contrast anchors" scheme: mostly muted
# tones with lightness doing the separating (dark navy vs light steel blue
# for the equity family, amber vs pale gold for the commodity family), so
# the chart reads calmly while adjacent categories stay distinct. Validated
# for colorblind separation (all adjacent stack pairs pass CVD deltaE
# checks, including Crypto's orange against both Gold and Commodities, since
# Crypto sits directly on Commodities in months with no gold). The defensive sleeve and T-bills/cash fade toward gray so
# risk-off periods read as the portfolio "going quiet."
#
# Stack order is bottom-to-top; the legend follows the same order.
ALLOC_HISTORY_START = "2024-01-01"  # strategy inception, published track record start

ALLOC_HISTORY_CATEGORIES = [
    # (key, display label, fill color)
    ("us",     "U.S. Equities",     "#2F4A6E"),  # dark navy anchor
    ("intl",   "International",     "#8FA9C4"),  # light steel blue, same family as US
    ("comm",   "Commodities",       "#B07D45"),  # muted amber
    ("gold",   "Gold",              "#E4D294"),  # pale gold, kept separate from
                                                 # Commodities because it is usually
                                                 # the strategy's largest single sleeve
    ("crypto", "Crypto",            "#F59A3C"),  # bitcoin orange, matching the
                                                 # Asset Universe card and the
                                                 # orange emoji (October 22, 2026)
    ("def",    "Defensive Equity",  "#6E6A62"),  # warm dark gray (BTAL)
    ("cash",   "T-bills & Cash",    "#F0F1F3"),  # near-white, reads as "nothing held"
]

# Ticker -> category key. Covers every ticker held since inception plus the
# rest of the current asset catalog. Extend this map when a new asset joins
# the universe; unmapped tickers fall back to U.S. Equities.
ALLOC_HISTORY_TICKER_CATEGORY = {
    "QQQ": "us", "IWM": "us", "SPY": "us",
    "EMXC": "intl", "DXJ": "intl", "EZU": "intl",
    "HGER": "comm", "COPX": "comm",
    "GLD": "gold",
    "IBIT": "crypto", "GBTC": "crypto", "BITO": "crypto",
    "BTAL": "def",
    "TLT": "def",
    "BIL": "cash", "389930108": "cash",  # 389930108 is a money-market CUSIP
}

# Permanent chart-only corrections for broker execution errors, keyed by the
# rebalance (going-in) date. The bar for the month that rebalance opened
# shows the basket the strategy called for instead of the mis-executed fill.
# Unlike month_start_override.json, which lapses at the next month end and is
# then deleted, these stay in place so the history keeps showing the intended
# basket. Weights are percents and are normalized on use. This NEVER touches
# the return series, which carries the real cost of each error.
ALLOC_HISTORY_EXECUTION_CORRECTIONS = {
    # Fidelity's basket rebalance misfired on Aug 31, 2026. Actual fill was
    # EMXC 9.95 / DXJ 40.73 / HGER 43.10 / IBIT 6.22 until the Sep 8 reset.
    "2026-08-31": {"EMXC": 21.21, "DXJ": 32.69, "HGER": 32.79, "IBIT": 13.31},
}


def _load_reconstructed_totals():
    """Load date-indexed account_value and cash from reconstructed_account_value.csv.

    Used by the allocation history chart so the uninvested cash sleeve can be
    shown alongside the securities. Returns a DataFrame indexed by date with
    'account_value' and 'cash' columns, or None if the file is missing or has
    an unexpected schema (the chart then falls back to securities-only
    weights, which only misses the usually-tiny pure-cash slice).
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pipeline_dir = os.path.join(os.path.dirname(script_dir), "Portfolio Hist Val Reconstruction")
    for path in (
        os.path.join(pipeline_dir, "reconstructed_account_value.csv"),
        os.path.join(script_dir, "reconstructed_account_value.csv"),
    ):
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_csv(path, parse_dates=["date"])
        except Exception:
            return None
        if "account_value" in df.columns and "cash" in df.columns:
            return df.set_index("date").sort_index()[["account_value", "cash"]]
        return None
    return None


def build_allocation_history_figure(holdings_values):
    """Build the Asset Allocation Over Time stacked-bar figure.

    One 100% stacked bar per month showing the portfolio that month was
    entered with (its going-in weights). This matches how the strategy
    trades: next month's targets are computed after the close on the
    second-to-last trading day and executed on the last trading day, so
    those trades belong to the NEXT month's bar, not the month they were
    placed in. Bar M is therefore the end-of-day holdings on the last
    trading day of month M-1 (the rebalance close). The inception month
    uses the close on the first trading day on or after ALLOC_HISTORY_START,
    when the initial positions were entered.

    The current open month appears as the final bar with its going-in
    weights, the same weights the Current Allocation table shows, including
    an active month-start override. When the data ends on a month-end
    rebalance that has registered (see find_rebalance_dates), the next
    month's bar is added right away with that rebalance as its going-in
    date, so the final bar and the Current Allocation table always agree. The cash sleeve
    comes from reconstructed_account_value.csv when available.

    Returns a Plotly figure, or None if there is no usable data.
    """
    if holdings_values.empty:
        return None
    hv = holdings_values.fillna(0.0).sort_index()
    inception = pd.Timestamp(ALLOC_HISTORY_START)
    in_range = hv.index[hv.index >= inception]
    if len(in_range) == 0:
        return None

    # Last trading day of every calendar month in the data, including the
    # pre-inception months so February 2024 can find its January close.
    idx = hv.index
    month_ends = idx.to_series().groupby([idx.year, idx.month]).max()

    # Bars run through the data's last month, plus the month after it when
    # the data ends on a registered month-end rebalance (that month's closed
    # final session). The extra bar's going-in date is that rebalance, the
    # same basket the Current Allocation table shows.
    last_period = idx[-1].to_period("M")
    rebalances = find_rebalance_dates(hv)
    if rebalances and rebalances[0] == idx[-1]:
        last_period = last_period + 1

    # (month period, going-in date) pairs, oldest first.
    bar_dates = []
    for period in pd.period_range(in_range[0].to_period("M"), last_period, freq="M"):
        prev = period - 1
        going_in = month_ends.get((prev.year, prev.month))
        if going_in is None or going_in < inception:
            in_month = in_range[(in_range.year == period.year) & (in_range.month == period.month)]
            if len(in_month) == 0:
                continue
            going_in = in_month[0]
        bar_dates.append((period, going_in))

    totals = _load_reconstructed_totals()
    override = load_month_start_override()
    override_date = override["period_start_date"] if override else ""

    cat_keys = [k for k, _label, _color in ALLOC_HISTORY_CATEGORIES]
    labels = []
    weights = {k: [] for k in cat_keys}   # percent values per month
    details = {k: [] for k in cat_keys}   # per-month ticker breakdown strings

    for period, date in bar_dates:
        date_key = date.strftime("%Y-%m-%d")
        correction = ALLOC_HISTORY_EXECUTION_CORRECTIONS.get(date_key)
        if correction is None and override and date_key == override_date:
            correction = override["weights"]
        if correction:
            # Broker execution error on this rebalance: show the basket the
            # strategy called for, as the Current Allocation table does.
            items = [(t, float(w)) for t, w in correction.items()]
            total = sum(w for _t, w in items)
            cash_dollars = 0.0
        else:
            row = hv.loc[date]
            items = [(t, float(v)) for t, v in row.items()]
            total = float(row.sum())
            cash_dollars = 0.0
            if totals is not None and date in totals.index:
                account_value = float(totals.at[date, "account_value"])
                if account_value > 0:
                    total = account_value
                    cash_dollars = max(float(totals.at[date, "cash"]), 0.0)
        if total <= 0:
            continue

        month_w = {k: 0.0 for k in cat_keys}
        month_parts = {k: [] for k in cat_keys}
        for ticker, value in items:
            if value <= 0:
                continue
            key = ALLOC_HISTORY_TICKER_CATEGORY.get(ticker, "us")
            w = value / total
            month_w[key] += w
            month_parts[key].append((ticker, w))
        month_w["cash"] += cash_dollars / total

        labels.append(period.strftime("%b-%y"))
        for k in cat_keys:
            pct = month_w[k] * 100.0
            # None (not 0) hides empty categories from the unified hover.
            weights[k].append(pct if pct >= 0.05 else None)
            parts = sorted(month_parts[k], key=lambda p: -p[1])
            if len(parts) >= 2:
                details[k].append(
                    "  (" + ", ".join(f"{t} {w * 100.0:.1f}%" for t, w in parts) + ")"
                )
            else:
                details[k].append("")

    if not labels:
        return None

    fig = go.Figure()
    for key, label, color in ALLOC_HISTORY_CATEGORIES:
        fig.add_trace(go.Bar(
            x=labels,
            y=weights[key],
            name=label,
            customdata=details[key],
            marker=dict(
                color=color,
                cornerradius=6,
                line=dict(color="#ffffff", width=1),
            ),
            hovertemplate="%{y:.1f}%%{customdata}<extra>" + label + "</extra>",
        ))
    fig.update_layout(
        **DARK_LAYOUT,
        barmode="stack",
        bargap=0.35,
        hovermode="x unified",
        yaxis=dict(
            range=[0, 100.5],
            dtick=25,
            ticksuffix="%",
            gridcolor=GRID_COLOR,
            zeroline=True,
            zerolinecolor=ZERO_LINE,
            tickfont=dict(size=15, color=TEXT_MUTED),
        ),
        xaxis=dict(
            type="category",
            tickvals=labels[::3],
            tickangle=0,
            tickfont=dict(size=14, color=TEXT_SECONDARY),
        ),
        legend=dict(
            orientation="h", yanchor="top", y=-0.12,
            xanchor="center", x=0.5,
            traceorder="normal",
            font=dict(size=16, color=TEXT_SECONDARY, weight=500),
        ),
        margin=dict(t=30, b=70, l=55, r=30),
        height=470,
    )
    return fig



def load_next_allocation():
    """Load the saved next allocation from JSON, or return an empty list."""
    if not os.path.exists(NEXT_ALLOC_PATH):
        return []
    try:
        with open(NEXT_ALLOC_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, OSError):
        return []


def save_next_allocation(rows):
    """Persist the next allocation to JSON."""
    with open(NEXT_ALLOC_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def build_next_allocation_table(rows):
    """Build a Plotly table figure for the next allocation, matching the
    Current Allocation table style. Rows are listed largest weight first."""

    rows = sort_rows_by_weight(rows)
    header_values = ["Asset", "Ticker", "Weight", "Purpose"]
    assets = [f'{row["emoji"]}  {row["asset"]}' for row in rows]
    tickers = [row["ticker"] for row in rows]
    weights = [_pct1_str(row["weight"]) for row in rows]
    purposes = [row["purpose"] for row in rows]

    n = len(rows)
    row_fills = ["#F9FAFB" if i % 2 == 1 else "#ffffff" for i in range(n)]

    fig = go.Figure(data=[go.Table(
        columnwidth=[220, 70, 80, 320],
        header=dict(
            values=[f"<b>{v}</b>" for v in header_values],
            fill_color="#F9FAFB",
            line_color="#E5E7EB",
            align=["left", "left", "right", "left"],
            font=dict(family="DM Sans, sans-serif", size=17, color=TEXT_PRIMARY),
            height=38,
        ),
        cells=dict(
            values=[assets, tickers, weights, purposes],
            fill_color=[row_fills],
            line_color="#E5E7EB",
            align=["left", "left", "right", "left"],
            font=dict(family="DM Sans, sans-serif", size=16, color=TEXT_PRIMARY),
            height=38,
        ),
    )])

    fig.update_layout(
        **DARK_LAYOUT,
        margin=dict(t=2, b=2, l=2, r=2),
        height=38 + 38 * n + 10,
        width=790,
    )
    return fig


# ---------- Allocation Drift table ----------
# Reads per-ticker daily dollar values emitted by portfolio_valuation.py and
# produces a forward-looking five-column summary: Asset, Month Start (going-in
# weights from the most recent rebalance), Pre-Rebalance Drift (current
# weights as of the latest data day), New Target (upcoming target from
# next_allocation.json), Trade (Drift -> New Target). This is the table the
# newsletter uses to preview the trades the upcoming rebalance will execute.


def _holdings_values_paths():
    """Return candidate paths for holdings_daily_values.csv (pipeline first)."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pipeline_dir = os.path.join(os.path.dirname(script_dir), "Portfolio Hist Val Reconstruction")
    return [
        os.path.join(pipeline_dir, "holdings_daily_values.csv"),
        os.path.join(script_dir, "holdings_daily_values.csv"),
    ]


@st.cache_data(ttl=3600)
def load_holdings_values():
    """Load per-ticker daily dollar values produced by portfolio_valuation.py.

    Returns a DataFrame indexed by date with one column per ticker. Each
    cell is the dollar value held in that ticker on that day. Returns an
    empty DataFrame if the file is missing or cannot be parsed.
    """
    for path in _holdings_values_paths():
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_csv(path, parse_dates=["date"])
            df = df.set_index("date").sort_index()
            return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


FIDELITY_LEDGER_NAME = "History_for_Account_Z27314115.csv"


@st.cache_data(ttl=3600)
def load_position_flows():
    """Per-ticker daily cash moving into or out of each position, from the
    Fidelity transaction export the pipeline is built on.

    Positive means cash came out of the position into the account (a sale or a
    dividend), negative means cash went into it (a purchase or a reinvested
    dividend). An in-kind ACAT transfer counts as money put into the position
    at the value Fidelity records, since those shares arrived from outside the
    account rather than being earned. Added October 29, 2026 so What Drove the
    Month can measure each position's actual dollar gain, including trades
    filled at prices other than the close.

    Returns a DataFrame indexed by trade date with one column per ticker, or
    None if the export is missing or unreadable.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pipeline_dir = os.path.join(os.path.dirname(script_dir), "Portfolio Hist Val Reconstruction")
    path = os.path.join(pipeline_dir, FIDELITY_LEDGER_NAME)
    if not os.path.exists(path):
        # The cloud deploy gets position_flows.csv, written by
        # portfolio_valuation.py with the same logic, instead of the raw export.
        for flows_path in (os.path.join(pipeline_dir, "position_flows.csv"),
                           os.path.join(script_dir, "position_flows.csv")):
            if os.path.exists(flows_path):
                try:
                    return pd.read_csv(flows_path, parse_dates=["date"]).set_index("date").sort_index()
                except Exception:
                    return None
        return None
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
        df.columns = [c.strip() for c in df.columns]
        df["date"] = pd.to_datetime(df["Run Date"], errors="coerce")
        df["sym"] = (df["Symbol"].astype(str).str.strip().str.upper()
                     .replace({"NAN": "", "NONE": ""}))
        amt = pd.to_numeric(df["Amount ($)"], errors="coerce").fillna(0.0)
        qty = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0.0)
        act = df["Action"].astype(str).str.upper()
        trade = (act.str.startswith("YOU BOUGHT") | act.str.startswith("YOU SOLD")
                 | act.str.startswith("DIVIDEND RECEIVED") | act.str.contains("REINVESTMENT")
                 | act.str.contains("SPINOFF") | act.str.contains("IN LIEU OF"))
        acat_in_kind = act.str.contains("TRANSFER OF ASSETS") & (df["sym"] != "") & (qty.abs() > 0)
        flow = amt.where(trade, 0.0) - amt.where(acat_in_kind, 0.0)
        keep = (trade | acat_in_kind) & (df["sym"] != "") & df["date"].notna() \
            & ~df["sym"].isin(CASH_LIKE_TICKERS)
        out = (pd.DataFrame({"date": df.loc[keep, "date"], "sym": df.loc[keep, "sym"],
                             "flow": flow[keep]})
               .groupby(["date", "sym"])["flow"].sum().unstack(fill_value=0.0).sort_index())
        return out
    except Exception:
        return None


MONTH_START_OVERRIDE_NAME = "month_start_override.json"


def _month_start_override_paths():
    """Candidate paths for the optional month-start override file."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pipeline_dir = os.path.join(os.path.dirname(script_dir), "Portfolio Hist Val Reconstruction")
    return [
        os.path.join(script_dir, MONTH_START_OVERRIDE_NAME),
        os.path.join(pipeline_dir, MONTH_START_OVERRIDE_NAME),
    ]


@st.cache_data(ttl=3600)
def load_month_start_override():
    """Optional correction for the current period's going-in weights.

    This exists for the case where a broker rebalance did not execute the
    intended basket, so the holdings sitting on the rebalance date are not
    the weights the strategy actually called for. Every table that reads
    start_weights (Current Allocation, Allocation Drift, Live Position
    Drift) then measures against the intended basket rather than the
    mis-executed one.

    It never touches the return series. Realized performance always
    reflects what was actually held, including the cost of the error.

    Schema:
        {"period_start_date": "YYYY-MM-DD",
         "weights": {"TICKER": percent, ...},
         "note": "why this exists"}

    The override applies only when period_start_date matches the rebalance
    date the holdings data reports, so it expires by itself at the next
    month-end rebalance. Returns None when absent or unusable.
    """
    for path in _month_start_override_paths():
        if not os.path.exists(path):
            continue
        try:
            # utf-8-sig so a byte-order mark from a Windows editor or
            # PowerShell redirect does not silently disable the override.
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            weights = {str(k): float(v) for k, v in (data.get("weights") or {}).items()}
            total = sum(weights.values())
            if not weights or total <= 0:
                return None
            return {
                "period_start_date": str(data.get("period_start_date", "")).strip(),
                "weights": {k: v / total for k, v in weights.items()},
                "note": str(data.get("note", "")).strip(),
            }
        except Exception:
            return None
    return None


class _NYSEHolidayCalendar(AbstractHolidayCalendar):
    """NYSE full-day market holidays, used to tell whether a date is the last
    trading day of its month. Only Good Friday and Memorial Day can ever
    displace a month's final session, but the full list keeps it honest.
    Unscheduled closures (days of mourning, weather) are not listed; if one
    ever lands on a month's final weekday, the rebalance is simply picked up
    a day later, the same way it was before this calendar existed."""
    rules = [
        Holiday("New Year's Day", month=1, day=1, observance=sunday_to_monday),
        USMartinLutherKingJr,
        USPresidentsDay,
        GoodFriday,
        USMemorialDay,
        Holiday("Juneteenth", month=6, day=19, start_date="2022-01-01",
                observance=nearest_workday),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday("Christmas Day", month=12, day=25, observance=nearest_workday),
    ]


def _is_month_final_session(day):
    """True when day is a trading day and no trading day follows it in the
    same calendar month."""
    day = pd.Timestamp(day).normalize()
    month_end = day + pd.offsets.MonthEnd(0)
    holidays = _NYSEHolidayCalendar().holidays(day, month_end)
    if day.dayofweek >= 5 or day in holidays:
        return False
    later = pd.bdate_range(day + pd.Timedelta(days=1), month_end, freq="C",
                           holidays=holidays)
    return len(later) == 0


def _session_has_closed(day):
    """True once the regular session on day has ended (4 p.m. Eastern), so a
    rebalance is never read from a partial trading day. If the Eastern clock
    is unavailable, only days before today count."""
    day = pd.Timestamp(day).normalize()
    try:
        from zoneinfo import ZoneInfo
        now_et = pd.Timestamp(datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None))
    except Exception:
        return day < pd.Timestamp(local_now()).normalize()
    return now_et >= day + pd.Timedelta(hours=16)


def find_rebalance_dates(holdings_values):
    """Return rebalance dates from the holdings_values index.

    The Asymmetric Edge strategy rebalances on the last trading day of each
    calendar month, regardless of how much the targets shift versus the
    prior month. This function returns the last trading day of every month
    that has been fully completed in the dataset, sorted most recent first.

    A month is treated as completed when the data extends past its last
    trading day (i.e., the next month has begun), or when the data ends ON
    the month's final trading day and that session has closed. The second
    case matters because portfolio_valuation.py stops its grid at the
    ledger's last transaction, which on a rebalance day is the rebalance
    itself. Without it, a fresh rebalance would not register until the next
    transaction extended the data, and every table reading start_weights
    would keep showing the prior month's basket. A month that is still
    open, whose rebalance has not happened yet, is excluded. This is robust
    to months where the new targets are similar to the old ones, which a
    turnover-threshold approach would miss.
    """
    if holdings_values.empty:
        return []
    idx = holdings_values.index
    # Last trading day of each calendar month present in the data
    month_ends = idx.to_series().groupby([idx.year, idx.month]).max()
    # Keep only month-ends that have at least one trading day after them
    completed = [d for d in month_ends.tolist() if (idx > d).any()]
    # Plus the data's last day when it is its month's closed final session
    last_day = idx.max()
    if (last_day not in completed and _is_month_final_session(last_day)
            and _session_has_closed(last_day)):
        completed.append(last_day)
    return sorted(completed, reverse=True)


def compute_drift_summary(holdings_values):
    """Build the data the Allocation Drift table needs.

    Identifies the most recent rebalance (the start of the current period)
    and the latest day in the data (the current drift snapshot). Returns:
      period_start_date   the most recent rebalance, which set the
                          going-in weights for the current period
      drift_date          the latest day in the data, capturing where
                          those weights have drifted to so far
      start_weights       {ticker: weight} at end of day on period_start_date
      drift_weights       {ticker: weight} at end of day on drift_date

    Returns None if no rebalance has occurred yet or totals are non-positive.

    Forward-looking by design: the table pairs Month Start (going-in) with
    current Drift, so that compared against the upcoming Next Target it
    previews the buys and sells that will execute at the next rebalance.
    """
    rebalance_dates = find_rebalance_dates(holdings_values)
    if not rebalance_dates:
        return None

    period_start = rebalance_dates[0]
    drift_date = holdings_values.index[-1]

    daily_totals = holdings_values.sum(axis=1)
    start_total = float(daily_totals.loc[period_start])
    drift_total = float(daily_totals.loc[drift_date])
    if start_total <= 0 or drift_total <= 0:
        return None

    start_weights = (holdings_values.loc[period_start] / start_total).to_dict()
    drift_weights = (holdings_values.loc[drift_date] / drift_total).to_dict()

    # A month-start override replaces the going-in weights when the broker
    # did not execute the intended basket on the rebalance date. It is
    # keyed to a specific rebalance date, so it lapses on its own at the
    # next month end. The return series is never affected.
    override = load_month_start_override()
    override_note = ""
    if override and override["period_start_date"] == period_start.strftime("%Y-%m-%d"):
        start_weights = dict(override["weights"])
        override_note = override["note"]

    return {
        "period_start_date": period_start,
        "drift_date": drift_date,
        "start_weights": start_weights,
        "drift_weights": drift_weights,
        "start_weights_overridden": bool(override_note),
        "start_weights_note": override_note,
    }


def derive_current_allocation(holdings_values):
    """Derive Current Allocation rows from actual holdings at the most recent
    rebalance close, the same source the Allocation Drift table uses for its
    Month Start column.

    Returns (rows, rebalance_date). rows is a list of allocation-row dicts
    (emoji, asset, ticker, weight, purpose) with weight as a 2-decimal percent
    string. Returns (None, None) if holdings data is unavailable, so callers
    can show an error instead of stale numbers.

    By reusing the same start_weights, threshold, and number formatting as
    build_drift_table, the Current Allocation table is guaranteed to match
    the drift table's Month Start column exactly. Rows come back in
    canonical order; both table builders list them largest Month Start
    weight first at render time, so the two tables also share a row order.
    """
    summary = compute_drift_summary(holdings_values)
    if summary is None:
        return None, None
    start = summary["start_weights"]
    weight_threshold = 0.0005  # 0.05%, matches build_drift_table
    tickers = [t for t, w in start.items() if w > weight_threshold]
    ordered = canonical_order(tickers)
    rows = []
    for ticker in ordered:
        info = ASSET_CATALOG.get(ticker, {"asset": ticker, "emoji": "", "purpose": ""})
        rows.append({
            "emoji": info.get("emoji", ""),
            "asset": info.get("asset", ticker),
            "ticker": ticker,
            "weight": f"{start[ticker] * 100.0:.2f}%",
            "weight_pct": start[ticker] * 100.0,
            "purpose": info.get("purpose", ""),
        })
    if not rows:
        return None, None
    return rows, summary["period_start_date"]


def build_drift_table(summary, new_target_rows):
    """Build a Plotly table for the Allocation Drift view.

    Mirrors build_allocation_table styling. Columns:
      Asset | Month Start | Pre-Rebalance Drift | New Target | Trade

    Month Start shows weights at the most recent rebalance close (the
    going-in weights for the current period). Pre-Rebalance Drift shows
    current weights as of the latest data day. New Target is the upcoming
    allocation from next_allocation.json. Trade is Drift -> New Target.
    Rows are listed largest Month Start weight first.

    If new_target_rows is empty (no upcoming allocation entered yet), the
    New Target and Trade cells render as em-dashes so the table still shows
    drift without misleading "(exit)" labels for every position.
    """
    start = summary["start_weights"]
    drift = summary["drift_weights"]

    # Index new targets by ticker, with numeric weights parsed once.
    new_target_map = {}
    for row in new_target_rows:
        ticker = row.get("ticker")
        if not ticker:
            continue
        weight_str = str(row.get("weight", "")).replace("%", "").strip()
        try:
            weight_num = float(weight_str)
        except ValueError:
            weight_num = 0.0
        new_target_map[ticker] = weight_num

    target_is_set = any(w > 0 for w in new_target_map.values())

    # Union of tickers that meaningfully appear in any column.
    weight_threshold = 0.0005  # 0.05% in weight terms
    union = set()
    for ticker, w in start.items():
        if w > weight_threshold:
            union.add(ticker)
    for ticker, w in drift.items():
        if w > weight_threshold:
            union.add(ticker)
    for ticker, w in new_target_map.items():
        if w > 0:
            union.add(ticker)

    # Largest Month Start weight first, so the rows line up with the Current
    # Allocation table. A position opening at the upcoming rebalance (no
    # Month Start weight) sorts below the held ones, largest New Target first.
    ordered = weight_order(
        {t: start.get(t, 0.0) for t in union},
        tiebreak={t: new_target_map.get(t, 0.0) for t in union},
    )

    asset_cells, start_cells, drift_cells, target_cells, trade_cells = [], [], [], [], []
    for ticker in ordered:
        info = ASSET_CATALOG.get(ticker, {"asset": ticker, "emoji": ""})
        start_w = start.get(ticker, 0.0) * 100.0
        drift_w = drift.get(ticker, 0.0) * 100.0
        target_w = new_target_map.get(ticker, 0.0)
        trade = target_w - drift_w

        asset_cells.append(f'{info["emoji"]}  {info["asset"]} ({ticker})')
        start_cells.append(_pct1(start_w))
        drift_cells.append(_pct1(drift_w))

        if target_is_set:
            target_cells.append(_pct1(target_w))
            is_new = start_w < 0.005 and drift_w < 0.005 and target_w > 0
            is_exit = target_w < 0.005 and drift_w >= 0.005
            if is_new:
                trade_cells.append(f"+{_pct1(target_w)} (new)")
            elif is_exit:
                trade_cells.append(f"-{_pct1(drift_w)} (exit)")
            else:
                trade_cells.append(_pct1(trade, signed=True))
        else:
            target_cells.append("\u2014")
            trade_cells.append("\u2014")

    n = len(asset_cells)
    row_fills = ["#F9FAFB" if i % 2 == 1 else "#ffffff" for i in range(n)]

    header_values = ["Asset", "Month Start", "Drift", "New Target", "Trim/Add"]

    # Column widths are tuned so the widest real content fits on one line, in
    # both the header row and the cells. Two columns need more room than a
    # bare percentage: Trim/Add carries labels like "-100.00% (exit)", and the
    # "Month Start" and "New Target" headers are the longest header strings.
    # Laid out at width=780 (October 22, 2026): Tyler's Firefox content column
    # is about 795 px, and Streamlit squeezes any wider figure to fit, which
    # wrapped the asset names and clipped the last row at the old 860. The
    # asset column keeps 287 px, enough for the longest name on one line.
    # If any cell or header wraps to a second line, the table renders taller
    # than the figure height set below and the final row gets clipped, so
    # these widths and that height calculation have to stay in sync.
    fig = go.Figure(data=[go.Table(
        columnwidth=[255, 120, 80, 110, 125],
        header=dict(
            values=[f"<b>{v}</b>" for v in header_values],
            fill_color="#F9FAFB",
            line_color="#E5E7EB",
            align=["left", "right", "right", "right", "right"],
            font=dict(family="DM Sans, sans-serif", size=17, color=TEXT_PRIMARY),
            height=38,
        ),
        cells=dict(
            values=[asset_cells, start_cells, drift_cells, target_cells, trade_cells],
            fill_color=[row_fills],
            line_color="#E5E7EB",
            align=["left", "right", "right", "right", "right"],
            font=dict(family="DM Sans, sans-serif", size=16, color=TEXT_PRIMARY),
            height=38,
        ),
    )])

    fig.update_layout(
        **DARK_LAYOUT,
        margin=dict(t=2, b=2, l=2, r=2),
        # Header row + n data rows + a 24px cushion. The cushion is larger than
        # the other tables' 10px because this one carries the widest cells, so
        # it absorbs a stray wrap instead of clipping the last row.
        height=38 + 38 * n + 24,
        width=780,
    )
    return fig


@st.cache_data(ttl=1800)
def compute_live_position_drift(tickers_tuple, start_weights_tuple, today_str,
                                cache_version="v1"):
    """Compute how the current month's going-in weights have drifted, live.

    Pulls dividend-adjusted Yahoo closes for the current allocation tickers
    and measures how each position's weight has moved since the start of the
    current month. Lets a mid-month client deposit or withdrawal be sized
    against where the positions actually sit now, without rerunning the
    reconstruction pipeline.

    The anchor (month start) is the last trading day of the calendar month
    before the current one, which is the most recent month-end rebalance and
    the going-in date for the current month's targets. This matches the Month
    Start convention used elsewhere on the dashboard.

    For each ticker:
        ret      = latest_close / anchor_close - 1   (total return since anchor)
        drift_w  = start_w * (1 + ret), renormalized across the holdings

    today_str is part of the cache key so the anchor recomputes each calendar
    day even while the ttl cache is still warm.

    Returns (result, message). result is None when live prices could not be
    fetched. On a partial failure the function uses the tickers that did
    fetch, renormalizes the start weights across them, and names the rest in
    the message.
    """
    tickers = list(tickers_tuple)
    start_weights = {t: float(w) for t, w in zip(tickers, start_weights_tuple)}
    if not tickers:
        return None, "no tickers in current allocation"

    today_ts = pd.Timestamp(today_str).normalize()
    first_of_month = today_ts.replace(day=1)
    prior_month_end_cal = first_of_month - pd.Timedelta(days=1)
    prior_year, prior_month = prior_month_end_cal.year, prior_month_end_cal.month

    fetch_start = (first_of_month - pd.Timedelta(days=75)).strftime("%Y-%m-%d")
    fetch_end = (today_ts + pd.Timedelta(days=2)).strftime("%Y-%m-%d")

    # Yahoo, then the snapshot, then the chart endpoint. Partial results are
    # fine here: the caller renormalizes across whichever tickers came back.
    close_map = dict(_yahoo_closes(tickers, fetch_start, fetch_end))

    snap = load_price_snapshot()
    lo, hi = pd.Timestamp(fetch_start), pd.Timestamp(fetch_end)
    for t in tickers:
        if t in close_map or t not in snap.columns:
            continue
        s = _clean_series(snap[t])
        s = s[(s.index >= lo) & (s.index <= hi)]
        if len(s):
            close_map[t] = s

    still_missing = [t for t in tickers if t not in close_map]
    if still_missing:
        close_map.update(_fallback_closes(still_missing, fetch_start, fetch_end))

    if not close_map:
        return None, "no price data from Yahoo or the committed snapshot"

    close = pd.DataFrame(close_map).sort_index()

    # Anchor = last trading day in the prior calendar month.
    prior_mask = (close.index.year == prior_year) & (close.index.month == prior_month)
    if not prior_mask.any():
        return None, (
            f"no trading days found in the prior month "
            f"({prior_year}-{prior_month:02d})"
        )
    anchor_dt = close.index[prior_mask].max()

    # As-of = latest available close that is not beyond today.
    on_or_before_today = close.index[close.index <= today_ts]
    if len(on_or_before_today) == 0:
        return None, "no trading days at or before today"
    as_of_dt = on_or_before_today.max()
    if as_of_dt < anchor_dt:
        as_of_dt = anchor_dt

    rows = {}
    skipped = []
    for t in tickers:
        if t not in close.columns:
            skipped.append(t)
            continue
        a = close.loc[anchor_dt, t]
        b = close.loc[as_of_dt, t]
        if pd.isna(a) or pd.isna(b) or float(a) <= 0:
            skipped.append(t)
            continue
        rows[t] = {
            "ret": float(b) / float(a) - 1.0,
            "start_w": start_weights.get(t, 0.0),
        }

    if not rows:
        return None, "none of the allocation tickers returned usable prices"

    # Renormalize start weights across the tickers that fetched, then grow
    # each by its return and renormalize again to get the drifted weights.
    surviving_start_total = sum(r["start_w"] for r in rows.values())
    if surviving_start_total <= 0:
        return None, "surviving tickers have zero combined start weight"
    for r in rows.values():
        r["start_w"] = r["start_w"] / surviving_start_total

    grown = {t: r["start_w"] * (1.0 + r["ret"]) for t, r in rows.items()}
    grown_total = sum(grown.values())
    if grown_total <= 0:
        return None, "drifted weights summed to a non-positive total"
    for t, r in rows.items():
        r["drift_w"] = grown[t] / grown_total

    skip_note = f" (skipped: {', '.join(sorted(set(skipped)))})" if skipped else ""
    result = {
        "anchor_date": anchor_dt,
        "as_of_date": as_of_dt,
        "rows": rows,
        "tickers": [t for t in tickers if t in rows],
    }
    return result, f"ok{skip_note}"


def build_live_drift_table(result):
    """Build a Plotly table for the Live Position Drift view.

    Mirrors build_allocation_table styling. Columns:
      Asset | Ticker | Month Start | Return | Current

    Month Start is each holding's going-in target weight for the current
    month. Return is its total return since the month-start anchor. Current is
    the weight it has drifted to as of the latest close. The Return column is
    tinted green for gains and red for losses so the over- and under-
    performers stand out at a glance. Rows are listed largest Month Start
    weight first.
    """
    rows = result["rows"]
    # Largest Month Start weight first, matching the Current Allocation table.
    # Sorting on Month Start rather than Current keeps the rows from
    # reshuffling as prices move during the month.
    ordered = weight_order({t: r["start_w"] for t, r in rows.items()})

    asset_cells, ticker_cells = [], []
    start_cells, ret_cells, cur_cells = [], [], []
    ret_colors = []
    for ticker in ordered:
        info = ASSET_CATALOG.get(ticker, {"asset": ticker, "emoji": ""})
        r = rows[ticker]
        ret_pct = r["ret"] * 100.0
        asset_cells.append(f'{info["emoji"]}  {info["asset"]}')
        ticker_cells.append(ticker)
        start_cells.append(_pct1(r["start_w"] * 100.0))
        ret_cells.append(_pct1(ret_pct, signed=True))
        cur_cells.append(_pct1(r["drift_w"] * 100.0))
        ret_colors.append(GAIN_GREEN if round(ret_pct, 1) >= 0 else LOSS_RED)

    n = len(asset_cells)
    row_fills = ["#F9FAFB" if i % 2 == 1 else "#ffffff" for i in range(n)]
    primary_col = [TEXT_PRIMARY] * n

    header_values = ["Asset", "Ticker", "Month Start", "Return", "Current"]

    fig = go.Figure(data=[go.Table(
        columnwidth=[230, 80, 120, 110, 110],
        header=dict(
            values=[f"<b>{v}</b>" for v in header_values],
            fill_color="#F9FAFB",
            line_color="#E5E7EB",
            align=["left", "left", "right", "right", "right"],
            font=dict(family="DM Sans, sans-serif", size=17, color=TEXT_PRIMARY),
            height=38,
        ),
        cells=dict(
            values=[asset_cells, ticker_cells, start_cells, ret_cells, cur_cells],
            fill_color=[row_fills],
            line_color="#E5E7EB",
            align=["left", "left", "right", "right", "right"],
            font=dict(
                family="DM Sans, sans-serif",
                size=16,
                color=[primary_col, primary_col, primary_col, ret_colors, primary_col],
            ),
            height=38,
        ),
    )])

    fig.update_layout(
        **DARK_LAYOUT,
        margin=dict(t=2, b=2, l=2, r=2),
        height=38 + 38 * n + 10,
        width=790,
    )
    return fig


# ---------- Partial-month extension ----------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _parse_current_allocation_weights(rows):
    """Parse allocation rows into a {ticker: weight_decimal} dict.

    rows is a list of dicts each with a "ticker" and a "weight" string like
    '27.60%'. Weights are stripped of the percent sign, divided by 100, and
    normalized to sum to 1.0 exactly. Returns None if rows is empty, any parse
    step fails, or the total is non-positive, so callers degrade gracefully.
    """
    if not rows:
        return None
    try:
        weights = {}
        for row in rows:
            ticker = (row.get("ticker") or "").strip()
            w_str = str(row.get("weight", "0")).replace("%", "").strip()
            if not ticker:
                continue
            w = float(w_str) / 100.0
            if w <= 0:
                continue
            weights[ticker] = w
        total = sum(weights.values())
        if total <= 0 or not weights:
            return None
        return {t: w / total for t, w in weights.items()}
    except (ValueError, TypeError, AttributeError):
        return None


def current_allocation_weights():
    """Return {ticker: weight_decimal} for the current allocation, derived from
    actual holdings at the most recent rebalance (holdings_daily_values.csv) and
    normalized to sum to 1.0. Returns None if the holdings data is unavailable.

    There is intentionally no hardcoded fallback, so callers either get the real
    current weights or None (and the UI shows an error rather than stale,
    hand-entered numbers).
    """
    rows, _date = derive_current_allocation(load_holdings_values())
    return _parse_current_allocation_weights(rows)


@st.cache_data(ttl=3600)
def extend_reconstruction_via_yahoo(recon_last_date_str: str, target_date_str: str,
                                    recon_last_value: float,
                                    tickers_tuple: tuple, weights_tuple: tuple,
                                    cache_version: str = "v3"):
    """Extend the close-only reconstruction past its last date using Yahoo
    closes for the current allocation tickers.

    For each trading day strictly after ``recon_last_date_str`` through
    ``target_date_str``, computes a weighted growth factor relative to the
    last close on or before ``recon_last_date_str``:

        factor[d] = sum_i w_i * (close_i[d] / close_i[anchor])

    Then multiplies by ``recon_last_value`` to get the extended portfolio
    value on each day.

    Robustness notes:
      - Single-ticker fetches return a flat-column DataFrame; multi-ticker
        fetches return a MultiIndex. Both are handled.
      - If a subset of the tickers fails to fetch, the function falls back
        to using only the successful ones, with the weights renormalized
        across the survivors so they still sum to 1.0.
      - Any uncaught failure returns an empty DataFrame and a diagnostic
        message so callers can surface the cause to the user.

    Inputs are strings/tuples so the result is cacheable. The ``cache_version``
    parameter exists so we can bump it from elsewhere to force re-fetch.

    Returns a tuple: (DataFrame[date, portfolio_value], diagnostic_message).
    DataFrame is empty if extension is not possible.
    """
    recon_last_ts = pd.Timestamp(recon_last_date_str)
    target_ts = pd.Timestamp(target_date_str)
    tickers = list(tickers_tuple)
    weights = np.array(list(weights_tuple), dtype=float)
    empty = pd.DataFrame(columns=["date", "portfolio_value"])

    if target_ts <= recon_last_ts:
        return empty, "target date is not after the recon's last date"
    if not tickers:
        return empty, "no tickers in current allocation"

    fetch_start = (recon_last_ts - timedelta(days=10)).strftime("%Y-%m-%d")
    fetch_end = (target_ts + timedelta(days=5)).strftime("%Y-%m-%d")

    # Same three-source ladder the chart loaders use: Yahoo first, then the
    # committed snapshot, then the direct chart endpoint. A ticker with
    # no data simply drops out and the surviving weights are renormalized.
    close_map = dict(_yahoo_closes(tickers, fetch_start, fetch_end))

    snap = load_price_snapshot()
    lo, hi = pd.Timestamp(fetch_start), pd.Timestamp(fetch_end)
    for t in tickers:
        if t in close_map or t not in snap.columns:
            continue
        s = _clean_series(snap[t])
        s = s[(s.index >= lo) & (s.index <= hi)]
        if len(s):
            close_map[t] = s

    still_missing = [t for t in tickers if t not in close_map]
    if still_missing:
        close_map.update(_fallback_closes(still_missing, fetch_start, fetch_end))

    if not close_map:
        return empty, "no price data from Yahoo or the committed snapshot"

    close = pd.DataFrame(close_map).sort_index()

    # Find which tickers actually have data for the anchor date
    on_or_before_idx = close.index[close.index <= recon_last_ts]
    if len(on_or_before_idx) == 0:
        return empty, f"yfinance returned no trading days at or before {recon_last_ts.date()}"

    anchor_dt = on_or_before_idx[-1]
    # A ticker only helps if it has both an anchor close and at least one close
    # after the anchor; a stale snapshot-only column would otherwise blank out
    # every extension day for the whole basket.
    available_tickers = []
    for t in tickers:
        if t not in close.columns:
            continue
        col = close[t].dropna()
        if len(col[(col.index > recon_last_ts) & (col.index <= target_ts)]) == 0:
            continue
        available_tickers.append(t)
    if not available_tickers:
        return empty, f"no fresh closes after {recon_last_ts.date()} for {tickers}"

    # Build per-ticker anchor closes, dropping any that are NaN/zero
    anchor_values = {}
    for t in available_tickers:
        v = close.loc[anchor_dt, t]
        if pd.notna(v) and float(v) > 0:
            anchor_values[t] = float(v)

    if not anchor_values:
        return empty, "all anchor closes were NaN or zero"

    # Renormalize weights across the surviving tickers
    surviving = list(anchor_values.keys())
    surviving_weights = np.array([weights[tickers.index(t)] for t in surviving], dtype=float)
    if surviving_weights.sum() <= 0:
        return empty, "surviving tickers have zero combined weight"
    surviving_weights = surviving_weights / surviving_weights.sum()
    anchor_arr = np.array([anchor_values[t] for t in surviving], dtype=float)

    skipped = sorted(set(tickers) - set(surviving))
    skip_note = f" (skipped: {', '.join(skipped)})" if skipped else ""

    # Extension dates: trading days strictly after recon_last_ts through target_ts
    ext_idx = close.index[(close.index > recon_last_ts) & (close.index <= target_ts)]
    if len(ext_idx) == 0:
        return empty, (
            f"yfinance has no trading days strictly after {recon_last_ts.date()} "
            f"through {target_ts.date()}{skip_note}"
        )

    new_dates, new_values = [], []
    for d in ext_idx:
        row = close.loc[d, surviving]
        day_arr = np.asarray(row.values, dtype=float)
        if not np.all(np.isfinite(day_arr)) or np.any(day_arr <= 0):
            continue
        ratios = day_arr / anchor_arr
        weighted_factor = float(np.dot(ratios, surviving_weights))
        new_dates.append(d)
        new_values.append(recon_last_value * weighted_factor)

    if not new_dates:
        return empty, f"all extension-day closes were NaN or zero{skip_note}"

    df = pd.DataFrame({"date": new_dates, "portfolio_value": new_values})
    return df, f"extended {len(new_dates)} day(s) using {', '.join(surviving)}{skip_note}"


def extend_with_partial_month(portfolio_df, mtd_return_pct, as_of_date):
    """Extend the portfolio series with a partial-month daily curve.

    Reads ``reconstructed_account_value.csv`` for the close-only daily
    shape over the open month, applies a single uniform per-day
    multiplicative correction, and appends those daily values to the
    portfolio series. The same chaining approach ``build_anchored_series.py``
    uses for closed months, applied at load time so the dashboard does not
    have to redraw a straight diagonal across the open month.

    Three regimes, in priority order:
      1. Reconstruction reaches the as-of date. Scale the daily shape so
         the compound return from the previous month-end through the as-of
         date equals Fidelity's reported MTD return. The series ends on
         the as-of date at the exact target value.
      2. Reconstruction is stale (covers part of the open month but not
         all the way to the as-of date). Scale the daily shape so the
         reconstruction's last covered date sits on the geometric
         interpolation between the anchor and the target, then append a
         single endpoint row at the as-of date with the target value.
         This produces a realistic shape for the covered portion and a
         short straight segment for whatever days are not yet in the
         reconstruction.
      3. Reconstruction is unavailable or its coverage is otherwise
         unusable. Fall back to appending a single endpoint at the as-of
         date, matching the original behavior.
    """
    as_of_ts = pd.Timestamp(as_of_date)
    last_date = portfolio_df["date"].iloc[-1]

    if as_of_ts <= last_date:
        return portfolio_df

    # Note: the published series normally carries open-month daily rows from
    # the reconstruction (portfolio_valuation.py runs to the present), so the
    # CSV's last date is usually inside the as-of month. We intentionally do
    # NOT skip in that case. Workflow 1 re-anchors the open month from the
    # prior month-end to the entered MTD return, and the open-month rows are
    # REPLACED (drop_duplicates keep="last" below), not appended on top, so
    # there is no double-counting. This is what makes mid-month updates work.

    # The month-end anchor is the last value in the existing series at or
    # before the last day of the month preceding the as-of date.
    prev_month_end = pd.Timestamp(as_of_ts.year, as_of_ts.month, 1) - timedelta(days=1)
    on_or_before = portfolio_df[portfolio_df["date"] <= prev_month_end]
    if on_or_before.empty:
        return portfolio_df

    anchor_date = pd.Timestamp(on_or_before["date"].iloc[-1])
    anchor_val = float(on_or_before["portfolio_value"].iloc[-1])
    target_val = anchor_val * (1 + mtd_return_pct / 100)
    target_mtd = mtd_return_pct / 100.0

    def _single_endpoint_fallback():
        new_row = pd.DataFrame({
            "date": [as_of_ts],
            "portfolio_value": [round(target_val, 4)],
        })
        extended = pd.concat([portfolio_df, new_row], ignore_index=True)
        extended = extended.drop_duplicates(subset="date", keep="last")
        extended = extended.sort_values("date").reset_index(drop=True)
        return extended

    # Reconstruction lookup
    recon_df = load_reconstruction_data()
    if recon_df is None:
        return _single_endpoint_fallback()

    # If the canonical reconstruction does not yet cover the as-of date,
    # try to extend it using Yahoo closes weighted by the current allocation.
    # This produces realistic daily shape for the days portfolio_valuation.py
    # has not been rerun against, eliminating the straight-line segment that
    # would otherwise bridge from the recon's last date to the as-of date.
    recon_last_in_csv = pd.Timestamp(recon_df["date"].iloc[-1])
    if as_of_ts > recon_last_in_csv:
        weights_dict = current_allocation_weights()
        if weights_dict is not None:
            recon_last_value = float(recon_df["portfolio_value"].iloc[-1])
            extension_df, _ext_msg = extend_reconstruction_via_yahoo(
                recon_last_in_csv.strftime("%Y-%m-%d"),
                as_of_ts.strftime("%Y-%m-%d"),
                recon_last_value,
                tuple(weights_dict.keys()),
                tuple(weights_dict.values()),
            )
            if not extension_df.empty:
                extension_df = extension_df.copy()
                extension_df["date"] = pd.to_datetime(extension_df["date"])
                recon_df = pd.concat([recon_df, extension_df], ignore_index=True)
                recon_df = recon_df.drop_duplicates(subset="date", keep="first")
                recon_df = recon_df.sort_values("date").reset_index(drop=True)

    recon_at_or_before = recon_df[recon_df["date"] <= anchor_date]
    if recon_at_or_before.empty:
        return _single_endpoint_fallback()
    recon_anchor_val = float(recon_at_or_before["portfolio_value"].iloc[-1])
    if recon_anchor_val <= 0:
        return _single_endpoint_fallback()

    recon_window = recon_df[(recon_df["date"] > anchor_date) & (recon_df["date"] <= as_of_ts)].copy()
    if recon_window.empty:
        return _single_endpoint_fallback()
    recon_window = recon_window.sort_values("date").reset_index(drop=True)

    cumulative_factor = recon_window["portfolio_value"].astype(float).values / recon_anchor_val
    if not np.all(np.isfinite(cumulative_factor)) or cumulative_factor[-1] <= 0:
        return _single_endpoint_fallback()

    recon_mtd = float(cumulative_factor[-1]) - 1.0
    n_days = len(cumulative_factor)
    if (1.0 + recon_mtd) <= 0:
        return _single_endpoint_fallback()

    # Decide whether reconstruction reaches the as-of date. We treat the
    # window as 'reaching' the as-of date when the last reconstruction date
    # is within one calendar day, which absorbs weekend/holiday alignment.
    recon_last_date = pd.Timestamp(recon_window["date"].iloc[-1])
    total_span_days = max((as_of_ts - anchor_date).days, 1)
    covered_days = (recon_last_date - anchor_date).days
    recon_reaches_as_of = (as_of_ts - recon_last_date).days <= 1

    if recon_reaches_as_of:
        # Regime 1: scale so the recon endpoint lands exactly on target_val.
        target_mtd_for_recon = target_mtd
        append_endpoint = False
    else:
        # Regime 2: scale so the recon endpoint sits on the geometric
        # interpolation between anchor (t=0) and target (t=total_span_days).
        # If the target return is negative beyond -100% we bail out (this
        # also defends against domain errors raising real numbers to a
        # non-integer power).
        if (1.0 + target_mtd) <= 0:
            return _single_endpoint_fallback()
        target_mtd_for_recon = ((1.0 + target_mtd) ** (covered_days / total_span_days)) - 1.0
        append_endpoint = True

    s = ((1.0 + target_mtd_for_recon) / (1.0 + recon_mtd)) ** (1.0 / n_days)
    step_powers = s ** np.arange(1, n_days + 1)
    adjusted_factor = cumulative_factor * step_powers
    new_values = anchor_val * adjusted_factor

    new_dates = list(recon_window["date"].values)
    new_vals = list(np.round(new_values, 4))
    if append_endpoint:
        new_dates.append(as_of_ts)
        new_vals.append(round(target_val, 4))

    new_rows = pd.DataFrame({"date": new_dates, "portfolio_value": new_vals})

    extended = pd.concat([portfolio_df, new_rows], ignore_index=True)
    extended = extended.drop_duplicates(subset="date", keep="last")
    extended = extended.sort_values("date").reset_index(drop=True)
    return extended


def get_partial_month_status(portfolio_df, mtd_return_pct, as_of_date):
    """Diagnose what the partial-month extender is doing for the current inputs.

    Returns a dict suitable for rendering a one-line status caption in the
    Update Portfolio Data expander. Fields: mode (str), detail (str),
    recon_last (date or None).
    """
    if mtd_return_pct is None or as_of_date is None:
        return {"mode": "none", "detail": "No MTD return entered.", "recon_last": None}
    as_of_ts = pd.Timestamp(as_of_date)
    last_date = portfolio_df["date"].iloc[-1] if not portfolio_df.empty else None
    if last_date is not None and as_of_ts <= last_date:
        return {"mode": "noop", "detail": "As-of date is not after the series last date.", "recon_last": None}
    recon_df = load_reconstruction_data()
    if recon_df is None:
        return {
            "mode": "single_endpoint",
            "detail": "Reconstruction CSV not found. Falling back to single endpoint.",
            "recon_last": None,
        }
    recon_last_csv = pd.Timestamp(recon_df["date"].iloc[-1])

    if (as_of_ts - recon_last_csv).days <= 1:
        return {
            "mode": "daily_shape_full",
            "detail": (
                f"Reconstruction covers through {recon_last_csv.strftime('%b %d, %Y')}. "
                f"Daily shape used for the full open month."
            ),
            "recon_last": recon_last_csv.date(),
        }

    # Recon is stale relative to the as-of date. See if we can extend it
    # via Yahoo using the current allocation.
    weights_dict = current_allocation_weights()
    if weights_dict is not None:
        recon_last_value = float(recon_df["portfolio_value"].iloc[-1])
        extension_df, ext_msg = extend_reconstruction_via_yahoo(
            recon_last_csv.strftime("%Y-%m-%d"),
            as_of_ts.strftime("%Y-%m-%d"),
            recon_last_value,
            tuple(weights_dict.keys()),
            tuple(weights_dict.values()),
        )
        if not extension_df.empty:
            ext_last = pd.Timestamp(extension_df["date"].iloc[-1])
            tickers_used = ", ".join(weights_dict.keys())
            if (as_of_ts - ext_last).days <= 1:
                return {
                    "mode": "daily_shape_full_via_yahoo",
                    "detail": (
                        f"Recon CSV covers through {recon_last_csv.strftime('%b %d, %Y')}; "
                        f"the gap to {as_of_ts.strftime('%b %d, %Y')} is extended in-dashboard "
                        f"using Yahoo closes weighted by the current allocation ({tickers_used}). "
                        f"{ext_msg}."
                    ),
                    "recon_last": ext_last.date(),
                }
            return {
                "mode": "daily_shape_partial_via_yahoo",
                "detail": (
                    f"Recon CSV covers through {recon_last_csv.strftime('%b %d, %Y')}; "
                    f"in-dashboard Yahoo extension reaches {ext_last.strftime('%b %d, %Y')}. "
                    f"Single endpoint added for the remaining {(as_of_ts - ext_last).days} day(s). "
                    f"{ext_msg}."
                ),
                "recon_last": ext_last.date(),
            }
        # Yahoo extension was attempted but failed; ext_msg explains why.
        return {
            "mode": "daily_shape_partial",
            "detail": (
                f"Recon CSV covers through {recon_last_csv.strftime('%b %d, %Y')}; "
                f"as-of date is {as_of_ts.strftime('%b %d, %Y')}. "
                f"Yahoo extension was attempted but failed: {ext_msg}. "
                f"Falling back to daily shape through the recon's last date plus a single endpoint "
                f"for the remaining {(as_of_ts - recon_last_csv).days} day(s)."
            ),
            "recon_last": recon_last_csv.date(),
        }

    return {
        "mode": "daily_shape_partial",
        "detail": (
            f"Recon covers through {recon_last_csv.strftime('%b %d, %Y')}; "
            f"the as-of date is {as_of_ts.strftime('%b %d, %Y')}. Daily shape used through the "
            f"recon's last date, single endpoint added for the remaining "
            f"{(as_of_ts - recon_last_csv).days} day(s)."
        ),
        "recon_last": recon_last_csv.date(),
    }


def render_update_section(portfolio_df):
    """Render the partial-month update controls and pipeline instructions."""
    last_date = portfolio_df["date"].iloc[-1]
    last_value = float(portfolio_df["portfolio_value"].iloc[-1])
    days_stale = (local_now().date() - last_date.date()).days

    # Decide which workflow the user is likely going to need based on the
    # calendar. If a full calendar month has elapsed since the last data
    # point, recommend Workflow 2 (permanent pipeline refresh). Otherwise
    # the open month is still in progress and Workflow 1 (quick MTD extend)
    # is the typical move. This is a soft recommendation, not a hard rule.
    today = local_now().date()
    last_ym = last_date.year * 12 + last_date.month
    today_ym = today.year * 12 + today.month
    recommend_workflow_2 = today_ym > last_ym

    with st.expander("Update Portfolio Data", expanded=False):

        # ---------------- Current status ----------------
        st.markdown(
            f"<p style='color:{TEXT_PRIMARY}; font-size:0.95rem; font-weight:600; "
            f"margin-bottom:0.25rem;'>Current status</p>"
            f"<p style='color:{TEXT_SECONDARY}; font-size:0.9rem; line-height:1.6; margin-bottom:1rem;'>"
            f"Series runs through <b>{last_date.strftime('%B %d, %Y')}</b> "
            f"(${last_value:,.2f}), {days_stale} day{'s' if days_stale != 1 else ''} ago. "
            f"Today is {today.strftime('%B %d, %Y')}."
            f"</p>",
            unsafe_allow_html=True,
        )

        # ---------------- Which workflow? ----------------
        if recommend_workflow_2:
            rec_text = (
                "A full calendar month has passed since the series was last updated, so "
                "<b>Workflow 2 (permanent pipeline refresh)</b> is the typical next step. "
                "Run it once to lock the now-closed month into the CSV, then resume "
                "Workflow 1 for the new open month."
            )
        else:
            rec_text = (
                "The current calendar month is still in progress, so "
                "<b>Workflow 1 (quick MTD extend)</b> is the typical next step. "
                "It is display-only and takes about 30 seconds."
            )

        st.markdown(
            f"<div style='background-color:#f7f5fb; border-left:3px solid {BRAND_PURPLE}; "
            f"padding:10px 14px; border-radius:4px; margin-bottom:1.25rem;'>"
            f"<p style='color:{TEXT_PRIMARY}; font-size:0.88rem; line-height:1.6; margin:0;'>"
            f"<b>Recommendation.</b> {rec_text}"
            f"</p></div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            f"<p style='color:{TEXT_PRIMARY}; font-size:0.95rem; font-weight:600; "
            f"margin-bottom:0.5rem;'>Which workflow do I need?</p>"
            f"<p style='color:{TEXT_SECONDARY}; font-size:0.88rem; line-height:1.7; margin-bottom:1.25rem;'>"
            f"<b>Workflow 1 (quick, display-only).</b> Use this any time you want the dashboard "
            f"to reflect the latest current-month return while the month is still in progress. "
            f"It uses the close-only daily reconstruction to draw the open month's daily shape, "
            f"chained to your MTD return on the as-of date, and does not modify any files.<br><br>"
            f"<b>Workflow 2 (permanent, full refresh).</b> Use this once a month, after a month "
            f"closes and Fidelity has finalized that month's return. It rebuilds the CSV from "
            f"your Fidelity transactions, locking the closed month into the data permanently. "
            f"After running it, you go back to Workflow 1 for the next open month."
            f"</p>",
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # ---------------- Workflow 1 ----------------
        st.markdown(
            f"<p style='color:{TEXT_PRIMARY}; font-size:1rem; font-weight:700; "
            f"margin-bottom:0.25rem;'>Workflow 1. Quick update during an open month</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<ol style='color:{TEXT_SECONDARY}; font-size:0.9rem; line-height:1.8; "
            f"padding-left:1.3rem; margin-bottom:0.75rem;'>"
            f"<li>Open Fidelity and go to the <b>Performance</b> tab.</li>"
            f"<li>Hover the <b>Current Month</b> bar in the returns chart. Note the "
            f"<b>MTD return percentage</b> and the <b>date it is current through</b>.</li>"
            f"<li>Enter both values in the form below. Refresh the page if the charts "
            f"do not update automatically.</li>"
            f"<li>Confirm the status line at the top of this expander now shows your "
            f"as-of date. Spot-check the Performance Comparison chart's MTD bar.</li>"
            f"<li><b>Manually update the End date on the Performance Summary table.</b> "
            f"The date picker at the top of the dashboard does not auto-advance when the "
            f"series is extended. Change it to your new as-of date so the summary metrics "
            f"reflect the latest range.</li>"
            f"</ol>",
            unsafe_allow_html=True,
        )

        col_a, col_b = st.columns([1, 1])
        with col_a:
            mtd_return = st.number_input(
                "MTD return (%)",
                value=None,
                format="%.4f",
                key="upd_mtd_return",
                placeholder="e.g. 2.32",
                help="Month-to-date pre-tax return from Fidelity's Performance tab. "
                     "Leave empty after a full pipeline rebuild. Enter a value only for a quick partial-month extend between rebuilds.",
            )
        with col_b:
            as_of = st.date_input(
                "As-of date",
                value=local_now().date(),
                key="upd_as_of",
                help="The date the MTD return is current through.",
            )

        # One-line indicator of what the partial-month extender is doing
        # for the current MTD / as-of inputs. The mode determines whether
        # the dashboard draws a full daily curve, a partial daily curve
        # with a short straight segment, or a single endpoint.
        _status = get_partial_month_status(portfolio_df, mtd_return, as_of)
        _status_color_map = {
            "daily_shape_full": "#14543E",
            "daily_shape_full_via_yahoo": "#14543E",
            "daily_shape_partial": "#7E4A0A",
            "daily_shape_partial_via_yahoo": "#7E4A0A",
            "single_endpoint": "#7E4A0A",
            "noop": TEXT_SECONDARY,
            "none": TEXT_SECONDARY,
        }
        _status_bg_map = {
            "daily_shape_full": "#D6E8DF",
            "daily_shape_full_via_yahoo": "#D6E8DF",
            "daily_shape_partial": "#F4E5C5",
            "daily_shape_partial_via_yahoo": "#F4E5C5",
            "single_endpoint": "#F4E5C5",
            "noop": "#f5f5f5",
            "none": "#f5f5f5",
        }
        _bg = _status_bg_map.get(_status["mode"], "#f5f5f5")
        _fg = _status_color_map.get(_status["mode"], TEXT_SECONDARY)
        st.markdown(
            f"<div style='margin-top:8px; padding:8px 12px; background-color:{_bg}; "
            f"color:{_fg}; border-radius:6px; font-size:0.85rem;'>"
            f"<b>Partial-month extension:</b> {_status['detail']}</div>",
            unsafe_allow_html=True,
        )

        st.caption(
            "This stores values in browser session state only. The underlying CSV is "
            "untouched. Clear the MTD return field to remove the extension."
        )

        st.markdown("---")

        # ---------------- Workflow 2 ----------------
        st.markdown(
            f"<p style='color:{TEXT_PRIMARY}; font-size:1rem; font-weight:700; "
            f"margin-bottom:0.25rem;'>Workflow 2. Permanent monthly refresh after a month closes</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<p style='color:{TEXT_SECONDARY}; font-size:0.88rem; line-height:1.7; margin-bottom:0.75rem;'>"
            f"Run this once after each calendar month ends, as soon as Fidelity finalizes that "
            f"month's return (usually within a day or two of month-end). This rebuilds the daily "
            f"series and chains it to Fidelity's official monthly figures."
            f"</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<ol style='color:{TEXT_SECONDARY}; font-size:0.9rem; line-height:1.8; "
            f"padding-left:1.3rem; margin-bottom:0.5rem;'>"
            f"<li><b>Export fresh transaction history if any trades happened.</b> "
            f"If there were any trades during the closed month, log into Fidelity, "
            f"export the latest transaction history, and replace "
            f"<code>History_for_Account_Z27314115.csv</code> in the pipeline folder. "
            f"If no trades happened, skip this step.</li>"
            f"<li><b>Read the closed month's finalized return.</b> "
            f"In Fidelity's Performance tab, hover that month's bar in the returns chart "
            f"to see its total return percentage.</li>"
            f"<li><b>Decide the as-of date.</b> Use the last calendar day of the closed "
            f"month (e.g. <code>2026-05-31</code> for May 2026). Weekends and holidays are "
            f"fine, the pipeline falls back to the most recent trading day automatically.</li>"
            f"<li><b>Open PowerShell in the pipeline folder and run the two commands below</b>, "
            f"replacing <code>&lt;return-percent&gt;</code> with the return from step 2 (no "
            f"percent sign) and <code>&lt;as-of-date&gt;</code> with the date from step 3.</li>"
            f"</ol>",
            unsafe_allow_html=True,
        )
        st.code(
            'cd "C:\\Users\\tyler\\OneDrive\\PROJECTS\\Strategy Backtesting System\\Portfolio Hist Val Reconstruction"\n'
            "python portfolio_valuation.py History_for_Account_Z27314115.csv <as-of-date>\n"
            "python build_anchored_series.py . <return-percent> <as-of-date>",
            language="powershell",
        )
        st.markdown(
            f"<p style='color:{TEXT_SECONDARY}; font-size:0.85rem; "
            f"margin-top:0.75rem; margin-bottom:0.25rem;'>"
            f"<b>Filled-in example</b> (drop the angle brackets and the percent sign; "
            f"PowerShell reads <code>&lt;</code> and <code>&gt;</code> as input/output "
            f"redirection, and <code>%</code> confuses the parser):</p>",
            unsafe_allow_html=True,
        )
        st.code(
            'cd "C:\\Users\\tyler\\OneDrive\\PROJECTS\\Strategy Backtesting System\\Portfolio Hist Val Reconstruction"\n'
            "python portfolio_valuation.py History_for_Account_Z27314115.csv 2026-05-26\n"
            "python build_anchored_series.py . 5.28 2026-05-26",
            language="powershell",
        )
        st.markdown(
            f"<p style='color:{TEXT_SECONDARY}; font-size:0.85rem; "
            f"margin-top:0.75rem; margin-bottom:0.25rem;'>"
            f"<b>Negative returns:</b> if the closed month was down, just type the minus "
            f"sign, e.g. <code>python build_anchored_series.py . -2.45 2026-05-31</code>. "
            f"The script reads the return straight from the command line, so the leading "
            f"minus is treated as part of the number, not a flag. No quotes or extra "
            f"characters are needed.</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<ol start='5' style='color:{TEXT_SECONDARY}; font-size:0.9rem; line-height:1.8; "
            f"padding-left:1.3rem; margin-top:0.5rem;'>"
            f"<li><b>Clear the Workflow 1 form above.</b> If you previously entered an "
            f"MTD return for what is now the closed month, delete it. Otherwise the partial-month "
            f"extension will sit on top of the finalized month and double-count it.</li>"
            f"<li><b>Refresh the dashboard page.</b> Confirm the status line at the top of "
            f"this expander shows the new last date (the as-of date from step 3).</li>"
            f"<li><b>Spot-check the charts.</b> Open the Performance Comparison and Portfolio "
            f"Growth charts. The newly-closed month should appear in the data, and the all-time "
            f"figures should now include it.</li>"
            f"<li><b>Manually update the End date on the Performance Summary table.</b> "
            f"The date picker at the top of the dashboard does not auto-advance. Change it "
            f"to your new as-of date so the summary metrics reflect the latest range.</li>"
            f"</ol>",
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # ---------------- Things to watch for ----------------
        st.markdown(
            f"<p style='color:{TEXT_PRIMARY}; font-size:1rem; font-weight:700; "
            f"margin-bottom:0.25rem;'>Things to watch for</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<ul style='color:{TEXT_SECONDARY}; font-size:0.88rem; line-height:1.7; "
            f"padding-left:1.3rem; margin-bottom:0;'>"
            f"<li><b>The MTD return and as-of date must match.</b> If Fidelity says the return "
            f"is current through May 15, enter May 15 as the as-of date, not today's date. "
            f"Mismatched dates produce a misleading partial month.</li>"
            f"<li><b>The Performance Summary End date does not auto-advance.</b> After updating "
            f"the data, manually change the End date picker on the table at the top of the "
            f"dashboard. Otherwise the summary metrics will keep using the previous end date "
            f"even though the charts below have moved forward.</li>"
            f"<li><b>Always clear the Workflow 1 form after running Workflow 2.</b> A leftover "
            f"MTD value will be applied on top of the freshly-rebuilt CSV and inflate the values.</li>"
            f"<li><b>Weekend and holiday as-of dates are fine.</b> The pipeline uses the most "
            f"recent trading day's close, which is the standard behavior.</li>"
            f"<li><b>No file copying is needed.</b> The dashboard reads "
            f"<code>asymmetric_edge_series.csv</code> directly from the pipeline folder. "
            f"Just refresh the browser page after running the pipeline.</li>"
            f"<li><b>The MTD return is pre-tax, time-weighted.</b> That is Fidelity's default "
            f"on the Performance tab. Do not switch to an after-tax or money-weighted view.</li>"
            f"</ul>",
            unsafe_allow_html=True,
        )

    return mtd_return, as_of



# ---------- HGER look-through (Quantix Commodity Index sector weights) ----------
# HGER tracks the Quantix Commodity Index (QCI). Harbor publishes the index's
# daily sector weights on the HGER fund page, no sign-in required. The page is
# a static Gatsby build, so the same data is also served as structured JSON at
# HGER_PAGE_DATA_URL, which is read first. If that fails, the rendered table on
# the HTML page is parsed instead. If both fail, the most recent saved snapshot
# is shown with a warning. Every successful fetch is saved to qci_snapshots\
# beside app.py, so a history of as-of dates builds up over time (Harbor only
# publishes the current day).
#
# QCI rebalances quarterly, phased in over business days 5 to 9 of the month
# after quarter end, and rolls contracts monthly in the same window. Between
# rebalances the sector mix moves only with prices.

HGER_PAGE_URL = "https://www.harborcapital.com/etf/hger/"
HGER_PAGE_DATA_URL = "https://www.harborcapital.com/page-data/etf/hger/page-data.json"
QCI_SNAPSHOT_DIR_NAME = "qci_snapshots"

# Harbor sector name -> (display name, emoji). An unknown sector still shows,
# under a cleaned-up version of Harbor's name, and is flagged on the page so
# the map can be extended.
QCI_SECTOR_DISPLAY = {
    "Petroleum": ("Petroleum", "\U0001F6E2️"),
    "Precious": ("Precious Metals", "\U0001F7E8"),  # shown as "Gold" when gold is the only holding
    "Grains And Soybean Products": ("Grains", "\U0001F33E"),
    "Softs": ("Softs", "☕"),
    "Industrial": ("Industrial Metals", "\U0001F529"),
    "LivestockAndDairy": ("Livestock", "\U0001F416"),
    "Natural Gas": ("Natural Gas", "\U0001F525"),
    "Energy": ("Energy", "⚡"),
}
QCI_UNMAPPED_EMOJI = "◻️"

# Harbor commodity name -> display name, in the order "What it holds" lists
# them. Contract months and duplicate names (Wheat and Kansas Wheat) collapse
# to one entry. Unknown commodities are lowercased and listed after the known ones.
QCI_COMMODITY_DISPLAY = [
    ("Brent Crude Oil", "Brent crude"),
    ("WTI Crude Oil", "WTI crude"),
    ("Crude Oil", "WTI crude"),
    ("Gasoil", "gasoil"),
    ("RBOB Gasoline", "gasoline"),
    ("Heating Oil", "heating oil"),
    ("Natural Gas", "natural gas"),
    ("Gold", "gold"),
    ("Silver", "silver"),
    ("Platinum", "platinum"),
    ("Palladium", "palladium"),
    ("Corn", "corn"),
    ("Wheat", "wheat"),
    ("Kansas Wheat", "wheat"),
    ("Soybeans", "soybeans"),
    ("Soymeal", "soymeal"),
    ("Bean Oil", "bean oil"),
    ("Cocoa", "cocoa"),
    ("Sugar", "sugar"),
    ("Coffee", "coffee"),
    ("Cotton", "cotton"),
    ("Comex Copper", "copper"),
    ("Copper", "copper"),
    ("Zinc", "zinc"),
    ("Aluminum", "aluminum"),
    ("Nickel", "nickel"),
    ("Lead", "lead"),
    ("Tin", "tin"),
    ("Lean Hogs", "lean hogs"),
    ("Live Cattle", "live cattle"),
    ("Feeder Cattle", "feeder cattle"),
]


def _find_json_key(obj, key):
    """Depth-first search for the first value stored under key."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found = _find_json_key(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_json_key(value, key)
            if found is not None:
                return found
    return None


def _qci_validated(rows, as_of, source):
    """Return the parsed payload only if the weights add up to about 100%."""
    if not rows or not as_of:
        return None
    total = sum(r["weight"] for r in rows)
    if not 95.0 <= total <= 105.0:
        return None
    return {"as_of": as_of, "rows": rows, "source": source,
            "fetched_at": local_now().strftime("%Y-%m-%d %H:%M")}


def _qci_from_page_data(payload):
    """Parse Harbor's page-data JSON (weights there are fractions of 1)."""
    sectors = _find_json_key(payload, "etfCommodityIndexSectors")
    if not sectors:
        return None
    rows, as_of = [], None
    for sector in sectors:
        as_of = as_of or str(sector.get("calendarDate") or "")[:10]
        for c in sector.get("commodities") or []:
            rows.append({
                "ticker": str(c.get("ticker") or "").strip(),
                "sector": str(sector.get("sectorName") or "").strip(),
                "commodity": str(c.get("commodityName") or "").strip(),
                "facility": str(c.get("tradingFacility") or "").strip(),
                "weight": float(c.get("weight") or 0) * 100.0,
            })
    return _qci_validated(rows, as_of, "Harbor page data")


def _qci_from_html(html):
    """Fallback: parse the rendered sector weights table on the HGER page.

    The table renders as a flat run of <div> cells, five per contract:
    ticker, sector, commodity, facility, weight (already in percent).
    """
    import re
    start = html.find("Daily Commodity Sector Weights")
    if start < 0:
        return None
    segment = html[start:start + 80000]
    m = re.search(r"As of\s*(\d{1,2})/(\d{1,2})/(\d{4})", segment)
    header_end = segment.find("Daily Weight (%)")
    if not m or header_end < 0:
        return None
    as_of = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    cells = [t.strip() for t in re.findall(r"<div[^>]*>([^<]+)</div>", segment[header_end:])]
    rows = []
    for i in range(0, len(cells) - 4, 5):
        ticker, sector, commodity, facility, weight = cells[i:i + 5]
        try:
            weight_val = float(weight)
        except ValueError:
            break
        rows.append({"ticker": ticker, "sector": sector, "commodity": commodity,
                     "facility": facility, "weight": weight_val})
    return _qci_validated(rows, as_of, "Harbor HGER page table")


def _http_text(url):
    """GET a page as text, preferring curl_cffi's browser impersonation."""
    try:
        from curl_cffi import requests as cffi_requests
        r = cffi_requests.get(url, impersonate="chrome", timeout=20)
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    try:
        import requests as _requests
        r = _requests.get(url, timeout=20, headers={"User-Agent": _BROWSER_UA})
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_qci_weights():
    """Fetch the latest QCI sector weights from Harbor.

    Raises on failure so Streamlit does not cache a miss for six hours.
    """
    payload = _http_json(HGER_PAGE_DATA_URL, None)
    data = _qci_from_page_data(payload) if payload else None
    if data is None:
        html = _http_text(HGER_PAGE_URL)
        data = _qci_from_html(html) if html else None
    if data is None:
        raise RuntimeError("Harbor QCI sector weights unavailable")
    return data


def _qci_snapshot_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), QCI_SNAPSHOT_DIR_NAME)


def save_qci_snapshot(data):
    """Save one snapshot per as-of date. Never overwrites, never raises."""
    try:
        folder = _qci_snapshot_dir()
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"qci_sector_weights_{data['as_of']}.json")
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
    except Exception:
        pass


def list_qci_snapshots():
    """Return {as_of: path} for saved snapshots, newest first."""
    folder = _qci_snapshot_dir()
    found = {}
    try:
        for name in os.listdir(folder):
            if name.startswith("qci_sector_weights_") and name.endswith(".json"):
                found[name[len("qci_sector_weights_"):-5]] = os.path.join(folder, name)
    except OSError:
        return {}
    return dict(sorted(found.items(), reverse=True))


def load_qci_snapshot(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def summarize_qci_sectors(data):
    """Group contract-level weights into display sectors.

    Returns (sector_rows, n_commodities, unmapped_sectors). sector_rows is
    sorted largest weight first. Nothing is dropped: an unknown sector or
    commodity still shows and still counts toward the total.
    """
    import re
    order = {src: i for i, (src, _) in enumerate(QCI_COMMODITY_DISPLAY)}
    names = dict(QCI_COMMODITY_DISPLAY)
    by_sector = {}
    for r in data["rows"]:
        by_sector.setdefault(r["sector"], []).append(r)

    sector_rows, unmapped = [], []
    for sector, rows in by_sector.items():
        display, emoji = QCI_SECTOR_DISPLAY.get(sector, (None, None))
        if display is None:
            unmapped.append(sector)
            display = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", sector).strip() or "Other"
            emoji = QCI_UNMAPPED_EMOJI
        ranked = sorted(rows, key=lambda r: (order.get(r["commodity"], len(order)), -r["weight"]))
        held = []
        for r in ranked:
            label = names.get(r["commodity"], r["commodity"].lower())
            if label not in held:
                held.append(label)
        if sector == "Precious" and held == ["gold"]:
            display, holds = "Gold", "Gold futures"
        else:
            holds = ", ".join(held)
            holds = holds[:1].upper() + holds[1:]
        sector_rows.append({
            "sector": display, "emoji": emoji, "holds": holds,
            "weight": sum(r["weight"] for r in rows),
        })
    sector_rows.sort(key=lambda s: -s["weight"])
    n_commodities = len({r["commodity"] for r in data["rows"]})
    return sector_rows, n_commodities, unmapped


def _rounded_bar_path(x0, x1, y_mid, height):
    """SVG path for a pill-shaped bar (fully rounded ends)."""
    r = height / 2
    if x1 - x0 < height:
        x1 = x0 + height
    y0, y1 = y_mid - r, y_mid + r
    return (f"M {x0 + r},{y0} L {x1 - r},{y0} Q {x1},{y0} {x1},{y_mid} "
            f"Q {x1},{y1} {x1 - r},{y1} L {x0 + r},{y1} Q {x0},{y1} {x0},{y_mid} "
            f"Q {x0},{y0} {x0 + r},{y0} Z")


def build_qci_sector_table(sector_rows, n_commodities):
    """Plotly figure of the HGER look-through table, drawn in pixel coordinates
    (like the Asset Universe grid) so the PNG export matches the screen.

    Columns: Sector (emoji + name), What it holds, a weight bar scaled to the
    largest sector, and the weight. A Total row closes the table.
    """
    WIDTH = 860
    HEADER_H = 46
    ROW_H = 48
    TOTAL_H = 48
    SECTOR_X = 18
    HOLDS_X = 240
    BAR_X0, BAR_X1 = 610, 742
    WEIGHT_X = WIDTH - 18
    BAR_H = 11
    BAR_FILL = "#4F2DB8"
    BAR_TRACK = "#ECECF1"
    RULE = "#E5E7EB"
    HEADER_BG = "#F9FAFB"
    font_family = "DM Sans, sans-serif"

    n = len(sector_rows)
    HEIGHT = HEADER_H + n * ROW_H + TOTAL_H
    shapes, annotations = [], []

    def text(x, y, value, anchor="left", size=16, color=TEXT_PRIMARY, bold=False):
        annotations.append(dict(
            x=x, y=y, xref="x", yref="y", xanchor=anchor, yanchor="middle",
            text=f"<b>{value}</b>" if bold else value, showarrow=False,
            font=dict(family=font_family, size=size, color=color),
        ))

    # Header band and its Deep Purple underline
    shapes.append(dict(type="rect", x0=0, x1=WIDTH, y0=0, y1=HEADER_H,
                       fillcolor=HEADER_BG, line_width=0, layer="below"))
    shapes.append(dict(type="line", x0=0, x1=WIDTH, y0=HEADER_H, y1=HEADER_H,
                       line=dict(color=BRAND_PURPLE, width=2)))
    header_y = HEADER_H / 2
    text(SECTOR_X, header_y, "Sector", size=17, bold=True)
    text(HOLDS_X, header_y, "What it holds", size=17, bold=True)
    text(WEIGHT_X, header_y, "Weight", anchor="right", size=17, bold=True)

    max_weight = max((s["weight"] for s in sector_rows), default=1.0) or 1.0
    for i, s in enumerate(sector_rows):
        top = HEADER_H + i * ROW_H
        mid = top + ROW_H / 2
        if i > 0:
            shapes.append(dict(type="line", x0=0, x1=WIDTH, y0=top, y1=top,
                               line=dict(color=RULE, width=1)))
        text(SECTOR_X, mid, f"{s['emoji']}  {s['sector']}")
        text(HOLDS_X, mid, s["holds"], color=TEXT_SECONDARY)
        shapes.append(dict(type="path", path=_rounded_bar_path(BAR_X0, BAR_X1, mid, BAR_H),
                           fillcolor=BAR_TRACK, line_width=0, layer="below"))
        fill_x1 = BAR_X0 + (BAR_X1 - BAR_X0) * (s["weight"] / max_weight)
        shapes.append(dict(type="path", path=_rounded_bar_path(BAR_X0, fill_x1, mid, BAR_H),
                           fillcolor=BAR_FILL, line_width=0))
        text(WEIGHT_X, mid, _pct1(s["weight"]), anchor="right")

    total_top = HEADER_H + n * ROW_H
    shapes.append(dict(type="rect", x0=0, x1=WIDTH, y0=total_top, y1=HEIGHT,
                       fillcolor=HEADER_BG, line_width=0, layer="below"))
    shapes.append(dict(type="line", x0=0, x1=WIDTH, y0=total_top, y1=total_top,
                       line=dict(color=RULE, width=1)))
    total_mid = total_top + TOTAL_H / 2
    noun = "commodity" if n_commodities == 1 else "commodities"
    sec_noun = "sector" if n == 1 else "sectors"
    text(SECTOR_X, total_mid, "Total", bold=True)
    text(HOLDS_X, total_mid, f"{n_commodities} {noun} across {n} {sec_noun}", color=TEXT_SECONDARY)
    text(WEIGHT_X, total_mid, _pct1(sum(s["weight"] for s in sector_rows)), anchor="right", bold=True)

    fig = go.Figure()
    fig.update_layout(
        **DARK_LAYOUT,
        width=WIDTH, height=HEIGHT,
        margin=dict(t=0, b=0, l=0, r=0),
        xaxis=dict(range=[0, WIDTH], visible=False, fixedrange=True),
        yaxis=dict(range=[HEIGHT, 0], visible=False, fixedrange=True),
        shapes=shapes, annotations=annotations, showlegend=False,
    )
    return fig


def _hger_is_held(current_alloc_rows):
    """True when HGER is in the current allocation or the saved next allocation."""
    tickers = {str(r.get("ticker", "")).upper() for r in (current_alloc_rows or [])}
    tickers |= {str(r.get("ticker", "")).upper() for r in load_next_allocation()}
    return "HGER" in tickers


def render_hger_lookthrough_section():
    st.markdown("## What HGER Holds")

    live, live_error = None, False
    try:
        live = fetch_qci_weights()
        save_qci_snapshot(live)
    except Exception:
        live_error = True

    snapshots = list_qci_snapshots()
    data = live
    if snapshots and (len(snapshots) > 1 or live is None):
        dates = list(snapshots.keys())
        default = dates.index(live["as_of"]) if live and live["as_of"] in dates else 0
        pick = st.selectbox(
            "As of", dates, index=default, key="qci_as_of",
            format_func=lambda d: datetime.strptime(d, "%Y-%m-%d").strftime("%b %d, %Y"),
        )
        if live is None or pick != live["as_of"]:
            data = load_qci_snapshot(snapshots[pick])

    if data is None:
        st.error(
            "HGER sector weights unavailable. Harbor's HGER page could not be reached or "
            f"its layout changed, and no saved snapshot exists yet. Source page: {HGER_PAGE_URL}"
        )
        return
    if live_error:
        st.warning(
            "Could not reach Harbor just now, so this shows the most recent saved snapshot. "
            "Check the as-of date before using it in an issue."
        )

    sector_rows, n_commodities, unmapped = summarize_qci_sectors(data)
    as_of_dt = datetime.strptime(data["as_of"], "%Y-%m-%d")
    st.plotly_chart(
        build_qci_sector_table(sector_rows, n_commodities),
        use_container_width=False,
        config=chart_config(f"QCI (HGER) Sector Weights {as_of_dt:%m-%d-%Y}", static=True),
    )
    if unmapped:
        st.warning(
            "New sector name from Harbor, shown under its raw name: "
            + ", ".join(unmapped)
            + ". Add it to QCI_SECTOR_DISPLAY in app.py to give it a display name and emoji."
        )

    footnote = (
        f"Source: Quantix Commodity Index daily holdings as of {as_of_dt:%m/%d/%Y}, the index "
        f"tracked by HGER, grouped by sector. Weights change daily."
    )
    st.markdown(f'<p class="footer-text">{footnote}</p>', unsafe_allow_html=True)
    newsletter_caption(
        f"Sector weights of the Quantix Commodity Index, which broad commodities (HGER) tracks, "
        f"as of {_cap_date(as_of_dt)}. Source: Harbor Capital. Weights change daily."
    )

    if st.button("Refresh from Harbor", key="qci_refresh"):
        fetch_qci_weights.clear()
        st.rerun()


# ---------- Asset Universe ----------
#
# The asset universe grid lives in a JSON file next to the portfolio CSV.
# The file is created on first save (or first "Reset to Default" click) and
# can be edited either through the in-app editor or directly with a text
# editor. The HTML builder below mirrors the design of the original
# Asset Universe Grid HTML used on the Ghost site: a 130px category label
# on the left, color-coded asset cards on the right, with `flex: 1` on the
# cards so they expand or contract automatically when assets are added or
# removed. Single-asset rows are constrained to 50% width so a lone card
# doesn't look stretched.

ASSET_UNIVERSE_PATH = os.path.join(SCRIPT_DIR, "asset_universe.json")

DEFAULT_ASSET_UNIVERSE = {
    "categories": [
        {
            "name": "U.S. equities",
            "visible": True,
            "color_bg": "#DCE7F4",
            "color_text": "#1F4D87",
            "assets": [
                {"name": "Nasdaq-100", "ticker": "QQQ"},
                {"name": "Russell 2000", "ticker": "IWM"},
            ],
        },
        {
            "name": "International",
            "visible": True,
            "color_bg": "#D6E8DF",
            "color_text": "#14543E",
            "assets": [
                {"name": "Japan", "ticker": "DXJ"},
                {"name": "Emerging Mkts", "ticker": "EMXC"},
            ],
        },
        {
            "name": "Commodities",
            "visible": True,
            "color_bg": "#F4E5C5",
            "color_text": "#7E4A0A",
            "assets": [
                {"name": "Gold", "ticker": "GLD"},
                {"name": "Broad commodities", "ticker": "HGER"},
            ],
        },
        {
            "name": "Crypto",
            "visible": True,
            "color_bg": "#FCE3CF",
            "color_text": "#A84E08",
            "assets": [
                {"name": "Bitcoin", "ticker": "IBIT"},
            ],
        },
        {
            "name": "Defensive",
            "visible": True,
            "color_bg": "#E8E4DA",
            "color_text": "#4A463D",
            "assets": [
                {"name": "Defensive equity", "ticker": "BTAL"},
                {"name": "Cash T-Bills", "ticker": "BIL"},
                {"name": "Long Treasuries", "ticker": "TLT"},
            ],
        },
    ]
}


def load_asset_universe():
    """Load the asset universe JSON. Fall back to DEFAULT_ASSET_UNIVERSE if missing or invalid."""
    if not os.path.exists(ASSET_UNIVERSE_PATH):
        return DEFAULT_ASSET_UNIVERSE
    try:
        with open(ASSET_UNIVERSE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("categories"), list):
            return DEFAULT_ASSET_UNIVERSE
        return data
    except (json.JSONDecodeError, OSError):
        return DEFAULT_ASSET_UNIVERSE


def save_asset_universe(universe):
    """Persist the asset universe to JSON."""
    with open(ASSET_UNIVERSE_PATH, "w", encoding="utf-8") as f:
        json.dump(universe, f, indent=2)


def build_asset_universe_html(universe):
    """Render the asset universe grid as inline-styled HTML.

    Categories with no assets are skipped silently so a half-edited row
    doesn't produce an empty stripe. Within a row, cards use flex: 1
    so they share width evenly regardless of how many there are.
    """
    categories = [
        c for c in universe.get("categories", [])
        if c.get("assets") and c.get("visible", True)
    ]
    n_cats = len(categories)
    rows_html = []

    for i, cat in enumerate(categories):
        is_last = (i == n_cats - 1)
        margin = "" if is_last else "margin-bottom: 12px;"

        bg = cat.get("color_bg", "#E8E4DA")
        txt = cat.get("color_text", "#4A463D")
        cat_name = cat.get("name", "")

        assets = cat.get("assets", [])
        n_assets = len(assets)
        cards = []
        for asset in assets:
            name = asset.get("name", "")
            ticker = asset.get("ticker", "")
            # Single-card rows take half the row so they don't look stretched
            extra = "max-width: calc(50% - 6px); " if n_assets == 1 else ""
            cards.append(
                f'<div style="flex: 1; {extra}background: {bg}; border-radius: 8px; '
                f'padding: 14px 16px; text-align: center;">'
                f'<div style="font-size: 15px; font-weight: 500; color: {txt}; line-height: 1.3;">{name}</div>'
                f'<div style="font-size: 12px; color: {txt}; opacity: 0.7; margin-top: 4px; letter-spacing: 0.5px;">{ticker}</div>'
                f'</div>'
            )

        rows_html.append(
            f'<div style="display: grid; grid-template-columns: 130px 1fr; gap: 16px; '
            f'align-items: center; {margin}">'
            f'<div style="font-size: 15px; color: #4D4D48;">{cat_name}</div>'
            f'<div style="display: flex; gap: 12px;">{"".join(cards)}</div>'
            f'</div>'
        )

    return (
        f'<div style="max-width: 680px; margin: 16px auto 8px auto; '
        f"font-family: 'DM Sans', sans-serif;\">"
        f'{"".join(rows_html)}'
        f'</div>'
    )


# Asset Universe styling, option B (October 22, 2026). Every card keeps its
# category's pastel fill and dark text. Cards the portfolio holds now add a
# 2 px outline and a weight pill, both in the category's text color, so the
# holdings stand out without a heavy fill. Set UNIVERSE_HIGHLIGHT_HELD to
# False to show every card alike.
UNIVERSE_HIGHLIGHT_HELD = True

# Pills above the grid switch the outlines between the holdings owned now and
# next month's basket from next_allocation.json (October 29, 2026).
UNIVERSE_VIEW_NOW = "Held now"
UNIVERSE_VIEW_NEXT = "Next month"

# Approximate DM Sans advance widths in em, used only to center the ticker
# and weight pill as one group under each held card's name.
_DM_SANS_EM = {".": 0.27, "%": 0.82, " ": 0.25, "-": 0.36}


def _est_text_width(text, size, bold=False):
    w = 0.0
    for ch in str(text):
        if ch in _DM_SANS_EM:
            w += _DM_SANS_EM[ch]
        elif ch.isdigit():
            w += 0.58
        elif ch.isupper():
            w += 0.66
        else:
            w += 0.55
    return w * size * (1.04 if bold else 1.0)


def build_asset_universe_chart(universe, held=None, held_label="Held now, with weight"):
    """Build a Plotly figure that renders the asset universe grid.

    Uses pixel-based coordinates (xaxis 0 to WIDTH, yaxis HEIGHT to 0 so
    y=0 sits at the top) so font sizes, card dimensions, and the rounded-
    corner radius stay consistent between the on-screen render and the PNG
    export from Plotly's toolbar download button.

    Plotly shape rectangles don't natively support rounded corners, so each
    card is drawn as an SVG path with quadratic Bezier curves at the four
    corners. Card backgrounds sit on layer='below' so the text annotations
    render cleanly on top.

    held: optional {ticker: weight percent} for the current allocation. Held
    cards get an outline and a weight pill; see UNIVERSE_HIGHLIGHT_HELD.
    held_label: the key's text for outlined cards. Pass next month's wording
    when held is the upcoming basket rather than the current holdings.
    """
    held = held if (held and UNIVERSE_HIGHLIGHT_HELD) else {}
    categories = [
        c for c in universe.get("categories", [])
        if c.get("assets") and c.get("visible", True)
    ]
    if not categories:
        fig = go.Figure()
        fig.update_layout(
            width=720, height=80,
            paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        )
        return fig

    n_rows = len(categories)

    # All layout constants are in pixels and mirror the HTML version above.
    WIDTH = 720
    LEFT_PAD = 16
    LABEL_WIDTH = 130
    LABEL_GAP = 16
    RIGHT_PAD = 16

    CARD_AREA_LEFT = LEFT_PAD + LABEL_WIDTH + LABEL_GAP
    CARD_AREA_RIGHT = WIDTH - RIGHT_PAD
    CARD_AREA_WIDTH = CARD_AREA_RIGHT - CARD_AREA_LEFT

    ROW_HEIGHT = 58
    ROW_GAP = 12
    CARD_GAP = 12
    CORNER_RADIUS = 8
    TOP_PAD = 4
    BOT_PAD = 4

    OUTLINE_W = 2
    PILL_H = 18
    PILL_PAD_X = 7
    PILL_GAP = 6

    LEGEND_H = 34 if held else 0
    HEIGHT = TOP_PAD + n_rows * ROW_HEIGHT + (n_rows - 1) * ROW_GAP + BOT_PAD + LEGEND_H

    shapes = []
    annotations = []
    font = "DM Sans, sans-serif"

    for i, cat in enumerate(categories):
        row_top = TOP_PAD + i * (ROW_HEIGHT + ROW_GAP)
        row_bottom = row_top + ROW_HEIGHT
        row_center_y = (row_top + row_bottom) / 2

        # Category label, right-aligned against the right edge of the label column
        annotations.append(dict(
            x=LEFT_PAD + LABEL_WIDTH, y=row_center_y,
            text=cat.get("name", ""),
            showarrow=False,
            xanchor="right", yanchor="middle",
            font=dict(size=15, color=TEXT_PRIMARY, family=font, weight=600),
        ))

        assets = cat.get("assets", [])
        n_assets = len(assets)
        txt = cat.get("color_text", "#4A463D")
        bg = cat.get("color_bg", "#E8E4DA")

        # Single-card rows fill half the card area so a lone card doesn't stretch
        if n_assets == 1:
            effective_width = (CARD_AREA_WIDTH - CARD_GAP) / 2
        else:
            effective_width = CARD_AREA_WIDTH

        total_gap = CARD_GAP * (n_assets - 1)
        card_width = (effective_width - total_gap) / n_assets

        for j, asset in enumerate(assets):
            card_left = CARD_AREA_LEFT + j * (card_width + CARD_GAP)
            card_right = card_left + card_width
            ticker = str(asset.get("ticker", "")).strip().upper()
            is_held = ticker in held

            if is_held:
                # Inset by half the stroke so the outline sits inside the card
                # edge, the way a CSS border does.
                h = OUTLINE_W / 2
                shapes.append(dict(
                    type="path",
                    path=_round_rect_path(card_left + h, row_top + h,
                                          card_right - h, row_bottom - h,
                                          CORNER_RADIUS - h),
                    fillcolor=bg, line=dict(color=txt, width=OUTLINE_W),
                    layer="below",
                ))
            else:
                shapes.append(dict(
                    type="path",
                    path=_round_rect_path(card_left, row_top, card_right, row_bottom,
                                          CORNER_RADIUS),
                    fillcolor=bg, line=dict(width=0),
                    layer="below",
                ))

            card_center_x = (card_left + card_right) / 2
            annotations.append(dict(
                x=card_center_x, y=row_center_y - 7,
                text=asset.get("name", ""),
                showarrow=False,
                xanchor="center", yanchor="middle",
                font=dict(size=15, color=txt, family=font, weight=600),
            ))

            sub_y = row_center_y + 13
            if not is_held:
                annotations.append(dict(
                    x=card_center_x, y=sub_y,
                    text=asset.get("ticker", ""),
                    showarrow=False,
                    xanchor="center", yanchor="middle",
                    font=dict(size=12, color=txt, family=font, weight=500),
                ))
                continue

            # Held: ticker, then a pill with the weight, centered as one group.
            weight_txt = f"{held[ticker]:.1f}%"
            tw = _est_text_width(ticker, 12)
            pw = _est_text_width(weight_txt, 12, bold=True) + 2 * PILL_PAD_X
            start = card_center_x - (tw + PILL_GAP + pw) / 2
            annotations.append(dict(
                x=start + tw, y=sub_y,
                text=ticker,
                showarrow=False,
                xanchor="right", yanchor="middle",
                font=dict(size=12, color=txt, family=font, weight=500),
            ))
            px0 = start + tw + PILL_GAP
            px1 = px0 + pw
            shapes.append(dict(
                type="path",
                path=_round_rect_path(px0, sub_y - PILL_H / 2, px1, sub_y + PILL_H / 2,
                                      PILL_H / 2),
                fillcolor=txt, line=dict(width=0),
            ))
            annotations.append(dict(
                x=(px0 + px1) / 2, y=sub_y,
                text=weight_txt,
                showarrow=False,
                xanchor="center", yanchor="middle",
                font=dict(size=12, color="#ffffff", family=font, weight=700),
            ))

    if held:
        ly = HEIGHT - LEGEND_H / 2 + 2
        x = CARD_AREA_LEFT
        # Neutral cool gray, so the key reads as applying to every category
        # rather than matching the Defensive row's warm tan.
        legend_bg, legend_txt = "#DFE1E7", "#5F6573"
        for outlined, label in [(True, held_label), (False, "In the universe")]:
            shapes.append(dict(
                type="path",
                path=_round_rect_path(x + 1, ly - 6, x + 13, ly + 6, 2) if outlined
                else _round_rect_path(x, ly - 7, x + 14, ly + 7, 3),
                fillcolor=legend_bg,
                line=dict(color=legend_txt, width=2) if outlined else dict(width=0),
            ))
            annotations.append(dict(
                x=x + 20, y=ly, text=label, showarrow=False, xanchor="left", yanchor="middle",
                font=dict(size=12, color=TEXT_SECONDARY, family=font),
            ))
            # Longer keys (next month's wording) push the second item right.
            x += max(190, 20 + _est_text_width(label, 12) + 34)

    fig = go.Figure()
    fig.update_layout(
        shapes=shapes,
        annotations=annotations,
        xaxis=dict(range=[0, WIDTH], visible=False, fixedrange=True),
        yaxis=dict(range=[HEIGHT, 0], visible=False, fixedrange=True),
        width=WIDTH,
        height=HEIGHT,
        margin=dict(t=0, b=0, l=0, r=0),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        showlegend=False,
        autosize=False,
        dragmode=False,
        hovermode=False,
    )
    return fig


def _build_universe_from_editors(cat_df, asset_df):
    """Combine the Categories and Assets editor frames into the JSON structure.

    Category order is preserved from the categories table. Within each
    category, asset order is preserved from the assets table. Rows with
    missing required fields or unknown categories are dropped silently.
    """
    universe = {"categories": []}
    seen = set()

    for _, row in cat_df.iterrows():
        name = str(row.get("category", "") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        # Treat missing/null visible values as True (the default) so a blank
        # checkbox cell in the editor doesn't accidentally hide a category.
        visible_raw = row.get("visible", True)
        visible = True if pd.isna(visible_raw) else bool(visible_raw)
        universe["categories"].append({
            "name": name,
            "visible": visible,
            "color_bg": str(row.get("background_color", "") or "").strip() or "#E8E4DA",
            "color_text": str(row.get("text_color", "") or "").strip() or "#4A463D",
            "assets": [],
        })

    cat_map = {c["name"]: c for c in universe["categories"]}
    for _, row in asset_df.iterrows():
        cat_name = str(row.get("category", "") or "").strip()
        a_name = str(row.get("asset_name", "") or "").strip()
        ticker = str(row.get("ticker", "") or "").strip()
        if not cat_name or not a_name or cat_name not in cat_map:
            continue
        cat_map[cat_name]["assets"].append({"name": a_name, "ticker": ticker})

    return universe


def render_asset_universe_section():
    """Render the Asset Universe heading, grid, footnote, and editor expander."""
    st.markdown("## Asset Universe")

    universe = load_asset_universe()

    # Render as a Plotly chart so the toolbar's PNG download button is
    # available. Native width is 720px; centered via column split since the
    # rest of the dashboard's charts are full-width. Hide the chart-interaction
    # tools (zoom, pan, etc.) that don't apply to a static layout, leaving
    # the toolbar focused on the download button.
    held = {}
    try:
        rows, _alloc_date = derive_current_allocation(load_holdings_values())
        held = {r["ticker"]: float(r["weight_pct"]) for r in (rows or [])}
    except Exception:
        held = {}

    # Next month's basket, the same targets as the Allocation Drift table's
    # New Target column. Blank or zero weights are skipped.
    next_held = {}
    for r in load_next_allocation():
        try:
            t = str(r.get("ticker", "")).strip().upper()
            w = float(str(r.get("weight", "")).strip().rstrip("%"))
        except (TypeError, ValueError, AttributeError):
            continue
        if t and w > 0:
            next_held[t] = w

    view = UNIVERSE_VIEW_NOW
    if next_held and UNIVERSE_HIGHLIGHT_HELD:
        view = st.pills("Show", [UNIVERSE_VIEW_NOW, UNIVERSE_VIEW_NEXT],
                        default=UNIVERSE_VIEW_NOW, selection_mode="single",
                        key="universe_view") or UNIVERSE_VIEW_NOW
    show_next = view == UNIVERSE_VIEW_NEXT
    shown = next_held if show_next else held

    if show_next:
        fig = build_asset_universe_chart(universe, next_held,
                                         held_label="Next month, with target weight")
        au_config = chart_config("Asset Universe Next Month", static=True)
    else:
        fig = build_asset_universe_chart(universe, held)
        au_config = chart_config("Asset Universe", static=True)
    # Drawn at its native 720 px. The old centering column squeezed it below
    # that width in narrower windows, which shrank the cards and crowded the text.
    st.plotly_chart(fig, use_container_width=False, config=au_config)

    # A held or targeted ticker with no card would otherwise vanish silently.
    grid_tickers = {str(a.get("ticker", "")).strip().upper()
                    for c in universe.get("categories", []) if c.get("visible", True)
                    for a in c.get("assets", [])}
    missing = sorted(t for t in shown if t not in grid_tickers)
    if missing and UNIVERSE_HIGHLIGHT_HELD:
        st.warning("Not shown in the grid (no visible card): " + ", ".join(missing)
                   + ". Add it under Edit Asset Universe.")

    if show_next:
        outline_note = ("Outlined cards are next month's holdings, with their target weights "
                        "for the upcoming month-end rebalance. ")
    elif held and UNIVERSE_HIGHLIGHT_HELD:
        outline_note = ("Outlined cards are the current holdings, with their weights as of the "
                        "latest rebalance. ")
    else:
        outline_note = ""
    footnote_au = (
        "Current asset universe used by the Asymmetric Edge strategy. "
        + outline_note
        + "Holdings rotate based on regime signals and are rebalanced as market conditions evolve."
    )
    st.markdown(f'<p class="footer-text">{footnote_au}</p>', unsafe_allow_html=True)

    with st.expander("Edit Asset Universe", expanded=False):
        st.caption(
            "Edit the categories and assets below, then click Save. Categories render in the order shown. "
            "Within each category, assets render left to right. Empty categories are hidden automatically."
        )

        cat_rows = []
        asset_rows = []
        for cat in universe.get("categories", []):
            cat_rows.append({
                "category": cat.get("name", ""),
                # Default to True if missing so older JSON files without the
                # visible field don't appear unchecked when first loaded.
                "visible": bool(cat.get("visible", True)),
                "background_color": cat.get("color_bg", "#E8E4DA"),
                "text_color": cat.get("color_text", "#4A463D"),
            })
            for asset in cat.get("assets", []):
                asset_rows.append({
                    "category": cat.get("name", ""),
                    "asset_name": asset.get("name", ""),
                    "ticker": asset.get("ticker", ""),
                })

        cat_df = pd.DataFrame(cat_rows) if cat_rows else pd.DataFrame(
            columns=["category", "visible", "background_color", "text_color"]
        )
        asset_df = pd.DataFrame(asset_rows) if asset_rows else pd.DataFrame(
            columns=["category", "asset_name", "ticker"]
        )

        st.markdown("**Categories**")
        st.caption(
            "Uncheck Visible to hide a category from the grid without losing its assets or colors. "
            "Check it again to bring it back."
        )
        edited_cats = st.data_editor(
            cat_df,
            num_rows="dynamic",
            column_config={
                "category": st.column_config.TextColumn("Category", required=True),
                "visible": st.column_config.CheckboxColumn(
                    "Visible",
                    help="Show this category in the grid. Uncheck to hide it while keeping its data.",
                    default=True,
                ),
                "background_color": st.column_config.TextColumn(
                    "Card background (hex)",
                    help="Hex color for the card background, e.g. #DCE7F4. Include the leading #.",
                    required=True,
                ),
                "text_color": st.column_config.TextColumn(
                    "Card text (hex)",
                    help="Hex color for the asset name and ticker, e.g. #1F4D87. Include the leading #.",
                    required=True,
                ),
            },
            key="au_categories",
            use_container_width=True,
        )

        # Materialize the current category names so the asset editor's
        # dropdown stays in sync with category edits.
        category_options = [
            c for c in edited_cats["category"].dropna().astype(str).tolist() if c.strip()
        ]

        st.markdown("**Assets**")
        edited_assets = st.data_editor(
            asset_df,
            num_rows="dynamic",
            column_config={
                "category": st.column_config.SelectboxColumn(
                    "Category",
                    options=category_options if category_options else [""],
                    required=True,
                ),
                "asset_name": st.column_config.TextColumn("Display name", required=True),
                "ticker": st.column_config.TextColumn("Ticker", required=True),
            },
            key="au_assets",
            use_container_width=True,
        )

        col_save, col_reset, _ = st.columns([1, 1, 3])
        with col_save:
            save_clicked = st.button("Save Changes", type="primary", key="au_save")
        with col_reset:
            reset_clicked = st.button("Reset to Default", key="au_reset")

        if save_clicked:
            try:
                new_universe = _build_universe_from_editors(edited_cats, edited_assets)
                if not new_universe["categories"]:
                    st.error("At least one category with at least one asset is required.")
                else:
                    save_asset_universe(new_universe)
                    st.success("Asset universe saved. Refreshing.")
                    st.rerun()
            except Exception as e:
                st.error(f"Save failed: {e}")

        if reset_clicked:
            try:
                save_asset_universe(DEFAULT_ASSET_UNIVERSE)
                st.success("Reset to default. Refreshing.")
                st.rerun()
            except Exception as e:
                st.error(f"Reset failed: {e}")


# ---------- Main ----------
# ===========================================================================
# Track-record analytics (added October 22, 2026)
#
# Seven sections built entirely from files the dashboard already reads: the
# anchored series, holdings_daily_values.csv, reconstructed_account_value.csv,
# and adjusted closes through _fetch_closes. They need no new inputs and
# refresh whenever the pipeline does.
#
#   Monthly Returns          calendar grid of monthly returns, year totals,
#                            and the difference against the S&P 500
#   What Drove the Month     each holding's contribution to one month
#   Rebalance Log            what each month-end rebalance added, exited,
#                            and how much of the portfolio turned over
#   Drawdowns Over Time      underwater chart plus the deepest declines
#   The Asymmetry            upside/downside capture against the S&P 500
#   Rolling 12-Month Return  trailing one-year return, excess, and volatility
#   Risk vs. Return          CAGR against volatility for the strategy, its
#                            benchmarks, and the asset universe
#
# Every figure is a Plotly figure rendered with chart_config, so the toolbar's
# PNG download works for newsletter use. Table-style figures are drawn in
# pixel coordinates (like the HGER look-through and Asset Universe grid) so the
# exported PNG matches the screen. Each section renders through
# _render_guarded, so a data problem in one section shows a notice instead of
# taking the page down.
# ===========================================================================

ANALYTICS_WIDTH = 780   # fits Tyler's Firefox content column (about 795 px); wider figures get squeezed
ANALYTICS_FONT = "DM Sans, sans-serif"
ANALYTICS_TINT = "#F0EDF8"      # light lavender used for AE emphasis cells
ANALYTICS_RULE = "#E5E7EB"
ANALYTICS_HEADER_BG = "#F9FAFB"
ANALYTICS_CELL_TEXT = "#2E2E38"
MINUS = "−"

# The benchmark every analytics section compares against first (Tyler's
# primary comparison, October 22, 2026): an 80/20 portfolio, proxied by AOA.
PRIMARY_BENCHMARK = "80/20"

# Capture ratios are the exception: they are measured against the S&P 500, the
# benchmark funds most commonly quote them against, so the figures compare
# directly with other managers' published capture ratios.
CAPTURE_BENCHMARK = "S&P 500"   # default for The Asymmetry: the standard capture-ratio benchmark
CAPTURE_BENCHMARK_CHOICES = ["S&P 500", "80/20", "60/40"]   # swappable in The Asymmetry
CAPTURE_CUSTOM_LABEL = "Custom ticker"   # fourth choice: any ticker typed in, QQQ by default
CAPTURE_CUSTOM_DEFAULT = "QQQ"
CAPTURE_CUSTOM_BAR = "#5F6B7A"   # default bar color for a typed-in ticker: a neutral slate that no portfolio
                                 # or asset category uses, darker than the S&P 500's light gray so negative
                                 # bars read solidly, and clearly apart from Asymmetric Edge purple

# Money-market and sweep positions are cash for every analytics purpose.
CASH_LIKE_TICKERS = {"389930108", "SPAXX"}

# Monthly heatmap tiers, light to strong, using the dashboard's gain/loss hues.
HEAT_TIERS = [
    # (lower bound inclusive in percent, fill, legend label)
    (3.0, "#9FD3B3", "≥ 3%"),
    (1.0, "#CFEAD9", "1% to 3%"),
    (0.0, "#EAF5EE", "0% to 1%"),
    (-1.0, "#FAE6E3", MINUS + "1% to 0%"),
    (-3.0, "#F2C6BF", MINUS + "3% to " + MINUS + "1%"),
    (None, "#E59E93", "≤ " + MINUS + "3%"),
]
HEAT_EMPTY = "#F7F7F9"


def _fmt_pct(value, digits=1, signed=True, suffix="%"):
    """Format a percent-unit number with a true minus sign; n/a when missing."""
    if value is None:
        return "n/a"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if not np.isfinite(value):
        return "n/a"
    if round(value, digits) == 0:
        return f"{0:.{digits}f}{suffix}"
    if value < 0:
        sign = MINUS
    else:
        sign = "+" if signed else ""
    return f"{sign}{abs(value):.{digits}f}{suffix}"


def _heat_fill(pct):
    if pct is None or not np.isfinite(pct):
        return HEAT_EMPTY
    pct = round(pct, 1)
    for lower, fill, _label in HEAT_TIERS:
        if lower is None or pct >= lower:
            return fill
    return HEAT_TIERS[-1][1]


def _round_rect_path(x0, y0, x1, y1, r=6):
    """SVG path for a rectangle with rounded corners, in data coordinates."""
    r = max(0.0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    return (
        f"M {x0 + r},{y0} L {x1 - r},{y0} Q {x1},{y0} {x1},{y0 + r} "
        f"L {x1},{y1 - r} Q {x1},{y1} {x1 - r},{y1} L {x0 + r},{y1} "
        f"Q {x0},{y1} {x0},{y1 - r} L {x0},{y0 + r} Q {x0},{y0} {x0 + r},{y0} Z"
    )


def _px_text(annotations, x, y, value, anchor="left", size=15, color=TEXT_PRIMARY,
             bold=False, valign="middle"):
    annotations.append(dict(
        x=x, y=y, xref="x", yref="y", xanchor=anchor, yanchor=valign,
        text=f"<b>{value}</b>" if bold else value, showarrow=False,
        align=anchor if anchor in ("left", "right") else "center",
        font=dict(family=ANALYTICS_FONT, size=size, color=color),
    ))


def _pixel_layout(fig, width, height, shapes, annotations):
    """Lay a figure out in pixel coordinates: x runs 0..width left to right and
    y runs 0..height top to bottom, so tables export to PNG exactly as drawn."""
    fig.update_layout(
        **DARK_LAYOUT,
        width=width, height=height,
        margin=dict(t=0, b=0, l=0, r=0),
        xaxis=dict(range=[0, width], visible=False, fixedrange=True),
        yaxis=dict(range=[height, 0], visible=False, fixedrange=True),
        shapes=shapes, annotations=annotations, showlegend=False,
        hoverlabel=dict(font=dict(family=ANALYTICS_FONT, size=13)),
    )
    return fig


def _footnote(text):
    st.markdown(f'<p class="footer-text">{text}</p>', unsafe_allow_html=True)


def _render_guarded(title, fn, *args, heading=True, **kwargs):
    """Render one analytics section under its header. Any exception becomes a
    notice in place of the section; the rest of the dashboard keeps going.
    heading=False lets a section write its own (changing) heading."""
    if heading:
        st.markdown(f"## {title}")
    try:
        fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - a section must never take the page down
        st.info(
            f"{title} could not be computed from the current data "
            f"({type(exc).__name__}: {exc})."
        )


def _long_date(d):
    d = pd.Timestamp(d)
    return f"{d:%B} {d.day}, {d.year}"


# ---------------------------------------------------------------------------
# Newsletter captions (added October 29, 2026). Each newsletter chart gets a
# collapsed "Newsletter caption" box under its long footnote, with the short,
# email-ready caption already dated for the current view and a copy button.
# The wording follows the asymmetric-edge-newsletter skill
# (references/dashboard-charts.md); change them together.
# ---------------------------------------------------------------------------
# "Before taxes and fees" (Tyler, October 29, 2026): the live returns come from
# actual fills, so trading costs are already in them. Backtest captions, which
# the dashboard does not produce, still say "and transaction costs."
# Shortened October 30, 2026 (November 2026 update). Captions whose description
# already names the benchmarks end with NEWSLETTER_RETURNS_SENTENCES. Growth of
# $10,000 names them in the ending instead (newsletter_returns_sentences).
NEWSLETTER_YAHOO = "from Yahoo Finance adjusted closes with dividends reinvested"
NEWSLETTER_CLOSE = "Before taxes and fees. Past performance does not guarantee future results."
NEWSLETTER_RETURNS_SENTENCES = (
    "Asymmetric Edge uses my account's time-weighted returns. "
    f"Benchmark data {NEWSLETTER_YAHOO}. " + NEWSLETTER_CLOSE
)
CAPTION_SERIES = {"80/20": "80/20 (AOA)", "60/40": "60/40 (AOR)", "S&P 500": "S&P 500 (SPY)"}


_NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
                 8: "eight", 9: "nine"}


def _cap_date(d):
    d = pd.Timestamp(d)
    return f"{d.month}/{d.day}/{d.year}"


def _cap_join(items):
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _cap_vs(keys):
    bench = [CAPTION_SERIES[k] for k in SERIES_ORDER if k in keys and k in CAPTION_SERIES]
    return "Asymmetric Edge vs. " + _cap_join(bench) if bench else "Asymmetric Edge"


def newsletter_returns_sentences(keys):
    """Standard ending that names the benchmarks shown, for a caption whose
    description doesn't (Growth of $10,000)."""
    bench = [CAPTION_SERIES[k] for k in SERIES_ORDER if k in keys and k in CAPTION_SERIES]
    out = "Asymmetric Edge uses my account's time-weighted returns. "
    if bench:
        lead = "Benchmarks are" if len(bench) > 1 else "The benchmark is"
        out += f"{lead} {_cap_join(bench)}, {NEWSLETTER_YAHOO}. "
    return out + NEWSLETTER_CLOSE


def newsletter_caption(text):
    """A collapsed, copy-ready caption for pasting under the chart in Ghost."""
    with st.expander("Newsletter caption", expanded=False):
        st.code(text, language=None, wrap_lines=True)


def attribution_title(month_return, period):
    """Section heading and newsletter heading for What Drove the Month, e.g.
    "Where October's Loss Came From". Tyler, October 29, 2026: one name for
    both, saying gain or loss to match the month."""
    word = "Return"
    if month_return is not None and round(month_return * 100.0, 2) != 0:
        word = "Gain" if month_return > 0 else "Loss"
    return f"Where {period.strftime('%B')}'s {word} Came From"


def _asset_label(ticker):
    info = ASSET_CATALOG.get(ticker)
    return f"{info['asset']} ({ticker})" if info else ticker


# ---------- shared data helpers ----------

def _monthly_returns(daily, inception):
    """Calendar-month returns (fractions) keyed by monthly Period.

    The first month is measured from the inception close and every later month
    from the prior month's last close, the same anchoring
    compute_summary_metrics uses, so closed Asymmetric Edge months tie to
    Fidelity's reported returns.
    """
    s = daily.dropna()
    s = s[s.index >= pd.Timestamp(inception)]
    if len(s) < 2:
        return pd.Series(dtype="float64")
    month_last = s.groupby(s.index.to_period("M")).last()
    prev = month_last.shift(1)
    prev.iloc[0] = float(s.iloc[0])
    return (month_last / prev - 1.0).dropna()


def _month_end_values(daily, inception):
    """Month-end values keyed by Period, with the inception close as the
    'prior month-end' anchor of the first month."""
    s = daily.dropna()
    s = s[s.index >= pd.Timestamp(inception)]
    if len(s) < 2:
        return pd.Series(dtype="float64")
    month_last = s.groupby(s.index.to_period("M")).last()
    anchor = pd.Series([float(s.iloc[0])], index=[month_last.index[0] - 1])
    return pd.concat([anchor, month_last])


def _last_month_closed(last_date):
    """True when the data ends on its month's final session and that session
    has closed, so the month's return is final."""
    last_date = pd.Timestamp(last_date)
    return _is_month_final_session(last_date) and _session_has_closed(last_date)


def _open_period(last_date):
    """The month still in progress at last_date, or None if it has closed."""
    return None if _last_month_closed(last_date) else pd.Timestamp(last_date).to_period("M")


@st.cache_data(ttl=3600)
def load_anchor_flags():
    """Date -> anchored flag from asymmetric_edge_series.csv. A day is anchored
    when its month ties to a Fidelity figure, including an open month built
    with Fidelity's month-to-date return. Empty when the column is missing."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pipeline_dir = os.path.join(os.path.dirname(script_dir), "Portfolio Hist Val Reconstruction")
    for path in (os.path.join(pipeline_dir, "asymmetric_edge_series.csv"),
                 os.path.join(script_dir, "asymmetric_edge_series.csv")):
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_csv(path, parse_dates=["date"])
        except Exception:
            return pd.Series(dtype="bool")
        if "anchored" not in df.columns:
            return pd.Series(dtype="bool")
        flags = df.set_index("date")["anchored"].astype(str).str.strip().str.lower() == "true"
        return flags.sort_index()
    return pd.Series(dtype="bool")


def _open_month_anchored(last_date):
    """True when the open month's figure ties to Fidelity: either the series
    was built with Fidelity's month-to-date return, or the dashboard extended
    it with a month-to-date return entered in Update Portfolio Data."""
    flags = load_anchor_flags()
    if flags.empty:
        return False
    last_date = pd.Timestamp(last_date)
    if last_date > flags.index.max():
        return True
    return bool(flags.get(last_date, False))


def _closed_only(monthly, last_date):
    open_p = _open_period(last_date)
    if open_p is None or monthly.empty:
        return monthly
    return monthly[monthly.index < open_p]


def _held_tickers(holdings_values, since=None):
    """Tickers with a meaningful position at any point since `since`."""
    if holdings_values is None or holdings_values.empty:
        return []
    hv = holdings_values
    if since is not None:
        hv = hv[hv.index >= pd.Timestamp(since) - pd.Timedelta(days=10)]
    held = hv.columns[(hv.fillna(0.0) > 1.0).any()]
    return [t for t in held if t not in CASH_LIKE_TICKERS]


@st.cache_data(ttl=3600)
def load_holding_prices(tickers: tuple, start_date: str, end_date: str):
    """Adjusted closes for every ticker held since inception. Routed through
    _fetch_closes, so the committed snapshot covers Yahoo outages."""
    return _fetch_closes(list(tickers), start_date, end_date)


def _price_frame_on(prices, dates):
    """Prices aligned to the given dates, carrying the last close forward over
    exchange holidays."""
    if prices is None or prices.empty:
        return pd.DataFrame(index=pd.DatetimeIndex(dates))
    union = prices.index.union(pd.DatetimeIndex(dates))
    return prices.reindex(union).sort_index().ffill().reindex(pd.DatetimeIndex(dates))


# ===========================================================================
# 1. MONTHLY RETURNS
# ===========================================================================

def build_monthly_returns_figure(ae_monthly, spx_monthly, open_period, last_date,
                                 bench_label=PRIMARY_BENCHMARK):
    """Calendar grid: one row per year, one cell per month, then the year's
    compounded return and its difference from the primary benchmark (80/20)
    in points. spx_monthly holds that benchmark's monthly returns. Month cells
    show the percent value without the % sign so the grid fits 780 px."""
    years = sorted({p.year for p in ae_monthly.index})
    W = ANALYTICS_WIDTH
    YEAR_W, TOT_W, VS_W, GAP = 46, 70, 80, 4
    cell_w = (W - YEAR_W - TOT_W - VS_W - 14 * GAP) / 12
    HEAD_H, ROW_H, ROW_GAP, LEG_H = 30, 48, 4, 50
    top0 = HEAD_H + 8
    H = int(top0 + len(years) * (ROW_H + ROW_GAP) + LEG_H)

    def x_month(m):
        return YEAR_W + GAP + (m - 1) * (cell_w + GAP)

    x_tot = YEAR_W + 13 * GAP + 12 * cell_w
    x_vs = x_tot + TOT_W + GAP

    shapes, ann = [], []
    hx, hy, htext = [], [], []

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    _px_text(ann, 0, HEAD_H / 2, "Year", size=12, color=TEXT_SECONDARY, bold=True)
    for m, name in enumerate(months, start=1):
        _px_text(ann, x_month(m) + cell_w / 2, HEAD_H / 2, name, anchor="center",
                 size=12, color=TEXT_SECONDARY, bold=True)
    _px_text(ann, x_tot + TOT_W / 2, HEAD_H / 2, "Year", anchor="center", size=12, bold=True)
    _px_text(ann, x_vs + VS_W / 2, HEAD_H / 2, f"vs {bench_label}", anchor="center", size=12,
             color=TEXT_SECONDARY, bold=True)
    shapes.append(dict(type="line", x0=0, x1=W, y0=HEAD_H, y1=HEAD_H,
                       line=dict(color=BRAND_PURPLE, width=2)))

    for row, year in enumerate(years):
        y0 = top0 + row * (ROW_H + ROW_GAP)
        y1 = y0 + ROW_H
        mid = (y0 + y1) / 2
        _px_text(ann, 0, mid, str(year), size=14, bold=True)
        ae_growth, spx_growth, spx_ok = 1.0, 1.0, True
        for m in range(1, 13):
            period = pd.Period(year=year, month=m, freq="M")
            x0 = x_month(m)
            x1 = x0 + cell_w
            r = ae_monthly.get(period)
            pct = None if r is None or not np.isfinite(r) else float(r) * 100.0
            is_open = open_period is not None and period == open_period and pct is not None
            shapes.append(dict(
                type="path", path=_round_rect_path(x0, y0, x1, y1, 5),
                fillcolor=_heat_fill(pct),
                # Solid outline: dashes on a small rounded cell render as
                # broken fragments, especially in the legend key.
                line=dict(color=BRAND_PURPLE, width=2) if is_open else dict(width=0),
                layer="below",
            ))
            if pct is None:
                continue
            ae_growth *= 1.0 + pct / 100.0
            s_r = spx_monthly.get(period) if spx_monthly is not None else None
            if s_r is None or not np.isfinite(s_r):
                spx_ok = False
            else:
                spx_growth *= 1.0 + float(s_r)
            cell_text = _fmt_pct(pct, suffix="")
            if is_open:
                _px_text(ann, (x0 + x1) / 2, mid - 7, cell_text, anchor="center",
                         size=13, color=ANALYTICS_CELL_TEXT, bold=True)
                _px_text(ann, (x0 + x1) / 2, mid + 12, "MTD", anchor="center",
                         size=9, color=BRAND_PURPLE, bold=True)
            else:
                _px_text(ann, (x0 + x1) / 2, mid, cell_text, anchor="center",
                         size=13, color=ANALYTICS_CELL_TEXT, bold=True)
            label = period.strftime("%B %Y")
            if is_open:
                label += f" (month to date through {pd.Timestamp(last_date):%b} {pd.Timestamp(last_date).day})"
            spx_txt = _fmt_pct(float(s_r) * 100.0, 2) if s_r is not None and np.isfinite(s_r) else "n/a"
            hx.append((x0 + x1) / 2)
            hy.append(mid)
            htext.append(f"<b>{label}</b><br>Asymmetric Edge {_fmt_pct(pct, 2)}"
                         f"<br>{bench_label} {spx_txt}")

        year_pct = (ae_growth - 1.0) * 100.0
        shapes.append(dict(type="path", path=_round_rect_path(x_tot, y0, x_tot + TOT_W, y1, 5),
                           fillcolor=ANALYTICS_TINT, line=dict(width=0), layer="below"))
        _px_text(ann, x_tot + TOT_W / 2, mid, _fmt_pct(year_pct), anchor="center",
                 size=14, color=BRAND_PURPLE, bold=True)
        if spx_ok:
            diff = year_pct - (spx_growth - 1.0) * 100.0
            _px_text(ann, x_vs + VS_W / 2, mid, _fmt_pct(diff, suffix=" pts"), anchor="center",
                     size=13, color=GAIN_GREEN if diff >= 0 else LOSS_RED, bold=True)
        else:
            _px_text(ann, x_vs + VS_W / 2, mid, "n/a", anchor="center", size=13,
                     color=TEXT_MUTED)

    # Scale legend
    ly = H - LEG_H / 2 + 4
    _px_text(ann, 0, ly, "Scale", size=11, color=TEXT_SECONDARY)
    chip_w, chip_h, chip_gap = 76, 24, 5
    cx = 38
    for lower, fill, label in reversed(HEAT_TIERS):
        shapes.append(dict(type="path",
                           path=_round_rect_path(cx, ly - chip_h / 2, cx + chip_w, ly + chip_h / 2, 5),
                           fillcolor=fill, line=dict(width=0), layer="below"))
        _px_text(ann, cx + chip_w / 2, ly, label, anchor="center", size=11, color=ANALYTICS_CELL_TEXT)
        cx += chip_w + chip_gap
    if open_period is not None:
        # Key: a miniature of the open-month cell, purple outline with its tag.
        mx = W - 124
        shapes.append(dict(type="path",
                           path=_round_rect_path(mx, ly - chip_h / 2, mx + 38, ly + chip_h / 2, 5),
                           fillcolor="#ffffff",
                           line=dict(color=BRAND_PURPLE, width=2)))
        _px_text(ann, mx + 19, ly, "MTD", anchor="center", size=10, color=BRAND_PURPLE, bold=True)
        _px_text(ann, mx + 46, ly, "Month to date", size=11, color=TEXT_SECONDARY)

    fig = go.Figure()
    if hx:
        fig.add_trace(go.Scatter(
            x=hx, y=hy, mode="markers",
            marker=dict(size=int(min(cell_w, ROW_H)), color="rgba(0,0,0,0)", symbol="square"),
            hovertext=htext, hovertemplate="%{hovertext}<extra></extra>",
            showlegend=False,
        ))
    return _pixel_layout(fig, W, H, shapes, ann)


MONTHLY_LAYOUTS = ["Dashboard", "Newsletter (tall)"]
MONTHLY_BENCH_FOOTNOTE = {
    "80/20": ("vs 80/20 is the difference in percentage points from the 80/20 portfolio (AOA, total "
              "return with dividends reinvested, Yahoo Finance) over the same months. "),
    "60/40": ("vs 60/40 is the difference in percentage points from the 60/40 portfolio (AOR, total "
              "return with dividends reinvested, Yahoo Finance) over the same months. "),
    "S&P 500": ("vs S&amp;P 500 is the difference in percentage points from the S&amp;P 500 (SPY, "
                "total return with dividends reinvested, Yahoo Finance) over the same months. "),
}
MONTHLY_BENCH_CAPTION = {"80/20": "the 80/20 portfolio (AOA)", "60/40": "the 60/40 portfolio (AOR)",
                         "S&P 500": "the S&P 500 (SPY)"}


def _monthly_custom_all(ticker, combined, latest_date):
    """Monthly total returns for a typed-in ticker, open month included, for
    the Monthly Returns grid. None when no usable history comes back."""
    inception = combined.index[0]
    prices = load_custom_ticker_data((ticker,), inception.strftime("%Y-%m-%d"),
                                     pd.Timestamp(latest_date).strftime("%Y-%m-%d"))
    if prices is None or prices.empty or ticker not in prices.columns:
        return None
    daily = _price_frame_on(prices[[ticker]], combined.index)[ticker].dropna()
    if len(daily) < 30:
        return None
    monthly = _monthly_returns(daily, inception)
    # A fund that launched after inception: its first month is partial, so drop it.
    if daily.index[0] > pd.Timestamp(inception) + timedelta(days=5) and len(monthly):
        monthly = monthly.iloc[1:]
    return monthly if len(monthly) >= 1 else None


def build_monthly_returns_tall_figure(ae_monthly, spx_monthly, open_period, last_date,
                                      bench_label=PRIMARY_BENCHMARK):
    """Phone-friendly Monthly Returns for the newsletter (added October 29,
    2026): months run down the side and years across the top, so a few wide
    columns replace the 15-column grid, which shrinks to unreadable on a
    phone. Same data, colors, totals and MTD outline as the wide grid."""
    years = sorted({p.year for p in ae_monthly.index})
    n = max(len(years), 1)
    W = 520
    LABEL_W, GAP = 88, 6
    cell_w = (W - LABEL_W - n * GAP) / n
    HEAD_H, ROW_H, ROW_GAP = 36, 38, 4
    TOT_H, VS_H = 44, 40
    top0 = HEAD_H + 8
    y_tot = top0 + 12 * (ROW_H + ROW_GAP) + 4
    y_vs = y_tot + TOT_H + ROW_GAP
    chip_w, chip_h, chip_gap = 104, 26, 8
    leg_top = y_vs + VS_H + 22
    H = int(leg_top + 22 + 2 * (chip_h + chip_gap) + (36 if open_period is not None else 0) + 6)

    def x_year(i):
        return LABEL_W + GAP + i * (cell_w + GAP)

    shapes, ann = [], []
    hx, hy, htext = [], [], []
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    _px_text(ann, 0, HEAD_H / 2, "Month", size=14, color=TEXT_SECONDARY, bold=True)
    for i, year in enumerate(years):
        _px_text(ann, x_year(i) + cell_w / 2, HEAD_H / 2, str(year), anchor="center",
                 size=15, bold=True)
    shapes.append(dict(type="line", x0=0, x1=W, y0=HEAD_H, y1=HEAD_H,
                       line=dict(color=BRAND_PURPLE, width=2)))
    for m, name in enumerate(months, start=1):
        mid = top0 + (m - 1) * (ROW_H + ROW_GAP) + ROW_H / 2
        _px_text(ann, 0, mid, name, size=14, color=TEXT_SECONDARY, bold=True)

    _px_text(ann, 0, y_tot + TOT_H / 2, "Year", size=15, color=BRAND_PURPLE, bold=True)
    _px_text(ann, 0, y_vs + VS_H / 2, f"vs {bench_label}", size=13, color=TEXT_SECONDARY,
             bold=True)
    for i, year in enumerate(years):
        x0 = x_year(i)
        x1 = x0 + cell_w
        ae_growth, spx_growth, spx_ok = 1.0, 1.0, True
        for m in range(1, 13):
            y0 = top0 + (m - 1) * (ROW_H + ROW_GAP)
            y1 = y0 + ROW_H
            mid = (y0 + y1) / 2
            period = pd.Period(year=year, month=m, freq="M")
            r = ae_monthly.get(period)
            pct = None if r is None or not np.isfinite(r) else float(r) * 100.0
            is_open = open_period is not None and period == open_period and pct is not None
            shapes.append(dict(
                type="path", path=_round_rect_path(x0, y0, x1, y1, 5),
                fillcolor=_heat_fill(pct),
                line=dict(color=BRAND_PURPLE, width=2) if is_open else dict(width=0),
                layer="below",
            ))
            if pct is None:
                continue
            ae_growth *= 1.0 + pct / 100.0
            s_r = spx_monthly.get(period) if spx_monthly is not None else None
            if s_r is None or not np.isfinite(s_r):
                spx_ok = False
            else:
                spx_growth *= 1.0 + float(s_r)
            text = _fmt_pct(pct)
            if is_open:
                text += "  MTD"
            _px_text(ann, (x0 + x1) / 2, mid, text, anchor="center", size=15,
                     color=ANALYTICS_CELL_TEXT, bold=True)
            label = period.strftime("%B %Y")
            if is_open:
                label += f" (month to date through {pd.Timestamp(last_date):%b} {pd.Timestamp(last_date).day})"
            spx_txt = _fmt_pct(float(s_r) * 100.0, 2) if s_r is not None and np.isfinite(s_r) else "n/a"
            hx.append((x0 + x1) / 2)
            hy.append(mid)
            htext.append(f"<b>{label}</b><br>Asymmetric Edge {_fmt_pct(pct, 2)}"
                         f"<br>{bench_label} {spx_txt}")
        year_pct = (ae_growth - 1.0) * 100.0
        shapes.append(dict(type="path", path=_round_rect_path(x0, y_tot, x1, y_tot + TOT_H, 5),
                           fillcolor=ANALYTICS_TINT, line=dict(width=0), layer="below"))
        _px_text(ann, (x0 + x1) / 2, y_tot + TOT_H / 2, _fmt_pct(year_pct), anchor="center",
                 size=16, color=BRAND_PURPLE, bold=True)
        if spx_ok:
            diff = year_pct - (spx_growth - 1.0) * 100.0
            _px_text(ann, (x0 + x1) / 2, y_vs + VS_H / 2, _fmt_pct(diff, suffix=" pts"),
                     anchor="center", size=14, color=GAIN_GREEN if diff >= 0 else LOSS_RED,
                     bold=True)
        else:
            _px_text(ann, (x0 + x1) / 2, y_vs + VS_H / 2, "n/a", anchor="center", size=14,
                     color=TEXT_MUTED)

    # Scale legend, three chips a row
    _px_text(ann, 0, leg_top, "Scale", size=12, color=TEXT_SECONDARY, bold=True)
    tiers = list(reversed(HEAT_TIERS))
    for k, (lower, fill, label) in enumerate(tiers):
        row, col = divmod(k, 3)
        cx = col * (chip_w + chip_gap)
        cy = leg_top + 22 + row * (chip_h + chip_gap)
        shapes.append(dict(type="path",
                           path=_round_rect_path(cx, cy - chip_h / 2, cx + chip_w, cy + chip_h / 2, 5),
                           fillcolor=fill, line=dict(width=0), layer="below"))
        _px_text(ann, cx + chip_w / 2, cy, label, anchor="center", size=12,
                 color=ANALYTICS_CELL_TEXT)
    if open_period is not None:
        my = leg_top + 22 + 2 * (chip_h + chip_gap) + 4
        shapes.append(dict(type="path",
                           path=_round_rect_path(0, my - chip_h / 2, 44, my + chip_h / 2, 5),
                           fillcolor="#ffffff", line=dict(color=BRAND_PURPLE, width=2)))
        _px_text(ann, 22, my, "MTD", anchor="center", size=11, color=BRAND_PURPLE, bold=True)
        _px_text(ann, 54, my, "Month to date", size=12, color=TEXT_SECONDARY)

    fig = go.Figure()
    if hx:
        fig.add_trace(go.Scatter(
            x=hx, y=hy, mode="markers",
            marker=dict(size=int(min(cell_w, ROW_H)), color="rgba(0,0,0,0)", symbol="square"),
            hovertext=htext, hovertemplate="%{hovertext}<extra></extra>",
            showlegend=False,
        ))
    return _pixel_layout(fig, W, H, shapes, ann)


def _asset_row_label(ticker):
    """Emoji, asset name and ticker for row labels, e.g. '🏭  Broad Commodities (HGER)'."""
    info = ASSET_CATALOG.get(ticker)
    if not info:
        return ticker
    return f"{info['emoji']}  {info['asset']} ({ticker})"


def _nice_step(span):
    """A tick step giving four to seven ticks across span."""
    for step in (0.1, 0.2, 0.25, 0.5, 1.0, 2.0, 2.5, 5.0, 10.0):
        if span / step <= 7:
            return step
    return 20.0


def build_attribution_figure(result, is_open):
    """One row per holding: emoji and name, average weight and return, then
    a horizontal waterfall bar showing where its contribution starts and ends,
    and the contribution in points. The month's total closes the table, so
    every bar sits on the same line as its label and the rows add up to it."""
    W = ANALYTICS_WIDTH
    NAME_X = 0
    WEIGHT_R = 300
    RETURN_R = 372
    BX0, BX1 = 396, 664          # bar area
    VALUE_R = W - 2
    HEAD_H, ROW_H, TOTAL_H = 34, 42, 46
    BAR_H = 18
    period = result["period"]
    month_name = period.strftime("%B")

    rows = []
    level = 0.0
    for r in result["rows"]:
        c = r["contribution"] * 100.0
        rows.append({"label": _asset_row_label(r["ticker"]),
                     "weight": None if r.get("avg_weight") is None else r["avg_weight"] * 100.0,
                     "entered_on": r.get("entered_on"),
                     "ret": None if r["return"] is None else r["return"] * 100.0,
                     "start": level, "end": level + c, "value": c,
                     "color": GAIN_GREEN if c >= 0 else LOSS_RED})
        level += c
    total = result["month_return"] * 100.0

    levels = [0.0, total] + [r["start"] for r in rows] + [r["end"] for r in rows]
    lo, hi = min(levels), max(levels)
    span = (hi - lo) or 1.0
    lo -= span * 0.06
    hi += span * 0.06

    def bx(v):
        return BX0 + (v - lo) / (hi - lo) * (BX1 - BX0)

    n = len(rows)
    rows_bottom = HEAD_H + n * ROW_H + TOTAL_H
    TICK_H = 24
    notes = _attribution_notes(result)
    note_lines = sum(len(textwrap.wrap(t, width=118)) for t in notes)
    H = rows_bottom + TICK_H + 50 + note_lines * 19 + (8 if notes else 0)

    shapes, ann = [], []
    # Header
    _px_text(ann, NAME_X, HEAD_H / 2, "Holding", size=13, bold=True)
    _px_text(ann, WEIGHT_R, HEAD_H / 2, "Avg. weight", anchor="right", size=13, bold=True)
    _px_text(ann, RETURN_R, HEAD_H / 2, "Return", anchor="right", size=13, bold=True)
    _px_text(ann, BX0, HEAD_H / 2, "How the month adds up", size=13, bold=True)
    _px_text(ann, VALUE_R, HEAD_H / 2, "Contribution", anchor="right", size=13, bold=True)
    shapes.append(dict(type="line", x0=0, x1=W, y0=HEAD_H, y1=HEAD_H,
                       line=dict(color=BRAND_PURPLE, width=2)))

    # Gridlines and ticks across the bar area
    step = _nice_step(hi - lo)
    t = np.ceil(lo / step) * step
    while t <= hi + 1e-9:
        x = bx(t)
        is_zero = abs(t) < 1e-9
        shapes.append(dict(type="line", x0=x, x1=x, y0=HEAD_H, y1=rows_bottom,
                           line=dict(color="#c9c9d3" if is_zero else GRID_COLOR, width=1),
                           layer="below"))
        tick = "0%" if is_zero else _fmt_pct(t, 2 if step < 0.5 else (1 if step < 1 else 0))
        _px_text(ann, x, rows_bottom + TICK_H / 2 + 2, tick, anchor="center", size=11,
                 color=TEXT_MUTED)
        t += step

    for i, r in enumerate(rows):
        top = HEAD_H + i * ROW_H
        mid = top + ROW_H / 2
        if i:
            shapes.append(dict(type="line", x0=0, x1=BX0 - 12, y0=top, y1=top,
                               line=dict(color=ANALYTICS_RULE, width=1)))
            shapes.append(dict(type="line", x0=BX1 + 12, x1=W, y0=top, y1=top,
                               line=dict(color=ANALYTICS_RULE, width=1)))
        _px_text(ann, NAME_X, mid, r["label"], size=14)
        if r["weight"] is not None:
            _px_text(ann, WEIGHT_R, mid, f"{r['weight']:.1f}%", anchor="right", size=13,
                     color=TEXT_SECONDARY)
        elif r.get("entered_on") is not None:
            _px_text(ann, WEIGHT_R, mid, f"Bought {r['entered_on'].month}/{r['entered_on'].day}",
                     anchor="right", size=12, color=TEXT_MUTED)
        if r["ret"] is not None:
            _px_text(ann, RETURN_R, mid, _fmt_pct(r["ret"], 2), anchor="right", size=13,
                     color=TEXT_SECONDARY)
        x0, x1 = sorted((bx(r["start"]), bx(r["end"])))
        x1 = max(x1, x0 + 2)
        shapes.append(dict(type="path", path=_round_rect_path(x0, mid - BAR_H / 2, x1, mid + BAR_H / 2, 4),
                           fillcolor=r["color"], line=dict(width=0)))
        # Connector from this bar's end down to the next row
        nxt_top = top + ROW_H + (ROW_H - BAR_H) / 2
        shapes.append(dict(type="line", x0=bx(r["end"]), x1=bx(r["end"]),
                           y0=mid + BAR_H / 2, y1=nxt_top,
                           line=dict(color="#9CA3AF", width=1, dash="dot")))
        _px_text(ann, VALUE_R, mid, _fmt_pct(r["value"], 2), anchor="right", size=14,
                 color=(TEXT_SECONDARY if r["color"] == "#9CA3AF" else r["color"]), bold=True)

    # Total row
    top = HEAD_H + n * ROW_H
    mid = top + TOTAL_H / 2
    shapes.append(dict(type="rect", x0=0, x1=W, y0=top, y1=top + TOTAL_H,
                       fillcolor=ANALYTICS_TINT, line_width=0, layer="below"))
    _px_text(ann, NAME_X + 8, mid, f"{month_name} return{' to date' if is_open else ''}",
             size=14, color=BRAND_PURPLE, bold=True)
    x0, x1 = sorted((bx(0.0), bx(total)))
    x1 = max(x1, x0 + 2)
    shapes.append(dict(type="path", path=_round_rect_path(x0, mid - BAR_H / 2, x1, mid + BAR_H / 2, 4),
                       fillcolor=BAR_SERIES_COLORS["AsymEdge"], line=dict(width=0)))
    _px_text(ann, VALUE_R, mid, _fmt_pct(total, 2), anchor="right", size=14,
             color=BRAND_PURPLE, bold=True)

    # One-line takeaway, generated from the numbers
    holdings_sorted = sorted(result["rows"], key=lambda r: r["contribution"])
    if holdings_sorted:
        best, worst = holdings_sorted[-1], holdings_sorted[0]
        parts = [f"{_asset_label(best['ticker'])} contributed the most "
                 f"({_fmt_pct(best['contribution'] * 100, 2)})."]
        if worst["contribution"] < 0 and worst is not best:
            parts.append(f"{_asset_label(worst['ticker'])} was the largest drag "
                         f"({_fmt_pct(worst['contribution'] * 100, 2)}).")
        elif best["contribution"] >= 0:
            parts.append("No holding detracted.")
        wrapped = "<br>".join(textwrap.wrap(" ".join(parts), width=118))
        _px_text(ann, 0, rows_bottom + TICK_H + 14, wrapped, size=13, valign="top")
        y = rows_bottom + TICK_H + 14 + 19 * len(textwrap.wrap(" ".join(parts), width=118)) + 8
        for t in notes:
            lines = textwrap.wrap(t, width=118)
            _px_text(ann, 0, y, "<br>".join(lines), size=12, color=TEXT_SECONDARY, valign="top")
            y += 19 * len(lines)

    return _pixel_layout(go.Figure(), W, int(H), shapes, ann)


def _attribution_notes(result):
    """Plain-language notes for rows a reader would otherwise question: a
    contribution whose sign differs from the fund's return, and a position
    bought on the month's last day for the next month. Added October 29, 2026."""
    notes = []
    for r in result["rows"]:
        c = r["contribution"] * 100.0
        if round(c, 2) == 0:
            continue
        name = _asset_label(r["ticker"])
        if r.get("entered_on") is not None:
            d = r["entered_on"]
            notes.append(f"{name} was bought on {d.strftime('%B')} {d.day} for the next month. "
                         f"The move from its purchase price to that day's close "
                         f"({_fmt_pct(c, 2)}) counts in this month.")
            continue
        ret = r.get("return")
        if ret is None or round(ret * 100.0, 2) == 0 or (ret > 0) == (c > 0):
            continue
        fw, lw = r.get("first_weight"), r.get("last_weight")
        if fw is None or lw is None:
            continue
        notes.append(f"{name} returned {_fmt_pct(ret * 100.0, 2)} but contributed "
                     f"{_fmt_pct(c, 2)}: its weight went from {fw * 100:.1f}% at the start "
                     f"of the month to {lw * 100:.1f}%, so its "
                     f"{'losing' if c < 0 else 'winning'} days landed on more money than its "
                     f"{'winning' if c < 0 else 'losing'} days.")
    return notes


def build_rebalance_log_figure(rows_newest_first, stats):
    W = ANALYTICS_WIDTH
    TILE_H, TILE_GAP = 70, 12
    HEAD_TOP = TILE_H + 22
    HEAD_H = 32
    cols = {"month": 0, "traded": 64, "added": 170, "exited": 318, "shifts": 466, "turn": W - 2}
    LINE_H = 18

    def row_height(r):
        lines = max(len(r["added"]), len(r["exited"]), 1, (len(r["shifts"]) + 1) // 2)
        return 16 + LINE_H * lines

    H = HEAD_TOP + HEAD_H + sum(row_height(r) for r in rows_newest_first) + 6
    shapes, ann = [], []

    tile_w = (W - 2 * TILE_GAP) / 3
    tiles = [
        (f"{stats['avg_turnover']:.1f}%", "average monthly turnover"),
        (f"{stats['new_months']} of {stats['n']}", "rebalances added a new holding"),
        (f"{stats['avg_holdings']:.1f}", "holdings on average"),
    ]
    for i, (big, small) in enumerate(tiles):
        x0 = i * (tile_w + TILE_GAP)
        shapes.append(dict(type="path", path=_round_rect_path(x0, 0, x0 + tile_w, TILE_H, 10),
                           fillcolor=ANALYTICS_TINT, line=dict(width=0), layer="below"))
        _px_text(ann, x0 + 16, 27, big, size=22, color=BRAND_PURPLE, bold=True)
        _px_text(ann, x0 + 16, 53, small, size=12)

    hy = HEAD_TOP + HEAD_H / 2
    for key, label in [("month", "Month"), ("traded", "Traded"), ("added", "Added"),
                       ("exited", "Exited"), ("shifts", "Reweighted")]:
        _px_text(ann, cols[key], hy, label, size=13, bold=True)
    _px_text(ann, cols["turn"], hy, "Turnover", anchor="right", size=13, bold=True)
    y = HEAD_TOP + HEAD_H
    shapes.append(dict(type="line", x0=0, x1=W, y0=y, y1=y, line=dict(color=BRAND_PURPLE, width=2)))

    def fmt_item(t, w, sign):
        return f"{sign}{t} {w:.1f}%"

    for r in rows_newest_first:
        h = row_height(r)
        top = y + 8
        first = top + LINE_H / 2
        _px_text(ann, cols["month"], first, r["period"].strftime("%b-%y"), size=14, bold=True)
        _px_text(ann, cols["traded"], first, _long_date(r["date"]).replace(
            r["date"].strftime("%B"), r["date"].strftime("%b")), size=12, color=TEXT_SECONDARY)
        for key, items, sign, color in [("added", r["added"], "+", GAIN_GREEN),
                                        ("exited", r["exited"], MINUS, LOSS_RED)]:
            if items:
                for j, (t, w) in enumerate(items):
                    _px_text(ann, cols[key], top + LINE_H * j + LINE_H / 2,
                             fmt_item(t, w, sign), size=12, color=color, bold=True)
            else:
                _px_text(ann, cols[key], first, "None", size=12, color=TEXT_MUTED)
        if r["shifts"]:
            items = [f"{t} {_fmt_pct(d, 1, suffix='')}" for t, d in r["shifts"]]
            lines = [", ".join(items[i:i + 2]) for i in range(0, len(items), 2)]
            for j, line in enumerate(lines):
                _px_text(ann, cols["shifts"], top + LINE_H * j + LINE_H / 2, line, size=12,
                         color=TEXT_SECONDARY)
        else:
            _px_text(ann, cols["shifts"], first, "None", size=12, color=TEXT_MUTED)
        bar_x1 = cols["turn"] - 52
        bar_x0 = bar_x1 - 56
        shapes.append(dict(type="path", path=_round_rect_path(bar_x0, first - 4, bar_x1, first + 4, 4),
                           fillcolor="#ECECF1", line=dict(width=0)))
        fill_x1 = bar_x0 + 56 * min(r["turnover"], 100.0) / 100.0
        if fill_x1 - bar_x0 >= 2:
            shapes.append(dict(type="path", path=_round_rect_path(bar_x0, first - 4, fill_x1, first + 4, 4),
                               fillcolor=BAR_SERIES_COLORS["AsymEdge"], line=dict(width=0)))
        _px_text(ann, cols["turn"], first, f"{r['turnover']:.1f}%", anchor="right", size=12, bold=True)
        y += h
        shapes.append(dict(type="line", x0=0, x1=W, y0=y, y1=y,
                           line=dict(color=ANALYTICS_RULE, width=1)))

    return _pixel_layout(go.Figure(), W, int(H), shapes, ann)


def build_capture_figure(captures, worst, bench_label=None, bench_color=None):
    """Capture tiles, sentence and table across the top; the benchmark's worst
    months as grouped bars across the bottom. Built for 780 px."""
    bench_label = bench_label or CAPTURE_BENCHMARK
    # Running text says "the 80/20 portfolio"; tiles and headers keep the short name.
    bench_noun = f"{bench_label} portfolio" if bench_label in ("80/20", "60/40") else bench_label
    # House benchmarks take "the"; a typed-in ticker reads better bare ("QQQ rose").
    the_noun = f"the {bench_noun}" if bench_label in ("S&P 500", "80/20", "60/40") else bench_noun
    W, H = ANALYTICS_WIDTH, 560
    shapes, ann = [], []
    ae = captures.get("AsymEdge")

    # Tiles, top left
    tile_w, tile_gap = 172, 10
    for i, (label, key, sub) in enumerate([
        ("Upside capture", "up", f"of {bench_label} up months"),
        ("Downside capture", "down", f"of {bench_label} down months"),
    ]):
        x0 = i * (tile_w + tile_gap)
        shapes.append(dict(type="path", path=_round_rect_path(x0, 0, x0 + tile_w, 118, 10),
                           fillcolor=ANALYTICS_TINT, line=dict(width=0), layer="below"))
        _px_text(ann, x0 + 14, 24, label, size=13, bold=True)
        value = ae[key] if ae else np.nan
        _px_text(ann, x0 + 14, 64, f"{value:.0f}%" if np.isfinite(value) else "n/a",
                 size=34, color=BRAND_PURPLE, bold=True)
        _px_text(ann, x0 + 14, 100, sub.replace("&", "&amp;"), size=11, color=TEXT_SECONDARY)

    if ae and np.isfinite(ae["up"]) and np.isfinite(ae["down"]):
        sentence = (f"In months {the_noun} rose, the strategy captured about {ae['up']:.0f}% "
                    f"of its gains. In months it fell, it took about {ae['down']:.0f}% of its losses.")
        _px_text(ann, 0, 132, "<br>".join(textwrap.wrap(sentence, width=52)).replace("&", "&amp;"),
                 size=13, valign="top")

    # Capture table, top right
    TX = 392
    ty = 14
    tcols = [(TX, f"vs {bench_label}", "left"), (TX + 236, "Up", "right"),
             (TX + 312, "Down", "right"), (W - 2, "Ratio", "right")]
    for x, label, anchor in tcols:
        _px_text(ann, x, ty, label.replace("&", "&amp;"), anchor=anchor, size=13, bold=True)
    shapes.append(dict(type="line", x0=TX, x1=W, y0=ty + 15, y1=ty + 15,
                       line=dict(color=BRAND_PURPLE, width=2)))
    y = ty + 15
    for name in [n for n in ["AsymEdge", "80/20", "60/40", "S&P 500"] if n != bench_label]:
        c = captures.get(name)
        if not c:
            continue
        mid = y + 17
        is_ae = name == "AsymEdge"
        _px_text(ann, TX, mid, ("Asymmetric Edge" if is_ae else name).replace("&", "&amp;"), size=13,
                 color=BRAND_PURPLE if is_ae else TEXT_SECONDARY, bold=is_ae)
        for (x, _l, _a), key in zip(tcols[1:], ["up", "down", "ratio"]):
            v = c[key]
            text = ("n/a" if not np.isfinite(v) else (f"{v:.2f}" if key == "ratio" else f"{v:.0f}%"))
            _px_text(ann, x, mid, text, anchor="right", size=13,
                     color=TEXT_PRIMARY if is_ae else TEXT_SECONDARY, bold=is_ae)
        y += 34
        shapes.append(dict(type="line", x0=TX, x1=W, y0=y, y1=y,
                           line=dict(color=ANALYTICS_RULE, width=1)))
    if ae:
        _px_text(ann, TX, y + 18,
                 f"{ae['n']} months: {ae['n_up']} up and {ae['n_down']} down for "
                 f"{the_noun.replace('&', '&amp;')}", size=11, color=TEXT_SECONDARY)

    fig = go.Figure()
    if worst is not None and not worst.empty:
        bench_bar = bench_color or BAR_SERIES_COLORS.get(bench_label, CAPTURE_CUSTOM_BAR)
        labels = [p.strftime("%b-%y") for p in worst.index]
        fig.add_trace(go.Bar(
            x=labels, y=worst["AsymEdge"] * 100.0, name="Asymmetric Edge",
            marker=dict(color=BAR_SERIES_COLORS["AsymEdge"], cornerradius=5),
            text=[_fmt_pct(v * 100.0) for v in worst["AsymEdge"]], textposition="outside",
            textfont=dict(size=12, color=BRAND_PURPLE, family=ANALYTICS_FONT, weight=700),
            cliponaxis=False, xaxis="x2", yaxis="y2",
            hovertemplate="%{x}<br>Asymmetric Edge %{y:.2f}%<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=labels, y=worst["bench"] * 100.0, name=bench_label,
            marker=dict(color=bench_bar, cornerradius=5),
            text=[_fmt_pct(v * 100.0) for v in worst["bench"]], textposition="outside",
            textfont=dict(size=11, color=TEXT_SECONDARY, family=ANALYTICS_FONT),
            cliponaxis=False, xaxis="x2", yaxis="y2",
            hovertemplate="%{x}<br>" + bench_label + " %{y:.2f}%<extra></extra>",
        ))
        low = float(min(worst["AsymEdge"].min(), worst["bench"].min()) * 100.0)
        high = float(max(worst["AsymEdge"].max(), worst["bench"].max(), 0.0) * 100.0)
        span = high - low
        title = f"{the_noun[0].upper() + the_noun[1:]}'s {len(worst)} worst months since inception"
        _px_text(ann, 0, 236, title.replace("&", "&amp;"), size=14, bold=True)
        lx = W - 230
        for name, color in [("Asymmetric Edge", BAR_SERIES_COLORS["AsymEdge"]), (bench_label, bench_bar)]:
            shapes.append(dict(type="path", path=_round_rect_path(lx, 230, lx + 12, 242, 3),
                               fillcolor=color, line=dict(width=0)))
            _px_text(ann, lx + 18, 236, name.replace("&", "&amp;"), size=12, color=TEXT_SECONDARY)
            lx += 140
        _pixel_layout(fig, W, H, shapes, ann)
        fig.update_layout(
            barmode="group", bargap=0.22, bargroupgap=0.04,
            uniformtext=dict(mode="show", minsize=11),
            xaxis2=dict(domain=[0.07, 1.0], anchor="y2", type="category",
                        tickfont=dict(size=12, color=TEXT_PRIMARY, weight=600), fixedrange=True),
            yaxis2=dict(domain=[0.05, 0.53], anchor="x2",
                        range=[low - span * 0.16, high + span * 0.12 + 0.3],
                        ticksuffix="%", gridcolor=GRID_COLOR, zeroline=True,
                        zerolinecolor="#c9c9d3", tickfont=dict(size=12, color=TEXT_MUTED),
                        fixedrange=True),
        )
    else:
        _pixel_layout(fig, W, H, shapes, ann)
    return fig


def render_monthly_returns_section(combined, latest_date):
    if "AsymEdge" not in combined.columns:
        st.info("Monthly returns unavailable: the portfolio series did not load.")
        return
    inception = combined.index[0]
    ae_m = _monthly_returns(combined["AsymEdge"], inception)
    open_p = _open_period(latest_date)
    layout = st.pills("Layout", MONTHLY_LAYOUTS, default=MONTHLY_LAYOUTS[0],
                      selection_mode="single", key="monthly_layout") or MONTHLY_LAYOUTS[0]
    # Compare against (added October 29, 2026): the 80/20 stays the default
    # as the primary benchmark; 60/40, the S&P 500 or any typed-in ticker can
    # be swapped in for the vs column and the hover.
    choices = [b for b in ("80/20", "60/40", "S&P 500") if b in combined.columns]
    default = PRIMARY_BENCHMARK if PRIMARY_BENCHMARK in choices else (choices[0] if choices else None)
    pick = st.pills("Compare against", choices + [CAPTURE_CUSTOM_LABEL], default=default,
                    selection_mode="single", key="monthly_bench") or default
    bench_label, spx_m, custom = pick, None, None
    if pick == CAPTURE_CUSTOM_LABEL:
        col, _ = st.columns([1, 3], vertical_alignment="bottom")
        raw = col.text_input("ETF ticker", value=CAPTURE_CUSTOM_DEFAULT, max_chars=12,
                             key="monthly_ticker",
                             help="Any ticker Yahoo Finance carries, such as QQQ, VTI or SCHD.")
        ticker = re.sub(r"[^A-Za-z0-9.\-^=]", "", raw or "").upper() or CAPTURE_CUSTOM_DEFAULT
        spx_m = _monthly_custom_all(ticker, combined, latest_date)
        if spx_m is None:
            st.warning(f"Couldn't load enough price history for {ticker}. Showing the 80/20 instead.")
            bench_label = default
        else:
            bench_label, custom = ticker, ticker
    if spx_m is None and bench_label in combined.columns:
        spx_m = _monthly_returns(combined[bench_label], inception)
    if layout == MONTHLY_LAYOUTS[1]:
        fig = build_monthly_returns_tall_figure(ae_m, spx_m, open_p, latest_date,
                                                bench_label=bench_label)
        st.plotly_chart(fig, use_container_width=False,
                        config=chart_config("Monthly Returns (newsletter)", static=True),
                        key="monthly_fig_tall")
    else:
        fig = build_monthly_returns_figure(ae_m, spx_m, open_p, latest_date,
                                           bench_label=bench_label)
        st.plotly_chart(fig, use_container_width=False,
                        config=chart_config("Monthly Returns", static=True),
                        key="monthly_fig_wide")
    open_note = ""
    if open_p is not None:
        through = f"{pd.Timestamp(latest_date):%B} {pd.Timestamp(latest_date).day}"
        if _open_month_anchored(latest_date):
            open_note = (
                f"{open_p.strftime('%B %Y')} is month to date through {through}, tied to Fidelity's "
                f"reported month-to-date return; it becomes final when the month closes. "
            )
        else:
            open_note = (
                f"{open_p.strftime('%B %Y')} is month to date through {through} and is estimated "
                f"from the daily reconstruction until Fidelity's figure is entered. "
            )
    _footnote(
        "Monthly time-weighted returns. Closed months are anchored to Fidelity's reported "
        "returns for the account and tie exactly. " + open_note +
        "The Year column compounds the months shown, so the current year is year to date. "
        + MONTHLY_BENCH_FOOTNOTE.get(bench_label,
            f"vs {bench_label} is the difference in percentage points from {bench_label} (total "
            "return with dividends reinvested, Yahoo Finance) over the same months; a year shows "
            "n/a when the ticker's history does not cover every month of it. ") +
        "January 2024 is "
        "measured from the January 2, 2024 inception close. Hover a cell for both returns to two "
        "decimals. All figures are before taxes and advisory fees."
    )
    newsletter_caption(
        f"Asymmetric Edge monthly returns from {_cap_date(inception)} through "
        f"{_cap_date(latest_date)}, with each year compared to "
        f"{MONTHLY_BENCH_CAPTION.get(bench_label, bench_label)}."
        + (f" {open_p.strftime('%B %Y')} is month to date." if open_p is not None else "")
        + " " + NEWSLETTER_RETURNS_SENTENCES
    )


# ===========================================================================
# 2. WHAT DROVE THE MONTH (return attribution)
# ===========================================================================

def compute_month_attribution(period, ae_series, holdings_values, totals, prices, flows=None):
    """Each holding's contribution to one month's return.

    Changed October 29, 2026. When the Fidelity ledger is available (flows),
    each holding's daily piece is its actual dollar gain that day: closing
    value minus the prior close, plus any cash it paid out (sales,
    dividends) and minus any cash put into it (purchases), divided by the
    prior close's account value. That captures trades filled at prices other
    than the close and positions bought on a month's final day for the next
    month, both of which the price-only method below missed. September 2026
    showed the gap: two rebalance days (September 8 and 30) left 0.21 points
    unexplained, and spreading that across the holdings flipped the sign of
    Japan's and broad commodities' contributions. Without the ledger, the
    price-only method below is the fallback.

    Contribution is built day by day: a holding's weight at the prior close
    (from the reconstructed holdings, so intramonth trades and deposits are
    reflected) times its adjusted-close return that day, scaled by the
    portfolio's growth so far in the month. Summed over the month, those daily
    pieces add up to the month's return exactly for a portfolio whose daily
    return is the weighted sum of its holdings. The remainder against the
    published (Fidelity-anchored) month is reported as its own line rather than
    spread across holdings: it is cash and money-market income, fees, intraday
    trade timing, and the anchoring adjustment.
    """
    s = ae_series.dropna()
    idx = s.index
    in_month = idx[idx.to_period("M") == period]
    if len(in_month) == 0:
        return None
    before = idx[idx < in_month[0]]
    if len(before):
        dates = [before[-1]] + list(in_month)
    else:
        dates = list(in_month)
    if len(dates) < 2:
        return None
    dates = pd.DatetimeIndex(dates)

    S = s.reindex(dates)
    start_val = float(S.iloc[0])
    month_return = float(S.iloc[-1]) / start_val - 1.0

    # Refuse to attribute a window the price data does not reach. Carrying
    # stale closes forward would book zero returns for the missing days and
    # push the whole gap into the cash, fees and timing line.
    if prices is None or prices.empty or prices.index.max() < dates[-1] - pd.Timedelta(days=4):
        return {"period": period, "stale_prices": True,
                "price_through": None if prices is None or prices.empty else prices.index.max()}

    hv = holdings_values.reindex(dates).ffill().fillna(0.0)
    if totals is not None and not totals.empty:
        acct = totals["account_value"].reindex(dates).ffill()
    else:
        acct = hv.sum(axis=1)
    px = _price_frame_on(prices, dates)

    use_ledger = flows is not None and not flows.empty
    contrib, weight_sum, held_growth, unpriced = {}, {}, {}, set()
    first_w, last_w, entered_on = {}, {}, {}
    n_days = len(dates) - 1
    for k in range(1, len(dates)):
        d0, d1 = dates[k - 1], dates[k]
        a0 = float(acct.loc[d0]) if pd.notna(acct.loc[d0]) else 0.0
        if a0 <= 0:
            continue
        growth = float(S.loc[d0]) / start_val
        row = hv.loc[d0]
        row1 = hv.loc[d1]
        day_flows = (flows[(flows.index > d0) & (flows.index <= d1)].sum()
                     if use_ledger else pd.Series(dtype=float))
        tickers = set(t for t, v in row.items() if v > 1.0)
        if use_ledger:
            tickers |= set(t for t, v in row1.items() if v > 1.0)
            tickers |= set(t for t, f in day_flows.items() if abs(f) >= 0.005 and t in hv.columns)
        for ticker in tickers:
            if ticker in CASH_LIKE_TICKERS:
                continue
            value = float(row.get(ticker, 0.0))
            w = value / a0 if value > 1.0 else 0.0
            if w > 0:
                weight_sum[ticker] = weight_sum.get(ticker, 0.0) + w
                first_w.setdefault(ticker, w)
                last_w[ticker] = w
            elif use_ledger and ticker not in weight_sum:
                entered_on.setdefault(ticker, d1)
            p0 = px.at[d0, ticker] if ticker in px.columns else np.nan
            p1 = px.at[d1, ticker] if ticker in px.columns else np.nan
            priced = pd.notna(p0) and pd.notna(p1) and p0 > 0
            if priced and w > 0:
                r_day = float(p1) / float(p0) - 1.0
                held_growth[ticker] = held_growth.get(ticker, 1.0) * (1.0 + r_day)
            if use_ledger:
                pnl = float(row1.get(ticker, 0.0)) - value + float(day_flows.get(ticker, 0.0))
                contrib[ticker] = contrib.get(ticker, 0.0) + growth * pnl / a0
            elif w > 0:
                if priced:
                    contrib[ticker] = contrib.get(ticker, 0.0) + growth * w * r_day
                else:
                    unpriced.add(ticker)

    rows = []
    for ticker, c in contrib.items():
        avg_w = weight_sum.get(ticker, 0.0) / n_days
        held = ticker in weight_sum
        if held and avg_w < 0.005 and abs(c) < 0.0001:
            continue
        # A position bought on the month's last trading day for the next
        # month: it gets its own row only when the slip from its purchase
        # price to that day's close is big enough to see (0.05 points).
        if not held and abs(c) < 0.0005:
            continue
        # The holding's own return over the days it was actually held this
        # month, so a position bought mid-month is not credited with moves
        # from before it was owned.
        ret = held_growth[ticker] - 1.0 if ticker in held_growth else None
        rows.append({"ticker": ticker, "avg_weight": avg_w if held else None, "return": ret,
                     "contribution": c,
                     "first_weight": first_w.get(ticker), "last_weight": last_w.get(ticker),
                     "entered_on": None if held else entered_on.get(ticker)})
    rows.sort(key=lambda r: -(r["avg_weight"] or 0.0))
    explained = sum(r["contribution"] for r in rows)
    residual = month_return - explained
    # Fold the small remainder (cash income, fees, timing and dividend-date
    # differences against the reported return) into the holdings in proportion
    # to their average weight, so the rows add up exactly to the reported month.
    # Tyler, October 22, 2026: a separate residual bar invited questions it
    # could not answer. The raw figures stay in the result for checking.
    wsum = sum((r["avg_weight"] or 0.0) for r in rows)
    for r in rows:
        r["raw_contribution"] = r["contribution"]
        if wsum > 0:
            r["contribution"] = r["contribution"] + residual * (r["avg_weight"] or 0.0) / wsum
    return {
        "period": period,
        "start": dates[0],
        "end": dates[-1],
        "month_return": month_return,
        "rows": rows,
        "residual": residual,
        "unpriced": sorted(unpriced),
        "method": "ledger" if use_ledger else "price",
    }




def render_attribution_section(portfolio_series, holdings_values, totals, prices, latest_date):
    # The heading names the selected month and says gain or loss, so it is
    # written once the month's result is known (Tyler, October 29, 2026).
    head = st.empty()
    head.markdown("## Where the Month's Return Came From")
    if holdings_values is None or holdings_values.empty:
        st.info("Attribution needs holdings_daily_values.csv from the pipeline.")
        return
    s = portfolio_series.dropna()
    inception = s.index[0]
    last_hold = holdings_values.index.max()
    open_p = _open_period(latest_date)
    periods = sorted({p for p in s.index.to_period("M")
                      if p.to_timestamp() <= last_hold and p >= inception.to_period("M")})
    # Keep the months the holdings data fully covers (plus the open month).
    usable = [p for p in periods
              if p == open_p or (p.to_timestamp(how="end") <= last_hold + pd.Timedelta(days=4))]
    if not usable:
        st.info("No month has enough holdings data for an attribution yet.")
        return
    options = usable[-6:]
    labels = [p.strftime("%b-%y") + (" (MTD)" if p == open_p else "") for p in options]
    closed_labels = [lab for p, lab in zip(options, labels) if p != open_p]
    default = closed_labels[-1] if closed_labels else labels[-1]
    choice = st.pills("Select month", labels, default=default, selection_mode="single",
                      key="attr_month")
    if not choice:
        choice = default
    period = options[labels.index(choice)]
    result = compute_month_attribution(period, s, holdings_values, totals, prices,
                                       flows=load_position_flows())
    if result is not None and result.get("stale_prices"):
        through = result["price_through"]
        st.info(
            f"Prices for {period.strftime('%B %Y')} are not available yet"
            + (f" (they currently run through {_long_date(through)})" if through is not None else "")
            + ". The attribution will appear once Yahoo Finance or the price snapshot covers the month."
        )
        return
    if result is None or not result["rows"]:
        st.info("Not enough data to attribute that month.")
        return
    is_open = period == open_p
    title = attribution_title(result["month_return"], period)
    head.markdown(f"## {title}")
    st.plotly_chart(build_attribution_figure(result, is_open), use_container_width=False,
                    config=chart_config(f"{title} {period.strftime('%Y')}", static=True),
                    key=f"attr_fig_{period}")
    if not is_open:
        total_src = "Fidelity's reported return for the month"
    elif _open_month_anchored(latest_date):
        total_src = "Fidelity's reported month-to-date return"
    else:
        total_src = "estimated from the daily reconstruction, as the month is still open"
    unpriced = ""
    if result["unpriced"]:
        unpriced = (" Holdings without a price history (" + ", ".join(result["unpriced"]) +
                    ") are reconciled into the other holdings.")
    if result.get("method") == "ledger":
        how = ("is built day by day from each position's actual dollar gain in the account: its "
               "value at the close, less its value at the prior close, plus any cash it paid out "
               "(sales and dividends) and less any cash put into it (purchases, at the prices the "
               "trades actually filled), divided by the account's value at the prior close and "
               "compounded through the month. Trades and dividends come from the Fidelity "
               "transaction history. A position bought on the month's last trading day for the "
               "next month can appear with no average weight, because the move from its purchase "
               "price to that day's close counts in this month. ")
        recon = ("Contributions are reconciled to that total: the small remaining difference "
                 "(cash interest and rounding) is spread across the holdings in proportion to "
                 "their weight.")
    else:
        how = ("is built day by day from each holding's weight at the prior close times its "
               "adjusted-close return, compounded through the month. ")
        recon = ("Contributions are reconciled to that total: the difference between the sum of "
                 "the funds' price moves and the account's reported return (cash income, fees, "
                 "and trade timing) is spread across the holdings in proportion to their weight.")
    _footnote(
        f"{period.strftime('%B %Y')}, measured from the {_long_date(result['start'])} close to the "
        f"{_long_date(result['end'])} close. Contribution, the share of the month's return each "
        f"holding produced (in percentage points), {how}"
        "Avg. weight is the average of the holding's weights at each prior close, and Return is "
        "the fund's own adjusted-close return over the days it was held. A holding's contribution "
        "can differ in sign from its return when its weight changed during the month, because "
        f"its gains and losses then landed on different amounts of money. The total is {total_src}. "
        + recon + unpriced
    )
    how_short = ("from actual gains in my account"
                 if result.get("method") == "ledger" else
                 "from each holding's weight and return")
    newsletter_caption(
        f"Each holding's contribution to my return, "
        f"{_cap_date(result['start'])} through {_cap_date(result['end'])}, {how_short}. "
        "Fund returns from Yahoo Finance (adjusted close). " + NEWSLETTER_CLOSE
    )


# ===========================================================================
# 3. REBALANCE LOG
# ===========================================================================

def _weights_at(hv, totals, date):
    """Weights (percent) at a date's close, with uninvested cash and
    money-market balances grouped as 'Cash'."""
    row = hv.loc[date]
    values = {t: float(v) for t, v in row.items() if v > 1.0 and t not in CASH_LIKE_TICKERS}
    cash = float(sum(row.get(t, 0.0) for t in CASH_LIKE_TICKERS if t in row.index))
    if totals is not None and date in totals.index:
        cash += max(float(totals.at[date, "cash"]), 0.0)
    total = sum(values.values()) + cash
    if total <= 0:
        return {}
    w = {t: v / total * 100.0 for t, v in values.items()}
    if cash > 0:
        w["Cash"] = cash / total * 100.0
    return w


def compute_rebalance_log(holdings_values, totals, prices):
    """One row per month-end rebalance since inception, oldest first.

    After-trade weights are the rebalance day's closing holdings (or the
    intended basket where ALLOC_HISTORY_EXECUTION_CORRECTIONS or an active
    month-start override applies, matching the allocation chart). Before-trade
    weights are the prior close's holdings drifted by the rebalance day's
    price moves.
    """
    if holdings_values is None or holdings_values.empty:
        return []
    hv = holdings_values.fillna(0.0).sort_index()
    inception = pd.Timestamp(ALLOC_HISTORY_START)
    rebalances = sorted(d for d in find_rebalance_dates(hv) if d > inception)
    override = load_month_start_override()
    override_date = override["period_start_date"] if override else ""
    px = _price_frame_on(prices, hv.index) if prices is not None else pd.DataFrame()

    rows = []
    for date in rebalances:
        pos = hv.index.get_loc(date)
        if pos == 0:
            continue
        prev = hv.index[pos - 1]
        before = _weights_at(hv, totals, prev)
        # Drift the prior close forward by the rebalance day's moves.
        drifted = {}
        for t, w in before.items():
            factor = 1.0
            if t != "Cash" and t in px.columns:
                p0, p1 = px.at[prev, t], px.at[date, t]
                if pd.notna(p0) and pd.notna(p1) and p0 > 0:
                    factor = float(p1) / float(p0)
            drifted[t] = w * factor
        dsum = sum(drifted.values())
        before = {t: v / dsum * 100.0 for t, v in drifted.items()} if dsum > 0 else before

        key = date.strftime("%Y-%m-%d")
        correction = ALLOC_HISTORY_EXECUTION_CORRECTIONS.get(key)
        if correction is None and override and key == override_date:
            correction = override["weights"]
        if correction:
            csum = sum(float(v) for v in correction.values())
            after = {t: float(v) / csum * 100.0 for t, v in correction.items()}
        else:
            after = _weights_at(hv, totals, date)
        if not after:
            continue

        def held(weights, t):
            threshold = 2.0 if t == "Cash" else 0.5
            return weights.get(t, 0.0) >= threshold

        names = set(before) | set(after)
        added = sorted((t for t in names if held(after, t) and not held(before, t)),
                       key=lambda t: -after[t])
        exited = sorted((t for t in names if held(before, t) and not held(after, t)),
                        key=lambda t: -before[t])
        continuing = [t for t in names if t != "Cash" and held(before, t) and held(after, t)]
        shifts = sorted(((t, after[t] - before[t]) for t in continuing
                         if abs(after[t] - before[t]) >= 0.5), key=lambda x: -abs(x[1]))[:3]
        turnover = 0.5 * sum(abs(after.get(t, 0.0) - before.get(t, 0.0)) for t in names)
        rows.append({
            "date": date,
            "period": (date.to_period("M") + 1),
            "added": [(t, after[t]) for t in added],
            "exited": [(t, before[t]) for t in exited],
            "shifts": shifts,
            "turnover": turnover,
            "n_holdings": sum(1 for t in after if t != "Cash" and after[t] >= 0.5),
            "new_holding": any(t != "Cash" for t in added),
        })
    return rows




def render_rebalance_log_section(holdings_values, totals, prices):
    rows = compute_rebalance_log(holdings_values, totals, prices)
    if not rows:
        st.info("No month-end rebalance found in the holdings history yet.")
        return
    view = st.pills("Show", ["Last 12 months", "Since inception"], default="Last 12 months",
                    selection_mode="single", key="rebal_view")
    if not view:
        view = "Last 12 months"
    shown = rows[-12:] if view == "Last 12 months" else rows
    # The tiles describe the rows on screen, so they follow the pills.
    stats = {
        "avg_turnover": float(np.mean([r["turnover"] for r in shown])),
        "new_months": sum(1 for r in shown if r["new_holding"]),
        "n": len(shown),
        "avg_holdings": float(np.mean([r["n_holdings"] for r in shown])),
    }
    fig = build_rebalance_log_figure(list(reversed(shown)), stats)
    st.plotly_chart(fig, use_container_width=False,
                    config=chart_config(f"Rebalance Log {view}", static=True),
                    # A key per view makes the browser draw a fresh chart when the
                    # pills change; with one shared identity the old figure stayed up.
                    key=f"rebal_fig_{view}")
    _footnote(
        "Each row is the month the new allocation applies to; its trades are placed on the prior "
        "month's final trading day (Traded). After-trade weights come from that day's closing "
        "holdings; before-trade weights are the prior close drifted by the rebalance day's price "
        "moves. Added and Exited list positions crossing 0.5% of the portfolio, with uninvested cash "
        "and money-market balances grouped as Cash and listed at 2% or more. Reweighted shows the "
        "largest changes, in percentage points, among continuing holdings. Turnover is one-way: the "
        f"share of the portfolio bought, which equals the share sold. The tiles cover the {len(shown)} "
        f"month-end rebalances shown ({'the last 12 months' if view == 'Last 12 months' else 'since inception'}). Computed from the reconstructed holdings, so the log "
        "refreshes whenever the pipeline does."
    )


# ===========================================================================
# 4. DRAWDOWNS OVER TIME
# ===========================================================================

def find_drawdown_episodes(series):
    """Every peak-to-recovery decline in a daily series, deepest first."""
    s = series.dropna()
    if len(s) < 2:
        return []
    dd = s / s.cummax() - 1.0
    idx, vals = s.index, dd.values
    episodes, cur = [], None
    for i in range(len(s)):
        v = vals[i]
        if v < -1e-9:
            if cur is None:
                cur = {"peak": idx[i - 1] if i > 0 else idx[i], "trough": idx[i], "depth": float(v)}
            elif v < cur["depth"]:
                cur["trough"], cur["depth"] = idx[i], float(v)
        elif cur is not None:
            cur["recovered"] = idx[i]
            episodes.append(cur)
            cur = None
    if cur is not None:
        cur["recovered"] = None
        episodes.append(cur)
    return sorted(episodes, key=lambda e: e["depth"])


# --- Drawdowns Over Time (October 22, 2026 redesign; mockup variation 9) ----------
# Asymmetric Edge is a standard-weight purple line over a fill that deepens with
# depth. Benchmarks are dashed lines in their usual colors, except the S&P 500,
# which is drawn in a darker slate on this chart only so its declines carry
# visual weight. "Rank by" picks whose five deepest episodes are numbered on the
# chart and listed in the table; "Show" picks which portfolios are drawn and
# compared; "Period" picks the start and end month. Drawdowns restart at the
# period start: every line measures from its own highest close inside the period.
DD_KEYS = ["AsymEdge", "80/20", "60/40", "S&P 500"]
DD_LINE = {"AsymEdge": BRAND_PURPLE, "80/20": "#4361EE", "60/40": "#4CC9F0", "S&P 500": "#6B7280"}
DD_DASH = {"80/20": "7px,4px", "60/40": "3px,4px", "S&P 500": "11px,4px,3px,4px"}
DD_WIDTH = {"AsymEdge": 2.4, "80/20": 2.0, "60/40": 2.6, "S&P 500": 2.0}
DD_TEXT = {"AsymEdge": BRAND_PURPLE, "80/20": "#3451D1", "60/40": "#0B7AA3", "S&P 500": "#4B5563"}
DD_DEFAULT_SHOW = ["AsymEdge", "S&P 500"]
DD_LEGEND_PAD = "\u2003\u2003"   # breathing room between legend entries
DD_DAILY_MAX_SESSIONS = 130     # periods this short plot every close instead of weekly lows
DD_COUNT_WORDS = ["No", "The deepest", "Two deepest", "Three deepest", "Four deepest", "Five deepest"]
DD_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]


def _dd_text_width(text, size, bold=False):
    """Approximate DM Sans width in px, used only to size table columns."""
    w = 0.0
    for ch in str(text):
        if ch.isdigit():
            w += 0.6
        elif ch in ".,' ":
            w += 0.27
        elif ch == "%":
            w += 0.84
        elif ch in (MINUS, "+", "-"):
            w += 0.6
        elif ch == "/":
            w += 0.4
        elif ch == "&":
            w += 0.68
        elif ch != ch.lower():
            w += 0.68
        else:
            w += 0.53
    return w * size * (1.06 if bold else 1.0)


def _dd_short_date(d):
    d = pd.Timestamp(d)
    return f"{d:%b} {d.day}, {d.year}"


def _dd_window_drawdown(series):
    s = series.dropna()
    return (s / s.cummax() - 1.0) * 100.0


def build_underwater_chart(window, shown, rank, episodes):
    """Underwater chart for the selected period. window: daily values (columns
    in DD_KEYS), already cut to the period. episodes: the ranked portfolio's
    deepest episodes inside the period, deepest first."""
    start, end = window.index[0], window.index[-1]
    daily = len(window) <= DD_DAILY_MAX_SESSIONS
    if daily:
        bucket = pd.Series(np.arange(len(window)), index=window.index)
    else:
        bucket = pd.Series(window.index.to_period("W-FRI").astype(str), index=window.index)
    bucket_last = window.index.to_series().groupby(bucket.values).max()

    curves, worst = {}, {}
    for k in shown:
        dd = _dd_window_drawdown(window[k])
        lows = dd.groupby(bucket.reindex(dd.index).values).min()
        x = [start] + list(bucket_last.reindex(lows.index).values)
        y = [0.0] + list(lows.values)
        curves[k] = (x, y)
        t = dd.idxmin()
        worst[k] = (float(dd.min()), t, pd.Timestamp(bucket_last[bucket[t]]))

    lo = min([v for v, _t, _x in worst.values()] + [0.0])
    step = 0.5 if lo > -3 else 1 if lo > -6 else 2 if lo > -12 else 4 if lo > -24 else 5
    ymin = min(-2 * step, np.floor((lo - 0.55 * step) / step) * step)

    fig = go.Figure()
    # Benchmarks first so Asymmetric Edge draws on top.
    for k in ["S&P 500", "60/40", "80/20"]:
        if k not in curves:
            continue
        x, y = curves[k]
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines", name=series_label(k) + DD_LEGEND_PAD, legendrank=DD_KEYS.index(k) + 1,
            line=dict(color=DD_LINE[k], width=DD_WIDTH[k], dash=DD_DASH[k]),
            hovertemplate=series_label(k).replace("&", "&amp;") + ": %{y:.1f}%<extra></extra>",
        ))
    if "AsymEdge" in curves:
        x, y = curves["AsymEdge"]
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines", name="Asymmetric Edge" + DD_LEGEND_PAD, legendrank=1,
            line=dict(color=DD_LINE["AsymEdge"], width=DD_WIDTH["AsymEdge"]),
            fill="tozeroy",
            # Shading deepens with depth: lightest at 0%, darkest at the low point.
            fillgradient=dict(type="vertical",
                              colorscale=[[0.0, "rgba(58,12,163,0.26)"], [1.0, "rgba(58,12,163,0.04)"]]),
            hovertemplate="Asymmetric Edge: %{y:.1f}%<extra></extra>",
        ))

    # Each portfolio's worst point: a ringed dot and its depth and date.
    HEIGHT, M_T, M_B = 470, 44, 84
    plot_h = HEIGHT - M_T - M_B
    span = max(1.0, (end - start).total_seconds())
    labels = []
    for k, (v, t, xb) in worst.items():
        if v > -0.05:
            continue
        fig.add_trace(go.Scatter(
            x=[xb], y=[v], mode="markers", showlegend=False, hoverinfo="skip",
            marker=dict(size=11, color=DD_LINE[k], line=dict(color="#ffffff", width=2)),
        ))
        frac = (xb - start).total_seconds() / span
        labels.append(dict(k=k, v=v, x=xb, frac=frac, py=v / ymin * plot_h, date=_dd_short_date(t)))
    labels.sort(key=lambda d: d["py"])
    for i in range(1, len(labels)):
        prev, cur = labels[i - 1], labels[i]
        if abs(cur["frac"] - prev["frac"]) < 0.09 and cur["py"] - prev["py"] < 30:
            cur["py"] = prev["py"] + 30
    annotations = []
    for d in labels:
        right = d["frac"] > 0.86
        annotations.append(dict(
            x=d["x"], y=d["v"], xref="x", yref="y", showarrow=False,
            xanchor="right" if right else "left", xshift=-10 if right else 10,
            yanchor="middle", yshift=-(d["py"] - d["v"] / ymin * plot_h),
            align="right" if right else "left",
            text=(f"<b>{_fmt_pct(d['v'])}</b><br>"
                  f"<span style='font-size:11px;color:{TEXT_MUTED}'>{d['date']}</span>"),
            font=dict(size=13, color=DD_TEXT[d["k"]], family=ANALYTICS_FONT),
        ))

    # The ranked portfolio's episodes: soft bands with a numbered badge above.
    shapes = []
    for i, e in enumerate(episodes):
        x0 = pd.Timestamp(e["peak"])
        x1 = pd.Timestamp(e["recovered"]) if e["recovered"] is not None else end
        shapes.append(dict(type="rect", xref="x", yref="paper", x0=x0, x1=x1, y0=0, y1=1,
                           fillcolor="rgba(40,36,70,0.045)", line=dict(width=0), layer="below"))
        mid = x0 + (x1 - x0) / 2
        shapes.append(dict(type="circle", xref="x", yref="paper", xsizemode="pixel", ysizemode="pixel",
                           xanchor=mid, yanchor=1, x0=-10, x1=10, y0=8, y1=28,
                           fillcolor="#F3F3F6", line=dict(color="#D5D6DD", width=1)))
        annotations.append(dict(x=mid, y=1, xref="x", yref="paper", yshift=18, yanchor="middle", showarrow=False,
                                text=f"<b>{i + 1}</b>", font=dict(size=11, color=TEXT_PRIMARY,
                                                                 family=ANALYTICS_FONT)))

    tick_dates, tick_labels = make_x_axis_labels(start, end)
    fig.update_layout(
        **DARK_LAYOUT,
        height=HEIGHT,
        margin=dict(t=M_T, b=M_B, l=60, r=30),
        yaxis=dict(ticksuffix="%", dtick=step, range=[ymin, step * 0.08], gridcolor="#EDEDF1",
                   zeroline=True, zerolinecolor="#C9C9D3", tickfont=dict(size=16, color=TEXT_MUTED),
                   fixedrange=True),
        xaxis=dict(tickmode="array", tickvals=tick_dates, ticktext=tick_labels,
                   gridcolor="rgba(0,0,0,0)", tickfont=dict(size=16, color=TEXT_MUTED), ticklabelstandoff=10,
                   range=[start - timedelta(days=2), end + timedelta(days=2)],
                   hoverformat="%B %-d, %Y" if daily else "Week ending %b %-d, %Y"),
        legend=dict(orientation="h", yanchor="top", y=-0.13, xanchor="center", x=0.5,
                    font=dict(size=16, color=TEXT_SECONDARY, weight=500)),
        hovermode="x unified",
        hoverlabel=dict(font=dict(family=ANALYTICS_FONT, size=13)),
        shapes=shapes,
        annotations=annotations,
    )
    return fig


def build_drawdown_rank_table(rows, rank, compare):
    """Deepest-episode table. rows: dicts with rank, depth, peak, trough,
    recovered, duration (display strings) plus compare values keyed by series.
    Columns are sized to their content and the spare width is shared evenly
    between them, so no column drifts away from its neighbors. Comparison
    columns are shaded and centered."""
    W = ANALYTICS_WIDTH
    HEAD_H, ROW_H = 40, 38
    cols = [
        dict(key="rank", head="Rank", align="left"),
        dict(key="depth", head="Depth", align="right", size=14, bold=True),
        dict(key="peak", head="Peak", align="left"),
        dict(key="trough", head="Low point", align="left"),
        dict(key="recovered", head="Recovered", align="left"),
        dict(key="duration", head="Duration", align="right"),
    ] + [dict(key=k, head=series_label(k), align="center", same=True) for k in compare]
    for c in cols:
        w = _dd_text_width(c["head"], 12 if c.get("same") else 13, True)
        for r in rows:
            bold = c.get("bold") or (c.get("same") and c["key"] == "AsymEdge") or \
                (c["key"] == "recovered" and r.get("open"))
            w = max(w, 20 if c["key"] == "rank" else _dd_text_width(r[c["key"]], c.get("size", 13), bold))
        c["w"] = np.ceil(w) + 2 + (16 if c.get("same") else 0)
    used = 16 + sum(c["w"] for c in cols)
    gap = max(12.0, min(44.0, (W - used) / max(1, len(cols) - 1)))
    x = 0.0
    for i, c in enumerate(cols):
        c["x0"] = x
        x += c["w"] + (gap if i else 8)
        c["x1"] = x
    H = HEAD_H + ROW_H * len(rows) + 4
    shapes, ann = [], []
    shapes.append(dict(type="rect", x0=0, x1=W, y0=0, y1=HEAD_H, fillcolor=ANALYTICS_HEADER_BG,
                       line_width=0, layer="below"))
    for c in cols:
        if c.get("same"):
            shapes.append(dict(type="rect", x0=c["x1"] - c["w"], x1=c["x1"], y0=0, y1=HEAD_H,
                               fillcolor="#F0EEF7", line_width=0, layer="below"))
            shapes.append(dict(type="rect", x0=c["x1"] - c["w"], x1=c["x1"], y0=HEAD_H, y1=H - 4,
                               fillcolor="#F8F7FC", line_width=0, layer="below"))

    def place(c):
        if c["align"] == "right":
            return c["x1"], "right"
        if c["align"] == "center":
            return c["x1"] - c["w"] / 2, "center"
        return c["x1"] - c["w"], "left"

    for c in cols:
        px, anchor = place(c)
        _px_text(ann, px, HEAD_H / 2, c["head"].replace("&", "&amp;"), anchor=anchor,
                 size=12 if c.get("same") else 13, bold=True,
                 color=DD_TEXT.get(c["key"], TEXT_PRIMARY) if c.get("same") else TEXT_PRIMARY)
    shapes.append(dict(type="line", x0=0, x1=W, y0=HEAD_H, y1=HEAD_H,
                       line=dict(color=BRAND_PURPLE, width=2)))
    for i, r in enumerate(rows):
        top = HEAD_H + i * ROW_H
        mid = top + ROW_H / 2
        shapes.append(dict(type="line", x0=0, x1=W, y0=top + ROW_H, y1=top + ROW_H,
                           line=dict(color=ANALYTICS_RULE, width=1)))
        for c in cols:
            px, anchor = place(c)
            if c["key"] == "rank":
                shapes.append(dict(type="circle", x0=px, x1=px + 20, y0=mid - 10, y1=mid + 10,
                                   fillcolor="#F3F3F6", line=dict(color="#D5D6DD", width=1)))
                _px_text(ann, px + 10, mid, r["rank"], anchor="center", size=11, bold=True)
                continue
            color, bold, size = TEXT_SECONDARY, False, 13
            if c["key"] == "depth":
                color, bold, size = DD_TEXT[rank], True, 14
            elif c["key"] == "recovered" and r.get("open"):
                color, bold = TEXT_PRIMARY, True
            elif c.get("same"):
                color = BRAND_PURPLE if c["key"] == "AsymEdge" else TEXT_PRIMARY
                bold = c["key"] == "AsymEdge"
            _px_text(ann, px, mid, r[c["key"]], anchor=anchor, size=size, color=color, bold=bold)
    return _pixel_layout(go.Figure(), W, int(H), shapes, ann)


def _dd_month_index(ts):
    ts = pd.Timestamp(ts)
    return ts.year * 12 + ts.month - 1


def _dd_clamp_period(which):
    """Keep the start month on or before the end month. Moving one past the
    other pulls the other along. Months outside the data are allowed in the
    pickers; the chart simply stops at the first or last available day."""
    def mi(prefix):
        return int(st.session_state[f"{prefix}_y"]) * 12 + DD_MONTHS.index(st.session_state[f"{prefix}_m"])
    def put(prefix, v):
        st.session_state[f"{prefix}_y"] = v // 12
        st.session_state[f"{prefix}_m"] = DD_MONTHS[v % 12]
    f, t = mi("dd_from"), mi("dd_to")
    if f > t:
        if which == "from":
            put("dd_to", f)
        else:
            put("dd_from", t)


def _dd_reset_period():
    lo, hi = st.session_state.get("dd_bounds", (None, None))
    if lo is None:
        return
    st.session_state["dd_from_y"], st.session_state["dd_from_m"] = lo // 12, DD_MONTHS[lo % 12]
    st.session_state["dd_to_y"], st.session_state["dd_to_m"] = hi // 12, DD_MONTHS[hi % 12]


def _dd_rank_changed():
    rank = st.session_state.get("dd_rank")
    show = list(st.session_state.get("dd_show") or [])
    if rank and rank not in show:
        st.session_state["dd_show"] = show + [rank]


def render_underwater_section(combined, latest_date):
    if "AsymEdge" not in combined.columns:
        st.info("Drawdowns unavailable: the portfolio series did not load.")
        return
    keys = [k for k in DD_KEYS if k in combined.columns]
    label_of = {k: series_label(k) for k in keys}
    key_of = {v: k for k, v in label_of.items()}
    data = combined[keys].sort_index()
    data = data[data.index <= pd.Timestamp(latest_date)].ffill()
    lo_mi, hi_mi = _dd_month_index(data.index[0]), _dd_month_index(data.index[-1])

    ss = st.session_state
    ss["dd_bounds"] = (lo_mi, hi_mi)
    ss.setdefault("dd_rank", label_of["AsymEdge"])
    ss.setdefault("dd_show", [label_of[k] for k in DD_DEFAULT_SHOW if k in label_of])
    ss.setdefault("dd_from_y", lo_mi // 12)
    ss.setdefault("dd_from_m", DD_MONTHS[lo_mi % 12])
    ss.setdefault("dd_to_y", hi_mi // 12)
    ss.setdefault("dd_to_m", DD_MONTHS[hi_mi % 12])

    st.pills("Rank by", [label_of[k] for k in keys], selection_mode="single", key="dd_rank",
             on_change=_dd_rank_changed)
    st.pills("Show", [label_of[k] for k in keys], selection_mode="multi", key="dd_show")
    years = list(range(lo_mi // 12, hi_mi // 12 + 1))
    c1, c2, c3, c4, c5 = st.columns([1.25, 0.9, 1.25, 0.9, 1.1], vertical_alignment="bottom")
    c1.selectbox("From", DD_MONTHS, key="dd_from_m", on_change=_dd_clamp_period, args=("from",))
    c2.selectbox("From year", years, key="dd_from_y", on_change=_dd_clamp_period, args=("from",),
                 label_visibility="hidden")
    c3.selectbox("To", DD_MONTHS, key="dd_to_m", on_change=_dd_clamp_period, args=("to",))
    c4.selectbox("To year", years, key="dd_to_y", on_change=_dd_clamp_period, args=("to",),
                 label_visibility="hidden")
    c5.button("Since inception", key="dd_reset", on_click=_dd_reset_period)

    rank = key_of.get(ss.get("dd_rank")) or "AsymEdge"
    picked = {key_of[v] for v in (ss.get("dd_show") or []) if v in key_of}
    shown = [k for k in DD_KEYS if k in keys and (k == rank or k in picked)]
    compare = [k for k in shown if k != rank]

    f_mi = int(ss["dd_from_y"]) * 12 + DD_MONTHS.index(ss["dd_from_m"])
    t_mi = int(ss["dd_to_y"]) * 12 + DD_MONTHS.index(ss["dd_to_m"])
    f_mi, t_mi = max(lo_mi, min(hi_mi, f_mi)), max(lo_mi, min(hi_mi, t_mi))
    months = data.index.year * 12 + data.index.month - 1
    window = data[(months >= f_mi) & (months <= t_mi)]
    if len(window) < 2:
        st.info("Pick a period with at least two trading days.")
        return
    full = f_mi == lo_mi and t_mi == hi_mi
    w_start, w_end = window.index[0], window.index[-1]
    at_latest = w_end == data.index[-1]

    episodes = find_drawdown_episodes(window[rank])[:5]
    fig = build_underwater_chart(window, shown, rank, episodes)
    tag = f"{rank}_{'-'.join(shown)}_{w_start:%Y%m}_{w_end:%Y%m}".replace("/", "").replace(" ", "")
    st.plotly_chart(fig, use_container_width=True, config=chart_config("Drawdowns Over Time"),
                    key=f"dd_fig_{tag}")

    rows = []
    for i, e in enumerate(episodes):
        end = e["recovered"] if e["recovered"] is not None else w_end
        days = (pd.Timestamp(end) - pd.Timestamp(e["peak"])).days
        row = dict(rank=str(i + 1), depth=_fmt_pct(e["depth"] * 100.0),
                   peak=_dd_short_date(e["peak"]), trough=_dd_short_date(e["trough"]),
                   recovered=(_dd_short_date(e["recovered"]) if e["recovered"] is not None
                              else ("Ongoing" if at_latest else "After period")),
                   duration=f"{days}{'' if e['recovered'] is not None else '+'} days",
                   open=e["recovered"] is None)
        for k in compare:
            row[k] = _fmt_pct(compute_max_drawdown(window[k], e["peak"], end))
        rows.append(row)

    if rows:
        title = f"{DD_COUNT_WORDS[len(rows)]} {label_of[rank]} drawdowns"
        if not full:
            title += f", {w_start:%b %Y} to {w_end:%b %Y}"
        the = {"AsymEdge": "Asymmetric Edge", "80/20": "the 80/20 portfolio",
               "60/40": "the 60/40 portfolio", "S&P 500": "the S&amp;P 500"}
        note = ""
        if len(compare) == 1:
            note = (f"The shaded column shows how far {the[compare[0]]} fell between the same "
                    "peak and recovery dates.")
        elif compare:
            note = ("The shaded columns show how far each of the other portfolios fell between "
                    "the same peak and recovery dates.")
        st.markdown(
            f'<p style="font-size:1.0rem; font-weight:700; color:{TEXT_PRIMARY}; '
            f'margin:0.6rem 0 0.1rem 0;">{title.replace("&", "&amp;")}</p>'
            + (f'<p style="font-size:0.8rem; color:{TEXT_SECONDARY}; margin:0 0 0.4rem 0;">{note}</p>'
               if note else ""),
            unsafe_allow_html=True,
        )
        st.plotly_chart(build_drawdown_rank_table(rows, rank, compare), use_container_width=False,
                        config=chart_config("Deepest Drawdowns", static=True), key=f"dd_tbl_{tag}")

    period = (f"from the {_long_date(w_start)} inception" if full else f"from {_long_date(w_start)}")
    sample = ("Lines plot every daily close." if len(window) <= DD_DAILY_MAX_SESSIONS else
              "Lines plot the lowest close of each week, so every trough is shown at its full depth.")
    _footnote(
        "Drawdown is the percentage decline from each portfolio's highest close within the selected "
        f"period, {period} through {_long_date(w_end)}, so every line starts at 0%. {sample} The "
        "numbered bands are the episodes in the table, ranked by the portfolio chosen above. Duration "
        "counts calendar days from the peak to the first close back at or above it. A shaded column is "
        "that portfolio's own largest decline between the ranked portfolio's peak and recovery dates. "
        "Asymmetric Edge daily values come from a close-only reconstruction anchored to Fidelity's "
        "monthly time-weighted returns, so within-month depths are approximations. 80/20 (AOA), "
        "60/40 (AOR) and S&amp;P 500 (SPY) are total returns from Yahoo Finance, dividends reinvested."
    )
    newsletter_caption(
        f"Decline from each portfolio's previous high, {_cap_vs(shown)}, "
        f"{_cap_date(w_start)} through {_cap_date(w_end)}. " + NEWSLETTER_RETURNS_SENTENCES
    )


# ===========================================================================
# 5. THE ASYMMETRY (upside / downside capture)
# ===========================================================================

def _annualized_geo(returns):
    r = np.asarray(returns, dtype="float64")
    if len(r) == 0:
        return np.nan
    return float(np.prod(1.0 + r) ** (12.0 / len(r)) - 1.0)


def compute_capture(port_monthly, bench_monthly):
    """Morningstar-style capture ratios: the annualized geometric return in the
    benchmark's up (down) months, divided by the benchmark's own."""
    j = pd.concat([port_monthly, bench_monthly], axis=1, join="inner").dropna()
    if j.empty:
        return None
    p, b = j.iloc[:, 0], j.iloc[:, 1]
    up, down = b > 0, b < 0
    up_cap = _annualized_geo(p[up]) / _annualized_geo(b[up]) * 100.0 if up.any() else np.nan
    down_cap = _annualized_geo(p[down]) / _annualized_geo(b[down]) * 100.0 if down.any() else np.nan
    ratio = up_cap / down_cap if np.isfinite(down_cap) and down_cap > 0 else np.nan
    return {"up": up_cap, "down": down_cap, "ratio": ratio,
            "n": len(j), "n_up": int(up.sum()), "n_down": int(down.sum())}




def _capture_custom_monthly(ticker, combined, latest_date):
    """Closed monthly total returns for a typed-in ticker, anchored like the
    house series. Returns None when no usable price history comes back."""
    inception = combined.index[0]
    prices = load_custom_ticker_data((ticker,), inception.strftime("%Y-%m-%d"),
                                     pd.Timestamp(latest_date).strftime("%Y-%m-%d"))
    if prices is None or prices.empty or ticker not in prices.columns:
        return None
    daily = _price_frame_on(prices[[ticker]], combined.index)[ticker].dropna()
    if len(daily) < 30:
        return None
    monthly = _closed_only(_monthly_returns(daily, inception), latest_date)
    # A fund that launched after inception: its first month is partial, so drop it.
    if daily.index[0] > pd.Timestamp(inception) + timedelta(days=5) and len(monthly):
        monthly = monthly.iloc[1:]
    return monthly if len(monthly) >= 6 else None


def render_capture_section(combined, latest_date):
    choices = [b for b in CAPTURE_BENCHMARK_CHOICES if b in combined.columns]
    if "AsymEdge" not in combined.columns or not choices:
        st.info("Capture ratios need both the portfolio series and a benchmark.")
        return
    # S&P 500 is the default because it is the benchmark capture ratios are
    # conventionally quoted against; 80/20 (AOA) and 60/40 (AOR) can be swapped
    # in, or any ticker typed into the custom box (QQQ by default).
    default = CAPTURE_BENCHMARK if CAPTURE_BENCHMARK in choices else choices[0]
    pick = st.pills("Compare against", choices + [CAPTURE_CUSTOM_LABEL], default=default,
                    selection_mode="single", key="capture_bench")
    if not pick:
        pick = default
    inception = combined.index[0]
    monthly = {name: _closed_only(_monthly_returns(combined[name], inception), latest_date)
               for name in SERIES_ORDER if name in combined.columns}
    full_months = len(monthly["AsymEdge"])

    bench_name, custom, custom_color = pick, None, None
    if pick == CAPTURE_CUSTOM_LABEL:
        col, col_c, _ = st.columns([1, 0.55, 2.45], vertical_alignment="bottom")
        raw = col.text_input("ETF ticker", value=CAPTURE_CUSTOM_DEFAULT, max_chars=12,
                             key="capture_ticker",
                             help="Any ticker Yahoo Finance carries, such as QQQ, VTI or SCHD.")
        custom_color = col_c.color_picker("Bar color", value=CAPTURE_CUSTOM_BAR, key="capture_color")
        ticker = re.sub(r"[^A-Za-z0-9.\-^=]", "", raw or "").upper() or CAPTURE_CUSTOM_DEFAULT
        custom_monthly = _capture_custom_monthly(ticker, combined, latest_date)
        if custom_monthly is None:
            st.warning(f"Couldn't load enough price history for {ticker}. Showing the S&P 500 instead.")
            bench_name = default
        else:
            bench_name, custom = ticker, ticker
            monthly[ticker] = custom_monthly

    bench = monthly[bench_name]
    captures = {name: compute_capture(monthly[name], bench)
                for name in monthly if name != bench_name}
    both = pd.concat({"AsymEdge": monthly["AsymEdge"], "bench": bench}, axis=1).dropna()
    worst = both[both["bench"] < 0].sort_values("bench").head(8)
    file_tag = "" if bench_name == CAPTURE_BENCHMARK else f" vs {bench_name.replace('/', '-')}"
    st.plotly_chart(build_capture_figure(captures, worst, bench_label=bench_name,
                                         bench_color=custom_color if custom else None),
                    use_container_width=False,
                    config=chart_config(f"The Asymmetry{file_tag}", static=True),
                    key=f"capture_fig_{pick}_{bench_name}_{custom_color if custom else ''}"
                    .replace("/", "").replace(" ", "").replace("#", ""))
    n = captures["AsymEdge"]["n"] if captures.get("AsymEdge") else 0
    if custom:
        bench_with, bench_the = f"{custom}'s", custom
        default_note = ("The S&amp;P 500 view is the standard comparison; this view applies the same "
                        f"measure to {custom}. ")
        if n < full_months:
            default_note += (f"{custom}'s price history covers only the last {n} of the "
                             f"{full_months} closed months, so the comparison uses those. ")
        sources = (f"80/20 (AOA), 60/40 (AOR), S&amp;P 500 (SPY) and {custom} are total returns "
                   "from Yahoo Finance.")
    else:
        bench_with = {
            "S&P 500": "the S&amp;P 500's, the benchmark capture ratios are most commonly quoted against",
            "80/20": "the 80/20 portfolio's (AOA)",
            "60/40": "the 60/40 portfolio's (AOR)",
        }[bench_name]
        bench_the = {"S&P 500": "the S&amp;P 500", "80/20": "the 80/20 portfolio",
                     "60/40": "the 60/40 portfolio"}[bench_name]
        default_note = ("" if bench_name == CAPTURE_BENCHMARK else
                        "The S&amp;P 500 view is the standard comparison; this view applies the same "
                        "measure to a balanced portfolio. ")
        sources = "80/20 (AOA), 60/40 (AOR), and S&amp;P 500 (SPY) are total returns from Yahoo Finance."
    _footnote(
        f"Capture ratios compare closed monthly returns since inception ({n} months) with "
        f"{bench_with}, using the Morningstar method: the strategy's annualized return across the "
        f"months {bench_the} rose (fell), divided by {bench_the}'s annualized return across those "
        "same months. Above 100% upside or below 100% downside favors the strategy, and Ratio is "
        "upside divided by downside. " + default_note +
        "The sample is still small, so these figures will move as months accumulate. Asymmetric "
        "Edge months are anchored to Fidelity's reported returns; " + sources
    )
    bench_cap = custom if custom else CAPTION_SERIES.get(bench_name, bench_name)
    bench_own = (f"{custom}'s" if custom else
                 {"S&P 500": "the S&P 500's", "80/20": "the 80/20 portfolio's",
                  "60/40": "the 60/40 portfolio's"}.get(bench_name, f"{bench_name}'s"))
    last_closed = monthly["AsymEdge"].index[-1] if len(monthly["AsymEdge"]) else None
    through = (f", through {_cap_date(last_closed.to_timestamp(how='end'))}"
               if last_closed is not None else "")
    newsletter_caption(
        f"Asymmetric Edge vs. {bench_cap} in {bench_own} "
        f"{_NUMBER_WORDS.get(len(worst), str(len(worst)))} worst months since the "
        f"strategy went live on {_cap_date(inception)}{through}. Upside and downside capture use "
        f"all {n} closed months. " + NEWSLETTER_RETURNS_SENTENCES
    )


# ===========================================================================
# 6. ROLLING 12-MONTH RETURN
# ===========================================================================

def _spread_end_labels(items, y_range, min_gap_frac=0.055):
    """Nudge end-of-line labels apart vertically so they never overlap."""
    if not items:
        return items
    gap = (y_range[1] - y_range[0]) * min_gap_frac
    items = sorted(items, key=lambda it: it["y"])
    for i in range(1, len(items)):
        if items[i]["y_label"] - items[i - 1]["y_label"] < gap:
            items[i]["y_label"] = items[i - 1]["y_label"] + gap
    return items


def build_rolling_figure(frame, view):
    """frame: DataFrame of month-end rolling values (percent), columns = series."""
    fig = go.Figure()
    if frame.empty:
        return fig
    start, end = frame.index[0], frame.index[-1]
    tick_dates, tick_labels = make_x_axis_labels(start, end)
    ratio = view == ROLLING_SORTINO_VIEW  # a ratio, not a percent
    vmin = float(np.nanmin(frame.values))
    vmax = float(np.nanmax(frame.values))
    pad = max(0.2 if ratio else 1.0, (vmax - vmin) * 0.12)
    y_range = [min(0.0, vmin - pad), vmax + pad]
    if ratio and vmin >= 0:
        y_range[0] = 0.0  # all ratios positive: start the axis at zero, not below it
    ends = []
    for name in reversed(list(frame.columns)):
        s = frame[name].dropna()
        if s.empty:
            continue
        if view == "Excess return":
            # The primary benchmark's line leads; the others sit behind it.
            color = SERIES_COLORS.get(name, "#999")
            label = f"vs {name}"
            width, opacity = (4, 1.0) if name == PRIMARY_BENCHMARK else (2.5, 0.55)
        else:
            color = SERIES_COLORS.get(name, "#999")
            label = "Asymmetric Edge" if name == "AsymEdge" else name
            width = 4 if name == "AsymEdge" else 3
            opacity = SERIES_OPACITY.get(name, 1.0)
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        rgba = f"rgba({r},{g},{b},{opacity})"
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, mode="lines+markers", name=label,
            line=dict(color=rgba, width=width), marker=dict(size=5, color=rgba),
            hovertemplate=("%{x|%b %Y}<br>%{y:.2f}" if ratio else "%{x|%b %Y}<br>%{y:.1f}%")
            + "<extra>" + label + "</extra>",
        ))
        label_color = color if name != "S&P 500" else "#6B7280"
        if name == "60/40":
            label_color = "#1C8FB3"
        ends.append({"x": s.index[-1], "y": float(s.iloc[-1]), "y_label": float(s.iloc[-1]),
                     "text": (f"{float(s.iloc[-1]):.2f}".replace("-", "\u2212") if ratio
                              else _fmt_pct(float(s.iloc[-1]))),
                     "color": label_color})
    ends = _spread_end_labels(ends, y_range)
    annotations = [dict(x=e["x"], y=e["y_label"], xref="x", yref="y", text=f"<b>{e['text']}</b>",
                        showarrow=False, xanchor="left", xshift=10, yanchor="middle",
                        font=dict(size=14, color=e["color"], family=ANALYTICS_FONT))
                   for e in ends]
    fig.update_layout(
        **DARK_LAYOUT,
        yaxis=dict(ticksuffix="" if ratio else "%", gridcolor=GRID_COLOR, zeroline=True, zerolinecolor="#c9c9d3",
                   range=y_range, tickfont=dict(size=16, color=TEXT_MUTED)),
        xaxis=dict(tickmode="array", tickvals=tick_dates, ticktext=tick_labels,
                   gridcolor="rgba(0,0,0,0)", tickfont=dict(size=16, color=TEXT_MUTED),
                   ticklabelstandoff=10,
                   range=[start - timedelta(days=12), end + timedelta(days=45)]),
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="center", x=0.5,
                    traceorder="reversed", font=dict(size=16, color=TEXT_SECONDARY, weight=500)),
        hovermode="x unified",
        margin=dict(t=15, b=80, l=60, r=30),
        height=440,
        annotations=annotations,
    )
    return fig


# Rolling 12-month Sortino (October 29, 2026). Measured from DAILY returns:
# twelve monthly returns often hold only one or two months below T-bills, and
# the monthly figure then explodes (55.9 for the window ending February 2026).
# So it will not match the Performance Summary's monthly-based Sortino.
ROLLING_VIEWS = ["12-month return", "Excess return", "12-month volatility", "12-month Sortino"]
ROLLING_SORTINO_VIEW = "12-month Sortino"


def _rolling_sortino(daily, periods, rf_daily):
    """Sortino ratio for the 12 months ending each month-end in periods:
    (window return - T-bill return) / annualized downside deviation, the
    downside measured from daily returns below the T-bill's daily return."""
    s = daily.dropna()
    d = s.pct_change().dropna()
    if rf_daily is not None:
        rf = rf_daily.reindex(s.index).ffill().pct_change().reindex(d.index).fillna(0.0)
    else:
        rf = pd.Series(0.0, index=d.index)
    out = {}
    for p in periods:
        end = p.to_timestamp(how="end").normalize()
        start = (p - 12).to_timestamp(how="end").normalize()
        mask = (d.index > start) & (d.index <= end)
        if mask.sum() < 150:  # roughly 12 months of sessions; skip short windows
            continue
        w, wrf = d[mask], rf[mask]
        excess_total = float((1 + w).prod() - (1 + wrf).prod())
        dd = float(np.sqrt(np.mean(np.minimum(w.values - wrf.values, 0.0) ** 2)) * np.sqrt(252))
        if dd > 0:
            out[p] = excess_total / dd
    return pd.Series(out, dtype="float64")


def compute_rolling_frame(combined, latest_date, view, rf_daily=None):
    """Month-end rolling figures in percent (a ratio for the Sortino view),
    one column per series, closed months only, indexed by month-end date."""
    inception = combined.index[0]
    open_p = _open_period(latest_date)
    names = [n for n in SERIES_ORDER if n in combined.columns]
    values, rets = {}, {}
    for n in names:
        v = _month_end_values(combined[n], inception)
        if open_p is not None:
            v = v[v.index < open_p]
        values[n] = v
        rets[n] = v.pct_change().dropna()
    if view == "12-month return":
        frame = pd.DataFrame({n: (values[n] / values[n].shift(12) - 1.0) * 100.0 for n in names})
    elif view == "12-month volatility":
        frame = pd.DataFrame({n: rets[n].rolling(12).std() * np.sqrt(12) * 100.0 for n in names})
    elif view == ROLLING_SORTINO_VIEW:
        # Same windows as the other views: the first ends twelve closed months in.
        periods = rets["AsymEdge"].index[11:]
        frame = pd.DataFrame({n: _rolling_sortino(combined[n], periods, rf_daily) for n in names})
    else:
        ae12 = values["AsymEdge"] / values["AsymEdge"].shift(12) - 1.0
        frame = pd.DataFrame({n: (ae12 - (values[n] / values[n].shift(12) - 1.0)) * 100.0
                              for n in names if n != "AsymEdge"})
    frame = frame.dropna(how="all")
    if not frame.empty:
        frame.index = pd.DatetimeIndex([p.to_timestamp(how="end").normalize() for p in frame.index])
    return frame


def render_rolling_section(combined, latest_date):
    if "AsymEdge" not in combined.columns:
        st.info("Rolling returns unavailable: the portfolio series did not load.")
        return
    view = st.pills("Select view", ROLLING_VIEWS,
                    default="12-month return", selection_mode="single", key="rolling_view")
    if not view:
        view = "12-month return"
    rf_daily = None
    if view == ROLLING_SORTINO_VIEW:
        rf_daily = load_bil_daily(combined.index[0].strftime("%Y-%m-%d"),
                                  pd.Timestamp(latest_date).strftime("%Y-%m-%d"))
    frame = compute_rolling_frame(combined, latest_date, view, rf_daily=rf_daily)
    if frame.empty:
        st.info("Rolling figures need at least 12 closed months.")
        return
    st.plotly_chart(build_rolling_figure(frame, view), use_container_width=True,
                    config=chart_config(f"Rolling 12-Month {view.replace('12-month ', '').title()}"),
                    key=f"rolling_fig_{view}")
    first_full = frame.index[0]
    view_text = {
        "12-month return": "Each point is the total return for the 12 months ending that month-end.",
        "Excess return": ("Each point is Asymmetric Edge's trailing 12-month return minus the named "
                          "benchmark's over the same 12 months, in percentage points; above zero means "
                          "the strategy was ahead."),
        "12-month volatility": ("Each point is the annualized standard deviation of the 12 monthly returns "
                                "ending that month-end."),
        ROLLING_SORTINO_VIEW: (
            "Each point is the Sortino ratio for the 12 months ending that month-end: the return above "
            "T-bills (BIL) divided by annualized downside deviation, which counts only the daily returns "
            "that fell short of the T-bill return" + ("" if rf_daily is not None else
                                                     " (T-bill prices did not load, so zero is used)")
            + ". It is measured from daily returns, because 12 monthly returns can hold just one losing "
            "month and swing the ratio wildly, so it will not match the monthly-based Sortino in the "
            "Performance Summary. Asymmetric Edge's daily values within each month are approximations, "
            "as with Max DD (Daily)."),
    }[view]
    _footnote(
        f"{view_text} Only closed months are used. The first full window ends {first_full:%B %Y}, "
        "measured from the January 2, 2024 inception close. Asymmetric Edge months are anchored to "
        "Fidelity's reported returns; 80/20 (AOA), 60/40 (AOR), and S&amp;P 500 (SPY) are total returns "
        "from Yahoo Finance with dividends reinvested. Before taxes and advisory fees."
    )
    roll_desc = {
        "12-month return": "Trailing 12-month total return at each month-end",
        "Excess return": ("Asymmetric Edge's trailing 12-month return minus each benchmark's, in "
                          "percentage points, at each month-end"),
        "12-month volatility": ("Annualized volatility of the trailing 12 monthly returns at each "
                                "month-end"),
        ROLLING_SORTINO_VIEW: ("Trailing 12-month Sortino ratio (return above T-bills per unit of "
                               "downside risk) at each month-end"),
    }[view]
    newsletter_caption(
        f"{roll_desc}, {_cap_vs(list(frame.columns))}, "
        f"{_cap_date(frame.index[0])} through {_cap_date(frame.index[-1])}. "
        + NEWSLETTER_RETURNS_SENTENCES
    )


# ===========================================================================
# 7. RISK VS. RETURN
# ===========================================================================

# Hollow-point colors for the asset universe on Risk vs. Return. Each asset
# takes its Asset Universe category hue (the card text colors in
# asset_universe.json), stepped lighter for the second and third asset in a
# category so every point is distinct. Bitcoin is orange everywhere on the
# dashboard; its point is one step brighter than the crypto card text so it
# stays clear of HGER's brown. All pass 3:1 contrast on white. Tickers not
# listed fall back to their category color.
ASSET_POINT_COLORS = {
    "QQQ": "#1F4D87", "IWM": "#4F7FC4",          # U.S. equities (blues)
    "DXJ": "#14543E", "EMXC": "#2F8A66",         # International (greens)
    "HGER": "#7E4A0A", "GLD": "#A57A08",         # Commodities (amber / gold)
    "IBIT": "#C8650A",                           # Crypto (bitcoin orange)
    "BTAL": "#4A463D", "TLT": "#6E6A62", "BIL": "#8C867C",  # Defensive (warm grays)
}


# --- Risk vs. Return (October 23, 2026 redesign; mockup option C) ------------------
# The volatility axis is linear up to just past the most volatile point at or
# below RR_OUTLIER_VOL, then breaks; anything more volatile (bitcoin, or a
# volatile custom ticker) sits in a narrow compressed strip so it stays on the
# chart without stretching it. The dashed 80/20 line stops at the break. Cash
# (BIL) is hidden by default and bitcoin (IBIT) shown; both can be toggled.
# A period picker recomputes every point for any span of three months or more,
# and a custom ticker can be added in a color of the viewer's choosing.
RR_OUTLIER_VOL = 25.0           # percent; points above this go in the compressed strip
RR_STRIP_FRAC = 0.13            # share of the plot width given to the compressed strip
RR_GAP_FRAC = 0.017             # the white gap that marks the break
RR_TOGGLES = {"Cash (BIL)": "BIL", "Bitcoin (IBIT)": "IBIT"}
RR_DEFAULT_SHOW = ["Bitcoin (IBIT)"]
# Dot toggles (October 27, 2026). One "Show" pill per dot: the four series, then
# every visible Asset Universe ETF in universe order (cash and bitcoin keep the
# names above). Everything is shown by default except cash, which matches the
# chart before the toggles existed. The axes are fit to the visible dots only,
# so hiding bitcoin also removes the compressed strip; the dashed 80/20 line is
# computed whether or not the 80/20 dot is shown.
RR_DEFAULT_HIDDEN = ["Cash (BIL)"]
RR_PRESETS = ["Strategy + benchmarks", "Everything"]
RR_SHOW_KEY = "rr_dots"


def _rr_show_options():
    """Ordered {pill label: (kind, id)} for the Show pills. The option list is
    fixed by SERIES_ORDER and the Asset Universe, not by what loaded, so a
    benchmark that fails to download does not reset the viewer's choices."""
    opts = {series_label(n): ("family", n) for n in SERIES_ORDER}
    names = {t: label for label, t in RR_TOGGLES.items()}
    seen = set()
    for cat in load_asset_universe().get("categories", []):
        if not cat.get("visible", True):
            continue
        for a in cat.get("assets", []):
            t = str(a.get("ticker", "")).strip().upper()
            if t and t not in seen and t != "SPY":
                seen.add(t)
                opts[names.get(t, t)] = ("asset", t)
    return opts


def _rr_apply_preset(labels):
    """Presets pill callback: set the Show pills, then clear itself so it acts
    like a button and can be clicked again."""
    ss = st.session_state
    pick = ss.get("rr_preset")
    if pick == "Strategy + benchmarks":
        family = {series_label(n) for n in SERIES_ORDER}
        ss[RR_SHOW_KEY] = [l for l in labels if l in family]
    elif pick == "Everything":
        ss[RR_SHOW_KEY] = list(labels)
    ss["rr_preset"] = None


def _rr_join(names):
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
RR_MIN_MONTHS = 3
# Risk measure toggle (October 27, 2026). "Downside risk (Sortino)" swaps the x
# axis to annualized downside deviation, the Sortino denominator, and starts the
# dashed line at the T-bill return so its slope is the 80/20 Sortino ratio.
RR_MEASURES = ["Volatility", "Downside risk (Sortino)"]
RR_MEASURE_DEFAULT = "Volatility"


def _period_clamp(prefix, which):
    """Keep a month/year period picker's start on or before its end."""
    ss = st.session_state
    f = int(ss[f"{prefix}_from_y"]) * 12 + DD_MONTHS.index(ss[f"{prefix}_from_m"])
    t = int(ss[f"{prefix}_to_y"]) * 12 + DD_MONTHS.index(ss[f"{prefix}_to_m"])
    if f > t:
        v = f if which == "from" else t
        side = "to" if which == "from" else "from"
        ss[f"{prefix}_{side}_y"], ss[f"{prefix}_{side}_m"] = v // 12, DD_MONTHS[v % 12]


def _period_reset(prefix):
    ss = st.session_state
    lo, hi = ss.get(f"{prefix}_bounds", (None, None))
    if lo is None:
        return
    ss[f"{prefix}_from_y"], ss[f"{prefix}_from_m"] = lo // 12, DD_MONTHS[lo % 12]
    ss[f"{prefix}_to_y"], ss[f"{prefix}_to_m"] = hi // 12, DD_MONTHS[hi % 12]


def _period_picker(prefix, lo_mi, hi_mi):
    """From month/year, To month/year and a Since inception reset. Returns the
    picked (from, to) as month indices, clamped to the data's months."""
    ss = st.session_state
    ss[f"{prefix}_bounds"] = (lo_mi, hi_mi)
    ss.setdefault(f"{prefix}_from_y", lo_mi // 12)
    ss.setdefault(f"{prefix}_from_m", DD_MONTHS[lo_mi % 12])
    ss.setdefault(f"{prefix}_to_y", hi_mi // 12)
    ss.setdefault(f"{prefix}_to_m", DD_MONTHS[hi_mi % 12])
    years = list(range(lo_mi // 12, hi_mi // 12 + 1))
    c1, c2, c3, c4, c5 = st.columns([1.25, 0.9, 1.25, 0.9, 1.1], vertical_alignment="bottom")
    c1.selectbox("From", DD_MONTHS, key=f"{prefix}_from_m", on_change=_period_clamp, args=(prefix, "from"))
    c2.selectbox("From year", years, key=f"{prefix}_from_y", on_change=_period_clamp,
                 args=(prefix, "from"), label_visibility="hidden")
    c3.selectbox("To", DD_MONTHS, key=f"{prefix}_to_m", on_change=_period_clamp, args=(prefix, "to"))
    c4.selectbox("To year", years, key=f"{prefix}_to_y", on_change=_period_clamp,
                 args=(prefix, "to"), label_visibility="hidden")
    c5.button("Since inception", key=f"{prefix}_reset", on_click=_period_reset, args=(prefix,))
    f = int(ss[f"{prefix}_from_y"]) * 12 + DD_MONTHS.index(ss[f"{prefix}_from_m"])
    t = int(ss[f"{prefix}_to_y"]) * 12 + DD_MONTHS.index(ss[f"{prefix}_to_m"])
    return max(lo_mi, min(hi_mi, f)), max(lo_mi, min(hi_mi, t))


def build_risk_return_figure(points, ref_point, measure="vol"):
    """points: dicts {label, vol, dd, sortino, rf, cagr, kind ('family'|'asset'|'custom'),
    color, size, text_color}. The x axis is drawn in a 0-to-1 display coordinate so
    the linear section and the compressed strip can share one axis; hover shows
    the true value.

    measure "vol" plots annualized volatility, with the dashed line from the
    origin through the 80/20 portfolio. measure "downside" plots annualized
    downside deviation (the Sortino denominator) and starts the dashed line at
    the T-bill return, so its slope is the 80/20 Sortino ratio and every point
    above it has a higher Sortino ratio."""
    downside = measure == "downside"
    if downside:
        # Put downside deviation in the "vol" slot so the axis, break and label
        # placement below work unchanged.
        points = [dict(p, vol=p["dd"]) for p in points]
        if ref_point:
            ref_point = dict(ref_point, vol=ref_point["dd"])
    vmax = max(p["vol"] for p in points)
    in_max = max([p["vol"] for p in points if p["vol"] <= RR_OUTLIER_VOL] + [1.0])
    broken = vmax > RR_OUTLIER_VOL
    if broken:
        brk = max(5.0, float(np.ceil(in_max * 1.06)))
        x_hi = vmax * 1.06
        w1 = 1.0 - RR_STRIP_FRAC - RR_GAP_FRAC

        def fx(v):
            if v <= brk:
                return v / brk * w1
            return w1 + RR_GAP_FRAC + (v - RR_OUTLIER_VOL) / max(1.0, x_hi - RR_OUTLIER_VOL) * RR_STRIP_FRAC
        lin_end = brk
    else:
        lin_end = max(5.0, float(np.ceil(vmax * 1.08 / 5.0) * 5.0))
        w1 = 1.0

        def fx(v):
            return v / lin_end

    step = 10 if (not broken and lin_end > 40) else 5
    tickvals, ticktext = [], []
    t = 0.0
    while t <= lin_end + 1e-9:
        tickvals.append(fx(t)); ticktext.append(f"{t:g}%")
        t += step
    if broken:
        last = w1
        for v in (30, 40, 50, 60, 75, 100):
            if RR_OUTLIER_VOL < v < x_hi and fx(v) - last >= 0.055:
                tickvals.append(fx(v)); ticktext.append(f"{v}%"); last = fx(v)

    y_lo = min(0.0, np.floor(min(p["cagr"] for p in points) / 5.0) * 5.0)
    y_hi = np.ceil(max(p["cagr"] for p in points) * 1.08 / 5.0) * 5.0
    if downside and ref_point:
        # Only matters when every visible dot sits below the T-bill return.
        y_hi = max(y_hi, np.ceil(ref_point.get("rf", 0.0) * 1.08 / 5.0) * 5.0)
    y_range = [y_lo - 1.5, y_hi + 1.5]
    y_step = 10 if (y_hi - y_lo) > 40 else 5

    fig = go.Figure()
    annotations, shapes = [], []
    # ---- label placement: try the spots around each point and keep the first
    # one that collides with no other point or label (approximate pixels at the
    # dashboard's usual plot size) ----
    PW_PX, PH_PX = 665.0, 464.0   # 780 wide less the side margins; 560 tall less top and bottom
    yr = y_range[1] - y_range[0]

    def to_px(xd, yd):
        return (xd + 0.005) / 1.005 * PW_PX, (y_range[1] - yd) / yr * PH_PX

    def overlap(a, b):
        return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))

    obstacles = []
    for p in points:
        cx, cy = to_px(fx(p["vol"]), p["cagr"])
        r = p["size"] / 2 + 2
        obstacles.append((cx - r, cy - r, cx + r, cy + r))
    order = sorted(range(len(points)), key=lambda i: (points[i]["label"] != "Asymmetric Edge",
                                                       points[i]["kind"] != "family",
                                                       points[i]["kind"] != "custom"))
    positions, placed = {}, []
    for i in order:
        p = points[i]
        is_ae = p["label"] == "Asymmetric Edge"
        size = 15 if is_ae else (13 if p["kind"] == "family" else 12)
        w, h = _dd_text_width(p["label"], size, bold=True), size * 1.25
        cx, cy = to_px(fx(p["vol"]), p["cagr"])
        r = p["size"] / 2 + 3
        cands = {
            "middle right": (cx + r, cy - h / 2, cx + r + w, cy + h / 2),
            "middle left": (cx - r - w, cy - h / 2, cx - r, cy + h / 2),
            "top center": (cx - w / 2, cy - r - h, cx + w / 2, cy - r),
            "bottom center": (cx - w / 2, cy + r, cx + w / 2, cy + r + h),
            "top right": (cx + r * 0.6, cy - r - h, cx + r * 0.6 + w, cy - r),
            "bottom right": (cx + r * 0.6, cy + r, cx + r * 0.6 + w, cy + r + h),
            "top left": (cx - r * 0.6 - w, cy - r - h, cx - r * 0.6, cy - r),
            "bottom left": (cx - r * 0.6 - w, cy + r, cx - r * 0.6, cy + r + h),
        }
        if is_ae:   # the hero label prefers the open space to its left
            cands = {k: cands[k] for k in ("middle left", "top left", "bottom left", "top center",
                                           "bottom center", "middle right", "top right", "bottom right")}
        best, best_cost = None, None
        for pos, box in cands.items():
            cost = sum(overlap(box, o) for j, o in enumerate(obstacles) if j != i)
            cost += sum(overlap(box, b) for b in placed)
            if box[0] < -8 or box[2] > PW_PX + 24 or box[1] < -6 or box[3] > PH_PX + 6:
                cost += 10000
            if best_cost is None or cost < best_cost - 1e-6:
                best, best_cost = pos, cost
            if cost == 0:
                break
        positions[p["label"]] = best
        placed.append(cands[best])

    if ref_point and ref_point["vol"] > 0:
        # Volatility: from the origin. Downside: from the T-bill return, so the
        # slope is (CAGR - risk-free) / downside deviation, the Sortino ratio.
        y0 = ref_point.get("rf", 0.0) if downside else 0.0
        slope = (ref_point["cagr"] - y0) / ref_point["vol"]
        x_end = lin_end                       # the line stops at the break
        if slope > 0 and y0 + slope * x_end > y_range[1]:
            x_end = (y_range[1] - y0) / slope
        if slope < 0 and y0 + slope * x_end < y_range[0]:
            x_end = (y_range[0] - y0) / slope
        shapes.append(dict(type="line", xref="x", yref="y", x0=0, y0=y0, x1=fx(x_end),
                           y1=y0 + slope * x_end,
                           line=dict(color="#9CA3AF", width=1.5, dash="dash"), layer="below"))
        # The line is named in a one-item key above the plot, not along the line
        # itself, so it never competes with the point labels.
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="lines",
            name=(f"{PRIMARY_BENCHMARK} Sortino ratio: return above T-bills per unit of downside risk"
                  if downside else f"{PRIMARY_BENCHMARK} return per unit of risk"),
            line=dict(color="#9CA3AF", width=1.5, dash="dash"), hoverinfo="skip", showlegend=True,
        ))
    if broken:
        g0, g1 = w1 + 0.002, w1 + RR_GAP_FRAC - 0.002
        shapes.append(dict(type="rect", xref="x", yref="paper", x0=g0, x1=g1, y0=0, y1=1,
                           fillcolor="#ffffff", line=dict(width=0), layer="between"))
        mid = (g0 + g1) / 2
        for dx in (-4, 4):
            shapes.append(dict(type="line", xref="x", yref="paper", xsizemode="pixel", ysizemode="pixel",
                               xanchor=mid, yanchor=0, x0=dx - 3, x1=dx + 3, y0=-7, y1=7,
                               line=dict(color="#9A9AAE", width=1.4)))
        annotations.append(dict(x=w1 + RR_GAP_FRAC + RR_STRIP_FRAC / 2, y=1, xref="x", yref="paper",
                                yanchor="bottom", showarrow=False, text="compressed",
                                font=dict(size=11, color=TEXT_MUTED, family=ANALYTICS_FONT)))

    for kind in ["asset", "custom", "family"]:
        for p in [q for q in points if q["kind"] == kind]:
            is_ae = p["label"] == "Asymmetric Edge"
            solid = kind == "family"
            fig.add_trace(go.Scatter(
                x=[fx(p["vol"])], y=[p["cagr"]], mode="markers+text",
                text=[f"<b>{p['label']}</b>"],
                textposition=positions[p["label"]],
                textfont=dict(size=15 if is_ae else (13 if kind == "family" else 12),
                              color=p["text_color"], family=ANALYTICS_FONT),
                marker=dict(size=p["size"], symbol="circle",
                            color=p["color"] if solid else "#ffffff",
                            line=dict(color="#ffffff" if solid else p["color"],
                                      width=2 if solid else 2.5)),
                hovertemplate=(f"<b>{p['label']}</b><br>Annualized return %{{y:.1f}}%"
                               + ((f"<br>Downside deviation {p['vol']:.1f}%<br>Sortino ratio "
                                   + (f"{p['sortino']:.2f}" if p["vol"] >= 0.05
                                      else "n/a (never trailed T-bills)"))
                                  if downside else f"<br>Volatility {p['vol']:.1f}%")
                               + "<extra></extra>"),
                showlegend=False, cliponaxis=False,
            ))
    title = (("Annualized downside deviation" if downside else "Annualized volatility")
             + (" (compressed scale above 25%)" if broken else ""))
    fig.update_layout(
        **DARK_LAYOUT,
        xaxis=dict(range=[-0.005, 1.0], tickmode="array", tickvals=tickvals, ticktext=ticktext,
                   gridcolor=GRID_COLOR, zeroline=False, fixedrange=True,
                   title=dict(text=title, font=dict(size=15, color=TEXT_PRIMARY)),
                   tickfont=dict(size=15, color=TEXT_MUTED)),
        yaxis=dict(range=y_range, ticksuffix="%", gridcolor=GRID_COLOR, zeroline=True,
                   zerolinecolor="#c9c9d3", tick0=0, dtick=y_step, fixedrange=True,
                   title=dict(text="Annualized return", font=dict(size=15, color=TEXT_PRIMARY),
                              standoff=9),   # a little room between the title and the tick labels
                   tickfont=dict(size=15, color=TEXT_MUTED)),
        margin=dict(t=36, b=60, l=85, r=30),
        height=560,
        shapes=shapes, annotations=annotations,
        hovermode="closest",
        showlegend=True,
        legend=dict(orientation="h", x=0, xanchor="left", y=1.0, yanchor="bottom",
                    bgcolor="rgba(0,0,0,0)", borderwidth=0, itemwidth=30,
                    itemclick=False, itemdoubleclick=False,
                    font=dict(size=12, color=TEXT_SECONDARY, family=ANALYTICS_FONT)),
    )
    return fig


def compute_risk_return_points(combined, start, end, hide=(), custom=None, custom_color=None,
                               rf_monthly=None, hide_family=()):
    """Points for the Risk vs. Return chart over [start, end]: the four series,
    every visible universe asset not in ``hide``, and an optional custom ticker.
    Returns (points, ref_point, late_start_notes, custom_ok)."""
    inception = combined.index[0]
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    family_style = {
        "AsymEdge": ("Asymmetric Edge", SERIES_COLORS["AsymEdge"], 20, BRAND_PURPLE),
        "80/20": ("80/20", SERIES_COLORS["80/20"], 14, "#3550C9"),
        "60/40": ("60/40", SERIES_COLORS["60/40"], 14, "#1C8FB3"),
        "S&P 500": ("S&P 500", SERIES_COLORS["S&P 500"], 14, "#6B7280"),
    }
    points, ref_point, late_start = [], None, []
    for name in SERIES_ORDER:
        if name not in combined.columns:
            continue
        m = compute_summary_metrics(combined[name], rf_monthly=rf_monthly, start_date=start, end_date=end)
        if not m:
            continue
        label, color, size, text_color = family_style[name]
        p = {"label": label, "vol": m["Annualized Vol"] * 100.0, "cagr": m["CAGR"] * 100.0,
             "dd": m["Downside Dev"] * 100.0, "sortino": m["Sortino Ratio"],
             "rf": m["Risk-Free Annual"] * 100.0,
             "kind": "family", "color": color, "size": size, "text_color": text_color}
        if name not in hide_family:
            points.append(p)
        if name == PRIMARY_BENCHMARK:
            ref_point = p     # the dashed line needs it even when its dot is hidden

    def asset_point(s, label, kind, color):
        # Pass the full history so the first month is anchored on the prior
        # month-end, exactly as for the four portfolios; an asset that began
        # trading after the period start is measured from its first day.
        s = s.dropna()
        s = s[(s.index >= inception) & (s.index <= end)]   # nothing before the strategy's inception
        in_range = s[s.index >= start]
        if len(in_range) < 40:
            return None
        first = in_range.index[0]
        late = s.index[0] > start + pd.Timedelta(days=5)
        if late:
            late_start.append(f"{label} from {_long_date(s.index[0])}")
        m = compute_summary_metrics(s, rf_monthly=rf_monthly,
                                    start_date=s.index[0] if late else start, end_date=end)
        if not m:
            return None
        return {"label": label, "vol": m["Annualized Vol"] * 100.0, "cagr": m["CAGR"] * 100.0,
                "dd": m["Downside Dev"] * 100.0, "sortino": m["Sortino Ratio"],
                "rf": m["Risk-Free Annual"] * 100.0,
                "kind": kind, "color": color, "size": 12 if kind == "custom" else 12,
                "text_color": color}

    universe = load_asset_universe()
    tickers, cat_color = [], {}
    for cat in universe.get("categories", []):
        if not cat.get("visible", True):
            continue
        for a in cat.get("assets", []):
            t = str(a.get("ticker", "")).strip().upper()
            if t and t not in tickers and t != "SPY":
                tickers.append(t)
                cat_color[t] = cat.get("color_text") or "#8a8f9c"
    if tickers:
        closes = load_asset_class_data(tuple(tickers), inception.strftime("%Y-%m-%d"),
                                       pd.Timestamp(combined.index[-1]).strftime("%Y-%m-%d"))
        for t in tickers:
            if t in hide or closes is None or t not in closes.columns:
                continue
            p = asset_point(closes[t], t, "asset", ASSET_POINT_COLORS.get(t, cat_color.get(t, "#8a8f9c")))
            if p:
                points.append(p)

    custom_ok = None
    if custom:
        shown = {p["label"] for p in points}
        if custom in tickers and custom in hide:
            custom_ok = "hidden"
        elif custom in shown or custom in tickers:
            custom_ok = "already"
        else:
            data = load_custom_ticker_data((custom,), inception.strftime("%Y-%m-%d"),
                                           pd.Timestamp(combined.index[-1]).strftime("%Y-%m-%d"))
            p = None
            if data is not None and not data.empty and custom in data.columns:
                p = asset_point(data[custom], custom, "custom", custom_color or CAPTURE_CUSTOM_BAR)
            if p:
                points.append(p)
                custom_ok = "ok"
            else:
                custom_ok = "missing"
    return points, ref_point, late_start, custom_ok


def render_risk_return_section(combined, latest_date):
    data_end = pd.Timestamp(latest_date)
    idx = combined.index[combined.index <= data_end]
    lo_mi, hi_mi = _dd_month_index(idx[0]), _dd_month_index(idx[-1])
    measure_pick = st.pills("Measure risk by", RR_MEASURES, default=RR_MEASURE_DEFAULT,
                            selection_mode="single", key="rr_measure")
    downside = (measure_pick or RR_MEASURE_DEFAULT) == RR_MEASURES[1]
    f_mi, t_mi = _period_picker("rr", lo_mi, hi_mi)
    opts = _rr_show_options()
    labels = list(opts)
    ss = st.session_state
    # Seed through session state rather than default= so the presets can set
    # it; the key persists across reruns and other controls.
    if RR_SHOW_KEY not in ss:
        ss[RR_SHOW_KEY] = [l for l in labels if l not in RR_DEFAULT_HIDDEN]
    elif any(l not in opts for l in ss[RR_SHOW_KEY]):
        ss[RR_SHOW_KEY] = [l for l in ss[RR_SHOW_KEY] if l in opts]   # the universe was edited
    st.pills("Presets", RR_PRESETS, selection_mode="single", key="rr_preset",
             on_change=_rr_apply_preset, args=(labels,))
    show = st.pills("Show", labels, selection_mode="multi", key=RR_SHOW_KEY)
    shown = set(show or [])
    hide = {i for l, (k, i) in opts.items() if k == "asset" and l not in shown}
    hide_family = {i for l, (k, i) in opts.items() if k == "family" and l not in shown}
    col_t, col_c, _ = st.columns([1, 0.55, 2.45], vertical_alignment="bottom")
    raw = col_t.text_input("Custom ticker", value="", max_chars=12, key="rr_custom",
                           placeholder="e.g. SMH",
                           help="Add any ticker Yahoo Finance carries to the chart.")
    custom_color = col_c.color_picker("Color", value=CAPTURE_CUSTOM_BAR, key="rr_custom_color")
    custom = re.sub(r"[^A-Za-z0-9.\-^=]", "", raw or "").upper() or None

    if not shown and not custom:
        st.info("Every dot is hidden. Turn some on under Show, or pick a preset.")
        return
    if t_mi - f_mi + 1 < RR_MIN_MONTHS:
        st.info("Pick a period of at least three months; volatility needs several monthly returns.")
        return
    months = idx.year * 12 + idx.month - 1
    window = idx[(months >= f_mi) & (months <= t_mi)]
    start, end = window[0], window[-1]
    full = f_mi == lo_mi and t_mi == hi_mi

    # BIL as the risk-free rate, loaded the same way as the Performance Summary,
    # so each point's Sortino ratio matches that table.
    rf_monthly = load_bil_data(combined.index[0].strftime("%Y-%m-%d"), data_end.strftime("%Y-%m-%d"))
    points, ref_point, late_start, custom_ok = compute_risk_return_points(
        combined, start, end, hide=hide, custom=custom, custom_color=custom_color,
        rf_monthly=rf_monthly, hide_family=hide_family)
    if not points:
        st.info("Risk and return figures could not be computed.")
        return
    if custom_ok == "missing":
        st.warning(f"Couldn't load enough price history for {custom} in this period.")
    elif custom_ok == "already":
        st.caption(f"{custom} is already on the chart.")
    elif custom_ok == "hidden":
        st.caption(f"{custom} is in the strategy's universe; turn it on under Show.")
    measure = "downside" if downside else "vol"
    tag = (f"{measure}_{f_mi}_{t_mi}_{'-'.join(sorted(hide | hide_family))}_{custom or ''}_{custom_color}"
           .replace("#", ""))
    st.plotly_chart(build_risk_return_figure(points, ref_point, measure), use_container_width=True,
                    config=chart_config("Risk vs. Downside Risk" if downside else "Risk vs. Return"),
                    key=f"rr_fig_{tag}")

    # A later period is measured from the prior month-end close, so name it by month.
    period = (f"from the {_long_date(start)} inception through {_long_date(end)}" if full
              else f"from {start:%B %Y} through "
                   + (_long_date(end) if t_mi == hi_mi else f"{end:%B %Y}"))
    friendly = {"Cash (BIL)": "cash (BIL)", "Bitcoin (IBIT)": "bitcoin (IBIT)"}
    hidden = [friendly.get(l, l) for l in labels if l not in shown]
    visible = [friendly.get(l, l) for l in labels if l in shown]
    late = (" Assets that began trading after the period start are measured from their first day: "
            + "; ".join(late_start) + ".") if late_start else ""
    broken = max(p["dd" if downside else "vol"] for p in points) > RR_OUTLIER_VOL
    if downside:
        lead = (f"Annualized return (CAGR) against annualized downside deviation, {period}. Downside "
                "deviation counts only the months that trailed T-bills (BIL), so gains add no risk; it "
                "is the denominator of the Sortino ratio, computed the same way as the Performance "
                "Summary table. Up and to the left is better. The dashed line starts at the T-bill "
                "return and runs through the 80/20 portfolio (AOA), so its slope is the 80/20 Sortino "
                "ratio and points above it have a higher Sortino ratio. Hover a point for its ratio."
                + (" Over less than a year, downside deviation rests on only a few down months and can "
                   "swing widely." if t_mi - f_mi + 1 < 12 else ""))
    else:
        lead = (f"Annualized return (CAGR) against annualized volatility of monthly returns, {period}, "
                "computed the same way as the Performance Summary table. Up and to the left is better. "
                "Points above the dashed line earned more return per unit of volatility than the 80/20 "
                "portfolio (AOA).")
    if ref_point and PRIMARY_BENCHMARK in hide_family:
        lead += " The 80/20 dot is hidden; the dashed line still marks its ratio."
    _footnote(
        lead
        + (" Hollow points are the assets in the strategy's universe, colored by their Asset Universe "
           "category; the strategy rotates among them rather than holding all of them."
           if any(p["kind"] == "asset" for p in points) else "")
        + (f" {custom} is the custom ticker you added." if custom_ok == "ok" else "")
        + (f" The {'downside deviation' if downside else 'volatility'} axis is linear up to the break; "
           "anything above 25% sits in a compressed strip at the right, so distances there are not to "
           "scale and the dashed line stops at the break."
           if broken else "")
        + ((f" Showing only {_rr_join(visible)}." if len(visible) < len(hidden)
            else f" Hidden: {_rr_join(hidden)}.") if hidden and visible else "")
        + late +
        " Asymmetric Edge is anchored to Fidelity's reported returns; everything else uses Yahoo Finance "
        "adjusted closes with distributions reinvested."
    )
    fam_shown = [opts[l][1] for l in labels if l in shown and opts[l][0] == "family"]
    assets_shown = any(opts[l][0] == "asset" for l in labels if l in shown)
    newsletter_caption(
        f"Annualized return vs. "
        f"{'downside risk (annualized downside deviation)' if downside else 'annualized volatility'}, "
        f"{_cap_vs(fam_shown)}"
        + (", plus the funds in the strategy's universe" if assets_shown else "")
        + f", {_cap_date(start)} through {_cap_date(end)}. " + NEWSLETTER_RETURNS_SENTENCES
    )


# ===========================================================================
# 8. CORRELATION AND DIVERSIFICATION (added October 31, 2026)
#
# Three views of how the basket's funds move together, built from the
# mockups Tyler approved on October 31, 2026 (Correlation Over Time Mockups
# canvas, boards Main, Matrix and Bets):
#
#   Correlation Over Time          fund pairs by month (Idea 1)
#   Correlation Matrix             current readings below the diagonal and
#                                  twelve monthly trend bars above it (Idea 2)
#   Did the Diversification Hold?  independent bets going in versus delivered,
#                                  against a floor set with a slider (Idea 4)
#
# Everything is computed here from data the dashboard already reads: each
# month's going-in basket comes from holdings_daily_values.csv by the same
# rules as Asset Allocation Over Time (corr_going_in_baskets), and daily
# prices come through load_holding_prices / _fetch_closes, so the committed
# price_snapshot.csv covers Yahoo outages on the cloud. No pipeline step and
# no new data file. Nothing here touches the return series.
# ===========================================================================

CORR_SECTION_TITLE = "Correlation and Diversification"

# Correlation windows in trading days: 63 counts as three months, 252 as twelve.
CORR_WINDOWS = {"3 months": 63, "6 months": 126, "12 months": 252}
CORR_CAL_WINDOWS = ["3 months", "6 months", "12 months"]
CORR_MATRIX_WINDOWS = ["3 months", "6 months"]
CORR_COMPARE = {"1 month ago": 1, "3 months ago": 3, "1 year ago": 12}
CORR_WINDOW_WORDS = {63: "63 trading days (about three months)",
                     126: "126 trading days (about six months)",
                     252: "252 trading days (about a year)"}
CORR_PRICE_LEAD_DAYS = 420   # calendar days of prices before inception, enough for a 12-month window in January 2024
CORR_HELD_MIN_PCT = 0.5      # a fund counts as held at 0.5% of the account, as in the Rebalance Log
CORR_FADED = 0.22            # opacity of a calendar cell when the basket did not hold both funds
CORR_STEADY = 0.05           # changes smaller than this read "steady"
CORR_RISE = "#B4482A"        # correlation rose (toward lockstep): the warm end of the heat scale
CORR_FALL = "#3A6A9E"        # correlation fell: the cool end
CORR_HIGH = 0.8              # "Held together above 0.8" tile
CORR_MATRIX_MAX = 8          # most funds the matrix shows (the most recently held win)
CORR_MATRIX_MONTHS = 12      # trend bars per pair above the diagonal
CORR_RULE_GRAY = "#9CA3AF"
CORR_PILL_BORDER = "#D5D6DD"

# Diverging correlation scale, interpolated linearly between these stops,
# with hard steps at -0.7 and +0.7 so strong readings jump out.
CORR_SCALE = [
    (-1.0, "#1E4A75"), (-0.701, "#3A6A9E"), (-0.7, "#7EA6CF"), (-0.3, "#B4CDE6"),
    (0.0, "#F4F4F6"), (0.3, "#F6D6C1"), (0.55, "#EDAE8B"), (0.699, "#E89A73"),
    (0.7, "#B4482A"), (0.85, "#99381F"), (1.0, "#7A2514"),
]

# Display order for funds: U.S. equities, international, commodities, gold,
# crypto, defensive (the mockup's matrix order). Unknown tickers go last.
CORR_FUND_ORDER = ["SPY", "QQQ", "IWM", "EZU", "EMXC", "DXJ", "HGER", "COPX", "GLD",
                   "IBIT", "GBTC", "BITO", "BTAL", "TLT"]
# Names for earlier holdings that are not in ASSET_CATALOG.
CORR_EXTRA_NAMES = {"SPY": "S&P 500", "EZU": "Eurozone", "COPX": "Copper Miners",
                    "GBTC": "Bitcoin (GBTC)", "BITO": "Bitcoin Futures"}
# Dot colors for tickers missing from ASSET_POINT_COLORS, by allocation category.
CORR_CATEGORY_DOT = {"us": "#1F4D87", "intl": "#14543E", "comm": "#7E4A0A", "gold": "#A57A08",
                     "crypto": "#C8650A", "def": "#4A463D", "cash": "#8C867C"}

# Independent bets (Idea 4).
BETS_FLOOR_DEFAULT = 2.0
BETS_FLOOR_MIN = 1.0
BETS_FLOOR_MAX = 3.0
BETS_FLOOR_STEP = 0.1
BETS_CAP = 4.0               # readings above 4 show as "4+"
BETS_WINDOW = 63             # going in: the 63 trading days before the month
BETS_MIN_PRE = 20            # fewest sessions a going-in reading may rest on
BETS_MIN_SESSIONS = 10       # an open month shows what it delivered once it has this many sessions
BETS_TBILL_SHARE = 0.5       # a basket more than half T-bills and cash reads "T-bills" and is left out
BETS_PURPLE = BAR_SERIES_COLORS["AsymEdge"]   # bets going in, at or above the floor
BETS_LOW = "#B4482A"         # below the floor, just under it
BETS_LOW_DEEP = "#7A2514"    # below the floor, at 1 bet
BETS_FAINT = "#F7E2D8"       # just above the floor
BETS_NEUTRAL = "#F3F3F5"     # half a bet or more above the floor
BETS_GOOD = "#1E7A50"        # the month delivered more bets than it went in with
BETS_TRACK = "#F4F4F6"
BETS_TBILL_FILL = "#F3F4F6"
BETS_STRIPE_EDGE = "#D9DAE0"
BETS_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ---------- small helpers ----------

def _cx_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _cx_hex(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def _cx_mix(a, b, t):
    t = max(0.0, min(1.0, float(t)))
    ra, rb = _cx_rgb(a), _cx_rgb(b)
    return _cx_hex([ra[i] + (rb[i] - ra[i]) * t for i in range(3)])


def _cx_text_on(bg):
    """White text where it passes 4.5:1 contrast on bg, otherwise the cell ink."""
    def channel(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _cx_rgb(bg)
    lum = 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
    return "#FFFFFF" if 1.05 / (lum + 0.05) >= 4.5 else ANALYTICS_CELL_TEXT


def _cx_text(ann, x, y, text, anchor="left", size=13, color=TEXT_PRIMARY, weight=400,
             valign="middle"):
    """Pixel-coordinate text with an explicit DM Sans weight (400 to 700)."""
    ann.append(dict(
        x=x, y=y, xref="x", yref="y", xanchor=anchor, yanchor=valign, text=text,
        showarrow=False, align=anchor if anchor in ("left", "right") else "center",
        font=dict(family=ANALYTICS_FONT, size=size, color=color, weight=weight),
    ))


def _cx_rect(shapes, x0, y0, x1, y1, fill, r=0.0, line_color=None, line_width=0.0,
             opacity=None, layer="below"):
    shape = dict(type="path", path=_round_rect_path(x0, y0, x1, y1, r), fillcolor=fill,
                 line=dict(color=line_color, width=line_width) if line_color else dict(width=0),
                 layer=layer)
    if opacity is not None:
        shape["opacity"] = opacity
    shapes.append(shape)


def _cx_line(shapes, x0, y0, x1, y1, color, width=1.0, dash=None):
    line = dict(color=color, width=width)
    if dash:
        line["dash"] = dash
    shapes.append(dict(type="line", x0=x0, y0=y0, x1=x1, y1=y1, line=line, layer="above"))


def _cx_dot(shapes, cx, cy, r, color):
    shapes.append(dict(type="circle", x0=cx - r, y0=cy - r, x1=cx + r, y1=cy + r,
                       fillcolor=color, line=dict(width=0), layer="above"))


def _cx_triangle(shapes, x, y, up, s, color):
    """Small up or down triangle centered near (x, y), as in the mockups."""
    if up:
        path = f"M {x - s},{y + s * 0.45} L {x + s},{y + s * 0.45} L {x},{y - s * 0.75} Z"
    else:
        path = f"M {x - s},{y - s * 0.45} L {x + s},{y - s * 0.45} L {x},{y + s * 0.75} Z"
    shapes.append(dict(type="path", path=path, fillcolor=color, line=dict(width=0), layer="above"))


def _cx_wrap(text, size, max_w):
    """Greedy word wrap by estimated DM Sans width (px)."""
    lines, cur = [], ""
    for word in str(text).split():
        trial = f"{cur} {word}".strip()
        if cur and _dd_text_width(trial, size) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _cx_tiles(shapes, ann, tiles, y0=0.0):
    """Lavender summary tiles across the full width: label, big value, and a
    one- or two-line note. Returns the tile height."""
    W = ANALYTICS_WIDTH
    gap = 12
    tile_w = (W - gap * (len(tiles) - 1)) / max(len(tiles), 1)
    wrapped = [_cx_wrap(sub, 12, tile_w - 30)[:2] for _label, _value, sub in tiles]
    tile_h = 98 if any(len(w) > 1 for w in wrapped) else 84
    for i, ((label, value, _sub), lines) in enumerate(zip(tiles, wrapped)):
        x0 = i * (tile_w + gap)
        _cx_rect(shapes, x0, y0, x0 + tile_w, y0 + tile_h, ANALYTICS_TINT, r=10)
        _cx_text(ann, x0 + 16, y0 + 20, label.replace("&", "&amp;"), size=13, color=TEXT_SECONDARY)
        _cx_text(ann, x0 + 16, y0 + 46, value.replace("&", "&amp;"), size=24,
                 color=BRAND_PURPLE, weight=700)
        for j, line in enumerate(lines):
            _cx_text(ann, x0 + 16, y0 + 70 + 15 * j, line.replace("&", "&amp;"), size=12,
                     color=TEXT_SECONDARY)
    return tile_h


def _cx_hover(fig, xs, ys, texts, size):
    """Invisible square markers that carry hover text for pixel figures."""
    if xs:
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers",
            marker=dict(size=max(int(size), 4), color="rgba(0,0,0,0)", symbol="square"),
            hovertext=texts, hovertemplate="%{hovertext}<extra></extra>", showlegend=False,
        ))


def corr_color(v):
    """Heat color for a correlation on the diverging scale."""
    if v is None or not np.isfinite(v):
        return HEAT_EMPTY
    v = max(-1.0, min(1.0, float(v)))
    for (a, ca), (b, cb) in zip(CORR_SCALE, CORR_SCALE[1:]):
        if v <= b:
            return _cx_mix(ca, cb, (v - a) / (b - a))
    return CORR_SCALE[-1][1]


def _corr_str(v, digits=2):
    """Correlation with a true minus sign, e.g. 0.82 or −0.22; n/a when missing."""
    if v is None or not np.isfinite(v):
        return "n/a"
    text = f"{abs(v):.{digits}f}"
    return (MINUS + text) if v < -0.5 * 10 ** -digits else text


def _corr_fund_name(ticker):
    info = ASSET_CATALOG.get(ticker)
    return info["asset"] if info else CORR_EXTRA_NAMES.get(ticker, ticker)


def _corr_fund_color(ticker):
    if ticker in ASSET_POINT_COLORS:
        return ASSET_POINT_COLORS[ticker]
    return CORR_CATEGORY_DOT.get(ALLOC_HISTORY_TICKER_CATEGORY.get(ticker, ""), "#8a8f9c")


def _corr_order(tickers):
    pos = {t: i for i, t in enumerate(CORR_FUND_ORDER)}
    return sorted(set(tickers), key=lambda t: (pos.get(t, len(pos)), t))


def _corr_month(period):
    return pd.Period(period, freq="M").strftime("%B %Y")


def _bets_shown(v):
    """The one-decimal value a cell displays (capped to 1..4). Floor tests use
    this, so a cell that reads 2.2 is never below a 2.2 floor."""
    return float(f"{max(1.0, min(BETS_CAP, float(v))):.1f}")


def _bets_fmt(v):
    if v is None or not np.isfinite(v):
        return "n/a"
    return "4+" if v > BETS_CAP else f"{max(1.0, float(v)):.1f}"


def bets_is_low(v, floor):
    return v is not None and np.isfinite(v) and _bets_shown(v) < floor - 1e-9


def bets_color(v, floor):
    """Reds only: deep red below the floor (darker the further below), a faint
    tint just above it fading to neutral over the next half bet."""
    v = max(1.0, min(BETS_CAP, float(v)))
    if bets_is_low(v, floor):
        return _cx_mix(BETS_LOW, BETS_LOW_DEEP, (floor - v) / max(floor - 1.0, 1e-9))
    return _cx_mix(BETS_FAINT, BETS_NEUTRAL, (v - floor) / 0.5)


# ---------- data ----------

def corr_going_in_baskets(holdings_values, totals):
    """Each month's going-in basket since inception, oldest first, by the same
    rules as Asset Allocation Over Time: the holdings at the close of the prior
    month's final trading day (the inception month uses the January 2, 2024
    close), with ALLOC_HISTORY_EXECUTION_CORRECTIONS and an active month-start
    override applied, and the month after a registered month-end rebalance
    included. Returns dicts with period, date (the going-in close), weights
    (ticker -> share of the account, securities only) and tbill (the share in
    BIL, money market and uninvested cash)."""
    if holdings_values is None or holdings_values.empty:
        return []
    hv = holdings_values.fillna(0.0).sort_index()
    inception = pd.Timestamp(ALLOC_HISTORY_START)
    in_range = hv.index[hv.index >= inception]
    if len(in_range) == 0:
        return []
    idx = hv.index
    month_ends = idx.to_series().groupby([idx.year, idx.month]).max()
    last_period = idx[-1].to_period("M")
    rebalances = find_rebalance_dates(hv)
    if rebalances and rebalances[0] == idx[-1]:
        last_period = last_period + 1
    override = load_month_start_override()
    override_date = override["period_start_date"] if override else ""

    baskets = []
    for period in pd.period_range(in_range[0].to_period("M"), last_period, freq="M"):
        prev = period - 1
        going_in = month_ends.get((prev.year, prev.month))
        if going_in is None or going_in < inception:
            in_month = in_range[(in_range.year == period.year) & (in_range.month == period.month)]
            if len(in_month) == 0:
                continue
            going_in = in_month[0]
        key = going_in.strftime("%Y-%m-%d")
        correction = ALLOC_HISTORY_EXECUTION_CORRECTIONS.get(key)
        if correction is None and override and key == override_date:
            correction = override["weights"]
        if correction:
            csum = sum(float(v) for v in correction.values())
            if csum <= 0:
                continue
            weights = {str(t): float(v) / csum for t, v in correction.items() if float(v) > 0}
            tbill = sum(w for t, w in weights.items() if t == "BIL" or t in CASH_LIKE_TICKERS)
            weights = {t: w for t, w in weights.items() if t not in CASH_LIKE_TICKERS}
        else:
            row = hv.loc[going_in]
            total = float(row[row > 0].sum())
            cash = 0.0
            if totals is not None and going_in in totals.index:
                account_value = float(totals.at[going_in, "account_value"])
                if account_value > 0:
                    total = account_value
                    cash = max(float(totals.at[going_in, "cash"]), 0.0)
            if total <= 0:
                continue
            weights = {str(t): float(v) / total for t, v in row.items()
                       if float(v) > 1.0 and t not in CASH_LIKE_TICKERS}
            money_market = sum(float(row[t]) for t in CASH_LIKE_TICKERS if t in row.index)
            tbill = weights.get("BIL", 0.0) + (max(money_market, 0.0) + cash) / total
        baskets.append({"period": period, "date": going_in, "weights": weights, "tbill": tbill})
    return baskets


def corr_price_tickers(baskets, next_rows):
    """Every fund any monthly basket held since inception, plus next month's
    basket and SPY, which marks the equity sessions."""
    tickers = {"SPY"}
    for b in baskets:
        tickers.update(t for t, w in b["weights"].items() if w > 0)
    for r in next_rows or []:
        t = str(r.get("ticker", "")).strip().upper()
        if t and _sort_weight(r.get("weight")) > 0:
            tickers.add(t)
    return sorted(t for t in tickers if t and t not in CASH_LIKE_TICKERS)


def corr_equity_returns(prices):
    """Daily returns on completed equity sessions. Rows where SPY has no close
    are dropped first, because a weekend row (BTC-USD style) would otherwise
    turn every Monday return into NaN, and a final session that has not closed
    yet is dropped so a partial trading day is never used."""
    if prices is None or prices.empty:
        return pd.DataFrame()
    px = prices.sort_index()
    px = px[~px.index.duplicated(keep="last")]
    if "SPY" in px.columns and px["SPY"].notna().any():
        px = px[px["SPY"].notna()]
    else:
        px = px[px.index.dayofweek < 5]
    if len(px) and not _session_has_closed(px.index[-1]):
        px = px.iloc[:-1]
    if len(px) < 2:
        return pd.DataFrame()
    return px.pct_change(fill_method=None).iloc[1:]


@st.cache_data(ttl=3600, show_spinner=False)
def compute_pair_correlations(returns, funds, dates, window):
    """{(a, b): [reading at each date]} for every pair of funds: the correlation
    of daily returns over the last `window` sessions both funds traded, ending
    on each date. NaN where fewer than a third of the window exists (a fund
    that had only just launched)."""
    min_obs = max(20, int(window) // 3)
    dates = [pd.Timestamp(d) for d in dates]
    out = {}
    funds = list(funds)
    for i, a in enumerate(funds):
        for b in funds[i + 1:]:
            vals = [np.nan] * len(dates)
            if a in returns.columns and b in returns.columns:
                pair = returns[[a, b]].dropna()
                if len(pair) >= min_obs:
                    roll = pair[a].rolling(int(window), min_periods=min_obs).corr(pair[b])
                    for k, d in enumerate(dates):
                        upto = roll.loc[:d]
                        if len(upto):
                            v = float(upto.iloc[-1])
                            vals[k] = v if np.isfinite(v) else np.nan
            out[(a, b)] = vals
    return out


def _dr_squared(block, weights):
    """Independent bets: the diversification ratio squared, ((w·σ) / σp)²
    (Choueifaty and Coignard, 2008). 1 means the funds behaved as one bet."""
    cov = block.cov().values
    if not np.all(np.isfinite(cov)):
        return np.nan
    vol = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    port_var = float(weights @ cov @ weights)
    if port_var <= 0:
        return np.nan
    return float((weights @ vol) ** 2 / port_var)


@st.cache_data(ttl=3600, show_spinner=False)
def compute_bets_rows(returns, months_spec):
    """Bets going in and delivered for each month. months_spec holds one tuple
    per month: (period string, going-in date, reading date, ((ticker, weight),
    ...), T-bill share, closed flag). Going in uses the BETS_WINDOW sessions up
    to the going-in close; delivered uses the month's own sessions after it."""
    rows = []
    for period_s, going_in, reading, items, tbill, closed in months_spec:
        going_in, reading = pd.Timestamp(going_in), pd.Timestamp(reading)
        row = {"period": pd.Period(period_s, freq="M"), "going_in_date": going_in,
               "reading_date": reading, "tbill": tbill >= BETS_TBILL_SHARE, "closed": bool(closed),
               "pre": np.nan, "dlv": np.nan, "n_dlv": 0, "missing": []}
        if not row["tbill"]:
            weights = {t: w for t, w in items if w > 0}
            priced = [t for t in weights if t in returns.columns]
            row["missing"] = [t for t in weights
                              if t not in priced and weights[t] * 100.0 >= CORR_HELD_MIN_PCT]
            if priced and not row["missing"]:
                w = np.array([weights[t] for t in priced])
                pre = returns.loc[:going_in, priced].dropna().tail(BETS_WINDOW)
                if len(pre) >= BETS_MIN_PRE:
                    row["pre"] = _dr_squared(pre, w)
                inside = returns.loc[(returns.index > going_in) & (returns.index <= reading), priced].dropna()
                row["n_dlv"] = int(len(inside))
                if len(inside) >= BETS_MIN_SESSIONS:
                    row["dlv"] = _dr_squared(inside, w)
        rows.append(row)
    return rows


def corr_section_context(baskets, prices, next_rows):
    """Everything the three views share: the months shown (inception through
    the latest month that has both a basket and a completed session), each
    month's reading date and basket, the daily returns, and the fund sets."""
    returns = corr_equity_returns(prices)
    if returns.empty or not baskets:
        return None
    last_session = returns.index[-1]
    last_period = min(baskets[-1]["period"], last_session.to_period("M"))
    sess_periods = returns.index.to_period("M")
    months = []
    for b in baskets:
        if b["period"] > last_period:
            break
        in_month = returns.index[(sess_periods == b["period"]) & (returns.index >= b["date"])]
        if len(in_month) == 0:
            continue
        months.append({**b, "reading": in_month[-1]})
    if not months:
        return None
    months[-1]["closed"] = months[-1]["period"] < last_session.to_period("M") or \
        _last_month_closed(months[-1]["reading"])
    for m in months[:-1]:
        m["closed"] = True

    def held(basket):
        return {t for t, w in basket["weights"].items()
                if w * 100.0 >= CORR_HELD_MIN_PCT and t != "BIL" and t not in CASH_LIKE_TICKERS}

    for m in months:
        m["held"] = held(m)
    nxt = set()
    for r in next_rows or []:
        t = str(r.get("ticker", "")).strip().upper()
        if t and t != "BIL" and t not in CASH_LIKE_TICKERS and _sort_weight(r.get("weight")) >= CORR_HELD_MIN_PCT:
            nxt.add(t)
    latest = months[-1]["held"]
    if nxt and nxt != latest:
        # next_allocation.json already holds the basket for the coming month.
        current, prior = nxt, latest
        current_period = months[-1]["period"] + 1
    else:
        current = latest
        prior = months[-2]["held"] if len(months) > 1 else set()
        current_period = months[-1]["period"]
    replaced = _corr_order(prior - current)
    cal_funds = _corr_order(current | prior)

    # Matrix: every fund held in the last twelve monthly baskets, plus next
    # month's. Past CORR_MATRIX_MAX, the most recently held win.
    last_held = {}
    for k, m in enumerate(months[-CORR_MATRIX_MONTHS:]):
        for t in m["held"]:
            last_held[t] = k
    for t in nxt:
        last_held[t] = CORR_MATRIX_MONTHS
    recent = sorted(last_held, key=lambda t: -last_held[t])[:CORR_MATRIX_MAX]
    matrix_funds = _corr_order(recent)
    return {
        "months": months, "returns": returns, "last_session": last_session,
        "cal_funds": cal_funds, "matrix_funds": matrix_funds,
        "current": _corr_order(current), "replaced": replaced, "current_period": current_period,
    }


def corr_readings(ctx, funds, window):
    """Month-end readings for every pair of funds at the given window."""
    funds = tuple(f for f in funds if f in ctx["returns"].columns)
    dates = tuple(m["reading"] for m in ctx["months"])
    sub = ctx["returns"][list(funds)] if funds else ctx["returns"].iloc[:, :0]
    return funds, compute_pair_correlations(sub, funds, dates, int(window))


def corr_missing_note(ctx, prices):
    """A short note naming any fund whose prices did not load, or only load
    through an earlier date, so gaps read as data gaps rather than zeros."""
    if ctx is None:
        return ""
    needed = set(ctx["cal_funds"]) | set(ctx["matrix_funds"]) | {"SPY"}
    for m in ctx["months"]:
        needed.update(t for t, w in m["weights"].items() if w * 100.0 >= CORR_HELD_MIN_PCT)
    needed -= set(CASH_LIKE_TICKERS)
    missing, stale = [], []
    for t in sorted(needed):
        if prices is None or t not in prices.columns or prices[t].dropna().empty:
            missing.append(t)
        elif prices[t].dropna().index[-1] < ctx["last_session"] - pd.Timedelta(days=6):
            stale.append(f"{t} (through {_cap_date(prices[t].dropna().index[-1])})")
    parts = []
    if missing:
        parts.append("Prices did not load for " + _cap_join(missing)
                     + "; readings that need them show n/a.")
    if stale:
        parts.append("Prices stop early for " + _cap_join(stale) + ".")
    return " ".join(parts)


# ---------- Idea 1: correlation calendar ----------

def _corr_change(shapes, ann, x_right, cy, d, size=13):
    """Right-aligned change: a red up or blue down triangle and the amount, or
    "steady" under CORR_STEADY."""
    if d is not None and np.isfinite(d) and abs(d) >= CORR_STEADY:
        color = CORR_RISE if d > 0 else CORR_FALL
        amount = f"{abs(d):.2f}"
        _cx_text(ann, x_right, cy, amount, anchor="right", size=size, color=color, weight=600)
        _cx_triangle(shapes, x_right - _dd_text_width(amount, size, True) - 8, cy, d > 0, 4.4, color)
    elif d is not None and np.isfinite(d):
        _cx_text(ann, x_right, cy, "steady", anchor="right", size=size - 0.5, color=TEXT_MUTED)
    else:
        _cx_text(ann, x_right, cy, "n/a", anchor="right", size=size - 0.5, color=TEXT_MUTED)


def _corr_scale_legend(shapes, ann, x, y, w=250):
    """The heat scale labeled Move opposite / Unrelated / Move together."""
    x += 10
    n = 60
    for i in range(n):
        v = -1 + 2 * (i + 0.5) / n
        _cx_rect(shapes, x + w * i / n, y, x + w * (i + 1) / n + 0.6, y + 12, corr_color(v))
    shapes.append(dict(type="rect", x0=x, y0=y, x1=x + w, y1=y + 12,
                       line=dict(color=CORR_PILL_BORDER, width=1), fillcolor="rgba(0,0,0,0)",
                       layer="above"))
    for v, label in [(-1, MINUS + "1"), (-0.5, MINUS + "0.5"), (0, "0"), (0.5, "0.5"),
                     (0.7, "0.7"), (1, "1")]:
        xx = x + w * (v + 1) / 2
        _cx_line(shapes, xx, y + 12, xx, y + 16, CORR_RULE_GRAY, 1)
        _cx_text(ann, xx, y + 25, label, anchor="center", size=11, color=TEXT_MUTED)
    _cx_text(ann, x, y - 10, "Move opposite", size=12, color=TEXT_SECONDARY, weight=600)
    _cx_text(ann, x + w / 2, y - 10, "Unrelated", anchor="center", size=12, color=TEXT_SECONDARY,
             weight=600)
    _cx_text(ann, x + w, y - 10, "Move together", anchor="right", size=12, color=TEXT_SECONDARY,
             weight=600)


def corr_calendar_tiles(months, pairs, values, lag=3):
    """Most linked pair now, biggest shift over `lag` months, and the most
    months any pair spent above CORR_HIGH while the basket held both funds."""
    tiles = []
    first = _corr_month(months[0]["period"])
    now = {p: values[p][-1] for p in pairs if np.isfinite(values[p][-1])}
    if now:
        top = max(now, key=lambda p: now[p])
        hist = [(v, m["period"]) for v, m in zip(values[top], months) if np.isfinite(v)]
        high_v, high_p = max(hist, key=lambda x: x[0])
        if now[top] >= high_v - 0.005:
            sub = f"{_corr_str(now[top])}, its highest since {first}"
        else:
            sub = f"{_corr_str(now[top])}; its high was {_corr_str(high_v)} in {_corr_month(high_p)}"
        tiles.append(("Most linked now", f"{top[0]} & {top[1]}", sub))
    else:
        tiles.append(("Most linked now", "n/a", "No current readings"))
    shifts = {}
    if len(months) > lag:
        for p in pairs:
            a, b = values[p][-1], values[p][-1 - lag]
            if np.isfinite(a) and np.isfinite(b):
                shifts[p] = (b, a)
    word = {1: "1 month", 3: "3 months", 12: "a year"}.get(lag, f"{lag} months")
    if shifts:
        top = max(shifts, key=lambda p: abs(shifts[p][1] - shifts[p][0]))
        then, cur = shifts[top]
        if then >= 0 > cur:
            phrase = "now moving opposite"
        elif then < 0 <= cur:
            phrase = "no longer moving opposite"
        elif cur > then:
            phrase = "moving more together"
        else:
            phrase = "moving less together"
        tiles.append((f"Biggest shift in {word}", f"{top[0]} & {top[1]}",
                      f"{_corr_str(then)} to {_corr_str(cur)}: {phrase}"))
    else:
        tiles.append((f"Biggest shift in {word}", "n/a", "Not enough history yet"))
    best, best_months = None, []
    for p in pairs:
        hits = [m["period"] for v, m in zip(values[p], months)
                if np.isfinite(v) and v > CORR_HIGH and p[0] in m["held"] and p[1] in m["held"]]
        if len(hits) > len(best_months):
            best, best_months = p, hits
    label = f"Held together above {CORR_HIGH:.1f}"
    if best is None:
        tiles.append((label, "None", f"No pair the basket held topped {CORR_HIGH:.1f}"))
    else:
        n = len(best_months)
        years = sorted({p.year for p in best_months})
        if len(years) == 1:
            where = f"all in {years[0]}" if n > 1 else f"in {_corr_month(best_months[0])}"
        else:
            where = f"most recently {_corr_month(best_months[-1])}"
        tiles.append((label, f"{n} month" + ("s" if n != 1 else ""), f"{best[0]} and {best[1]}, {where}"))
    return tiles


def build_corr_calendar_figure(months, pairs, values, tiles, lag=3):
    """Idea 1: one row per fund pair, one cell per month since inception on the
    correlation scale, faded where the basket did not hold both funds; Now and
    change columns at the right; the latest column outlined. 780 px wide."""
    W = ANALYTICS_WIDTH
    shapes, ann = [], []
    hx, hy, htext = [], [], []
    tile_h = _cx_tiles(shapes, ann, tiles, 0)
    n = len(months)
    X0, CELLS_RIGHT, XNOW, XCHG = 168.0, 684.0, 728.0, float(W)
    step = min(15.4, (CELLS_RIGHT - X0 + 1.9) / max(n, 1))
    cw = step - 1.9
    head = tile_h + 22
    top = head + 40
    rh, ch = 27, 22
    for i, m in enumerate(months):
        p = m["period"]
        x = X0 + i * step
        if p.month == 1 or i == 0:
            _cx_text(ann, x, head + 9, str(p.year), size=13, color=TEXT_PRIMARY, weight=700)
        if step >= 11 or p.month in (1, 4, 7, 10):
            _cx_text(ann, x + cw / 2, head + 27, p.strftime("%b")[0], anchor="center", size=11,
                     color=TEXT_MUTED, weight=500)
    _cx_text(ann, XNOW, head + 27, "Now", anchor="right", size=12, color=TEXT_PRIMARY, weight=700)
    _cx_text(ann, XCHG, head + 27, f"vs {lag} mo", anchor="right", size=12, color=TEXT_PRIMARY,
             weight=700)
    for r, (a, b) in enumerate(pairs):
        y = top + r * rh
        cy = y + ch / 2
        _cx_dot(shapes, 10, cy, 4.5, _corr_fund_color(a))
        _cx_text(ann, 20, cy, a, size=13, color=ANALYTICS_CELL_TEXT, weight=700)
        xb = 20 + _dd_text_width(a, 13, True) + 8
        _cx_text(ann, xb, cy, "&amp;", size=12, color=TEXT_MUTED)
        xb += 14
        _cx_dot(shapes, xb + 5, cy, 4.5, _corr_fund_color(b))
        _cx_text(ann, xb + 15, cy, b, size=13, color=ANALYTICS_CELL_TEXT, weight=700)
        vals = values[(a, b)]
        for i, (v, m) in enumerate(zip(vals, months)):
            x = X0 + i * step
            both = a in m["held"] and b in m["held"]
            if np.isfinite(v):
                _cx_rect(shapes, x, y, x + cw, y + ch, corr_color(v), r=2.5,
                         opacity=None if both else CORR_FADED)
            else:
                _cx_rect(shapes, x, y, x + cw, y + ch, HEAT_EMPTY, r=2.5)
            hx.append(x + cw / 2)
            hy.append(cy)
            status = "held both" if both else "not both held"
            htext.append(f"<b>{a} &amp; {b}</b>, {m['period'].strftime('%b %Y')}<br>"
                         f"{_corr_str(v)} ({status})")
        now = vals[-1] if vals else np.nan
        _cx_text(ann, XNOW, cy, _corr_str(now), anchor="right", size=13.5,
                 color=ANALYTICS_CELL_TEXT, weight=700)
        d = now - vals[-1 - lag] if len(vals) > lag else np.nan
        _corr_change(shapes, ann, XCHG, cy, d)
    last_x = X0 + (n - 1) * step
    _cx_rect(shapes, last_x - 2.5, top - 4, last_x + cw + 2.5, top + rh * len(pairs) - 1, "rgba(0,0,0,0)",
             r=4, line_color=BRAND_PURPLE, line_width=1.5, layer="above")
    ly = top + rh * len(pairs) + 34
    _corr_scale_legend(shapes, ann, 0, ly)
    sw = corr_color(0.8)
    _cx_rect(shapes, 322, ly - 0.5, 332, ly + 12.5, sw, r=2)
    _cx_rect(shapes, 334, ly - 0.5, 344, ly + 12.5, sw, r=2, opacity=CORR_FADED)
    _cx_text(ann, 352, ly + 6, "Full color: held both that month", size=12, color=TEXT_SECONDARY)
    _cx_rect(shapes, 326, ly + 22, 340, ly + 36, "rgba(0,0,0,0)", r=3, line_color=BRAND_PURPLE,
             line_width=1.5, layer="above")
    _cx_text(ann, 352, ly + 29, f"Latest reading ({_long_date(months[-1]['reading'])})", size=12,
             color=TEXT_SECONDARY)
    _cx_triangle(shapes, 584, ly + 6, True, 4.6, CORR_RISE)
    _cx_text(ann, 596, ly + 6, "More correlated", size=12, color=TEXT_SECONDARY)
    _cx_triangle(shapes, 584, ly + 29, False, 4.6, CORR_FALL)
    _cx_text(ann, 596, ly + 29, "Less correlated", size=12, color=TEXT_SECONDARY)
    H = int(ly + 46)
    fig = go.Figure()
    _cx_hover(fig, hx, hy, htext, min(cw, ch))
    return _pixel_layout(fig, W, H, shapes, ann)


def corr_calendar_view(ctx, window, lag=3):
    """Pairs (highest current reading first), their readings, and the tiles
    for Correlation Over Time at the given window."""
    funds, values = corr_readings(ctx, ctx["cal_funds"], window)
    pairs = [(a, b) for i, a in enumerate(funds) for b in funds[i + 1:]]
    # Pairs without a current reading sink to the bottom.
    pairs.sort(key=lambda p: -(values[p][-1] if np.isfinite(values[p][-1]) else -9.0))
    tiles = corr_calendar_tiles(ctx["months"], pairs, values, lag) if pairs else []
    return pairs, values, tiles


def render_corr_calendar(ctx):
    window_label = st.pills("Window", CORR_CAL_WINDOWS, default=CORR_CAL_WINDOWS[0],
                            selection_mode="single", key="corr_cal_window") or CORR_CAL_WINDOWS[0]
    window = CORR_WINDOWS[window_label]
    lag = 3
    pairs, values, tiles = corr_calendar_view(ctx, window, lag)
    if not pairs:
        st.info("Correlation Over Time needs at least two current or recent funds with prices.")
        return
    months = ctx["months"]
    fig = build_corr_calendar_figure(months, pairs, values, tiles, lag)
    st.plotly_chart(fig, use_container_width=False,
                    config=chart_config("Correlation Over Time", static=True),
                    key=f"corr_cal_fig_{window}")
    current_name = _corr_month(ctx["current_period"])
    who = f"Pairs among the {current_name} basket ({_cap_join(ctx['current'])})"
    if ctx["replaced"]:
        who += f" plus {_cap_join(ctx['replaced'])}, which it replaced"
    _footnote(
        f"Each cell is the correlation of daily returns over the {CORR_WINDOW_WORDS[window]} ending "
        f"that month; the latest column runs through {_long_date(months[-1]['reading'])}. 1 means two "
        f"funds move in lockstep, 0 means unrelated, {MINUS}1 means opposite. Shades turn dark at 0.7 "
        "and above. Months when the basket held both funds are in full color; other months are faded. "
        f"vs {lag} mo is the change from the reading three months earlier; changes under 0.05 read "
        f"steady. {who}. Daily returns come from adjusted closes on U.S. equity trading days."
    )


# ---------- Idea 2: correlation matrix ----------

def build_corr_matrix_figure(funds, values, months, lag, compare_label):
    """Idea 2: current readings below the diagonal with the change since the
    comparison month, fund names on the diagonal, and each pair's monthly
    readings over the past year as bars above it; then the color key and the
    biggest moves. 780 px wide."""
    W = ANALYTICS_WIDTH
    shapes, ann = [], []
    hx, hy, htext = [], [], []
    n = len(funds)
    LW, TH, CH = 66.0, 30.0, 66.0
    cw = (W - LW) / n
    spark_n = min(CORR_MATRIX_MONTHS, len(months))
    spark_months = months[-spark_n:]

    def val(a, b, k):
        key = (a, b) if (a, b) in values else (b, a)
        series = values.get(key)
        if not series or k >= len(series) or k < -len(series):
            return np.nan
        return series[k]

    for j, t in enumerate(funds):
        _cx_text(ann, LW + j * cw + cw / 2, 15, t, anchor="center", size=13.5,
                 color=TEXT_PRIMARY, weight=700)
    for i, a in enumerate(funds):
        y = TH + i * CH
        mid = y + CH / 2
        _cx_dot(shapes, 10, mid, 4.5, _corr_fund_color(a))
        _cx_text(ann, 20, mid, a, size=13.5, color=TEXT_PRIMARY, weight=700)
        for j, b in enumerate(funds):
            x = LW + j * cw
            if i == j:
                _cx_rect(shapes, x + 2, y + 2, x + cw - 2, y + CH - 2, ANALYTICS_HEADER_BG, r=6)
                name = _corr_fund_name(a)
                words = name.split(" ")
                if _dd_text_width(name, 11.5) > cw - 14 and len(words) > 1:
                    _cx_text(ann, x + cw / 2, mid - 7, words[0], anchor="center", size=11.5,
                             color=TEXT_MUTED, weight=500)
                    _cx_text(ann, x + cw / 2, mid + 8, " ".join(words[1:]), anchor="center",
                             size=11.5, color=TEXT_MUTED, weight=500)
                else:
                    _cx_text(ann, x + cw / 2, mid, name, anchor="center", size=11.5,
                             color=TEXT_MUTED, weight=500)
            elif i > j:
                v = val(a, b, -1)
                then = val(a, b, -1 - lag) if len(months) > lag else np.nan
                fill = corr_color(v)
                ink = _cx_text_on(fill)
                _cx_rect(shapes, x + 2, y + 2, x + cw - 2, y + CH - 2, fill, r=6)
                _cx_text(ann, x + cw / 2, mid - 6, _corr_str(v), anchor="center", size=17,
                         color=ink, weight=700)
                d = v - then if np.isfinite(v) and np.isfinite(then) else np.nan
                if np.isfinite(d) and abs(d) >= CORR_STEADY:
                    amount = f"{abs(d):.2f}"
                    wd = _dd_text_width(amount, 11.5) + 12
                    _cx_triangle(shapes, x + cw / 2 - wd / 2 + 4, mid + 15, d > 0, 3.6, ink)
                    _cx_text(ann, x + cw / 2 - wd / 2 + 11, mid + 15, amount, size=11.5,
                             color=ink, weight=500)
                elif np.isfinite(d):
                    _cx_text(ann, x + cw / 2, mid + 15, "steady", anchor="center", size=11.5,
                             color=ink)
                hx.append(x + cw / 2)
                hy.append(mid)
                then_m = months[-1 - lag] if len(months) > lag else None
                htext.append(
                    f"<b>{b} &amp; {a}</b><br>Now {_corr_str(v)} ({months[-1]['period'].strftime('%b %Y')})"
                    + (f"<br>{compare_label.capitalize()}: {_corr_str(then)} "
                       f"({then_m['period'].strftime('%b %Y')})" if then_m else "")
                )
            else:
                _cx_rect(shapes, x + 2, y + 2, x + cw - 2, y + CH - 2, "#FFFFFF", r=6,
                         line_color=ANALYTICS_RULE, line_width=1)
                px0, px1 = x + 10, x + cw - 14
                py0, py1 = y + 9, y + CH - 9

                def yy(v):
                    return py1 - (max(v, -0.6) + 0.6) / 1.6 * (py1 - py0)

                slot = (px1 - px0) / CORR_MATRIX_MONTHS
                bw = slot - 1.8
                _cx_line(shapes, px0 - 1, yy(0), px1 + 1, yy(0), CORR_RULE_GRAY, 1)
                parts = []
                for k, m in enumerate(spark_months):
                    v = val(a, b, len(months) - spark_n + k)
                    parts.append(f"{m['period'].strftime('%b-%y')} {_corr_str(v)}")
                    if not np.isfinite(v):
                        continue
                    bx = px0 + (CORR_MATRIX_MONTHS - spark_n + k) * slot + 0.9
                    ya, yb = sorted([yy(min(v, 1.0)), yy(0)])
                    _cx_rect(shapes, bx, ya, bx + bw, max(yb, ya + 1.5), corr_color(v), r=1.2)
                hx.append(x + cw / 2)
                hy.append(mid)
                rows = [", ".join(parts[k:k + 4]) for k in range(0, len(parts), 4)]
                htext.append(f"<b>{a} &amp; {b}</b>, month-end readings<br>" + "<br>".join(rows))
    y = TH + n * CH + 28
    _corr_scale_legend(shapes, ann, 0, y)
    for k, v in enumerate([0.55, 0.62, 0.7, 0.78, 0.84, 0.82]):
        hh = 4 + 16 * (v - 0.4) / 0.6
        _cx_rect(shapes, 330 + k * 6, y + 16 - hh, 334.4 + k * 6, y + 16, corr_color(v), r=1)
    _cx_line(shapes, 328, y + 16, 368, y + 16, CORR_RULE_GRAY, 1)
    _cx_text(ann, 378, y + 2, f"Upper half: one bar per month for the past {spark_n} months,", size=12,
             color=TEXT_SECONDARY)
    _cx_text(ann, 378, y + 18, "colored and sized by that month's reading", size=12,
             color=TEXT_SECONDARY)

    # Biggest moves since the comparison month, two columns of three.
    moves = []
    if len(months) > lag:
        for i, a in enumerate(funds):
            for b in funds[i + 1:]:
                t0, t1 = val(a, b, -1 - lag), val(a, b, -1)
                if np.isfinite(t0) and np.isfinite(t1):
                    moves.append((a, b, t0, t1, t1 - t0))
    moves.sort(key=lambda m: -abs(m[4]))
    moves = moves[:6]
    my = y + 52
    if moves:
        then_p = months[-1 - lag]["period"]
        since = then_p.strftime("%B") if then_p.year == months[-1]["period"].year else _corr_month(then_p)
        _cx_text(ann, 0, my + 10, f"Biggest moves since {since}", size=15, color=TEXT_PRIMARY, weight=600)
        col_w = (W - 36) / 2
        half = (len(moves) + 1) // 2
        for k, (a, b, t0, t1, d) in enumerate(moves):
            col, row = (0, k) if k < half else (1, k - half)
            x0 = col * (col_w + 36)
            ry = my + 26 + row * 32
            _cx_line(shapes, x0, ry, x0 + col_w, ry, ANALYTICS_RULE, 1)
            _cx_text(ann, x0, ry + 16, f"{a} &amp; {b}", size=13.5, color=ANALYTICS_CELL_TEXT, weight=700)
            _cx_text(ann, x0 + 122, ry + 16, f"{_corr_str(t0)} to {_corr_str(t1)}", size=13.5,
                     color=TEXT_SECONDARY)
            word = "up" if d > 0 else ("down" if d < 0 else "flat")
            _cx_text(ann, x0 + col_w, ry + 16, f"{word} {abs(d):.2f}", anchor="right", size=13.5,
                     color=ANALYTICS_CELL_TEXT, weight=600)
        H = int(my + 26 + half * 32 + 6)
    else:
        H = int(my)
    fig = go.Figure()
    _cx_hover(fig, hx, hy, htext, min(cw, CH) - 6)
    return _pixel_layout(fig, W, H, shapes, ann)


def render_corr_matrix(ctx):
    c1, c2 = st.columns([3, 2])
    with c1:
        compare_label = st.pills("Compare with", list(CORR_COMPARE), default="3 months ago",
                                 selection_mode="single", key="corr_mx_compare") or "3 months ago"
    with c2:
        window_label = st.pills("Window", CORR_MATRIX_WINDOWS, default=CORR_MATRIX_WINDOWS[0],
                                selection_mode="single", key="corr_mx_window") or CORR_MATRIX_WINDOWS[0]
    window = CORR_WINDOWS[window_label]
    lag = CORR_COMPARE[compare_label]
    funds, values = corr_readings(ctx, ctx["matrix_funds"], window)
    if len(funds) < 2:
        st.info("Correlation Matrix needs at least two current or recent funds with prices.")
        return
    months = ctx["months"]
    lag = min(lag, len(months) - 1)
    fig = build_corr_matrix_figure(list(funds), values, months, lag, compare_label)
    st.plotly_chart(fig, use_container_width=False,
                    config=chart_config("Correlation Matrix", static=True),
                    key=f"corr_mx_fig_{window}_{lag}")
    spark = months[-min(CORR_MATRIX_MONTHS, len(months)):]
    then_txt = (f"the reading {compare_label} ({_long_date(months[-1 - lag]['reading'])})"
                if lag >= 1 else "the prior reading")
    _footnote(
        f"Correlation of daily returns over the {CORR_WINDOW_WORDS[window]} ending "
        f"{_long_date(months[-1]['reading'])}. The arrow under each value is the change from "
        f"{then_txt}; changes under 0.05 read steady. The bars above the diagonal show the same pair's "
        f"month-end readings from {_corr_month(spark[0]['period'])} to {_corr_month(spark[-1]['period'])}, "
        "bars below the line meaning the pair moved opposite. Funds are those held at any point in the "
        "last 12 months plus next month's basket. Hover a cell for the exact readings."
    )


# ---------- Idea 4: did the diversification hold? ----------

def _bets_dlv_text(r):
    """Hover wording for what a month delivered."""
    if np.isfinite(r["dlv"]):
        return f"Delivered {_bets_fmt(r['dlv'])}" + ("" if r["closed"] else " so far")
    if r["closed"] or r["n_dlv"] >= BETS_MIN_SESSIONS:
        return "Delivered: n/a (prices missing)"
    return f"Delivered: shows after {BETS_MIN_SESSIONS} sessions"


def bets_summary_tiles(rows, floor):
    shown = [r for r in rows if not r["tbill"] and np.isfinite(r["pre"])]
    tiles = []
    latest = shown[-1] if shown else None
    if latest is None:
        tiles.append(("Latest month", "n/a", "No bets reading yet"))
    else:
        name = _corr_month(latest["period"])
        if np.isfinite(latest["dlv"]):
            label = name if latest["closed"] else f"{name} so far"
            tiles.append((label, f"{_bets_fmt(latest['pre'])} to {_bets_fmt(latest['dlv'])}",
                          "Bets going in versus delivered" + ("" if latest["closed"] else " so far")))
        elif latest["closed"] or latest["n_dlv"] >= BETS_MIN_SESSIONS:
            tiles.append((name, f"{_bets_fmt(latest['pre'])} going in",
                          "What it delivered is n/a: prices missing"))
        else:
            tiles.append((name, f"{_bets_fmt(latest['pre'])} going in",
                          f"What it delivered shows after {BETS_MIN_SESSIONS} sessions"))
    below = [r for r in shown if bets_is_low(r["pre"], floor)]
    year = latest["period"].year if latest else local_now().year
    in_year = sum(1 for r in below if r["period"].year == year)
    tiles.append(("Went in below the floor", f"{len(below)} of {len(shown)}",
                  f"Below {floor:.1f}; {in_year} of them in {year}"))
    slipped = sum(1 for r in shown if r["closed"] and np.isfinite(r["dlv"])
                  and not bets_is_low(r["pre"], floor) and bets_is_low(r["dlv"], floor))
    tiles.append(("Slipped below during the month", str(slipped),
                  f"Went in at {floor:.1f} or more, delivered below it"))
    return tiles


def build_bets_tiles_figure(rows, floor):
    shapes, ann = [], []
    h = _cx_tiles(shapes, ann, bets_summary_tiles(rows, floor), 0)
    return _pixel_layout(go.Figure(), ANALYTICS_WIDTH, int(h + 2), shapes, ann)


def build_bets_floor_figure(rows, floor):
    """Over time: bets going in each month as bars on a light track up to 4,
    purple at or above the floor and red below it, with the dashed floor; a
    strip underneath shows delivered minus going in. 780 px wide."""
    W = ANALYTICS_WIDTH
    shapes, ann = [], []
    hx, hy, htext = [], [], []
    n = len(rows)
    X0, X1 = 56.0, float(W)
    step = (X1 - X0) / max(n, 1)
    bw = step * 0.62
    TOP, H4 = 12.0, 150.0

    def yb(v):
        return TOP + H4 - v / BETS_CAP * H4

    base = yb(0)
    cap = lambda v: min(float(v), BETS_CAP)
    tbill_idx = [i for i, r in enumerate(rows) if r["tbill"]]
    for i, r in enumerate(rows):
        if r["tbill"] or not np.isfinite(r["pre"]):
            continue
        cx = X0 + (i + 0.5) * step
        v = cap(r["pre"])
        low = bets_is_low(r["pre"], floor)
        _cx_rect(shapes, cx - bw / 2, yb(BETS_CAP), cx + bw / 2, base, BETS_TRACK, r=3)
        _cx_rect(shapes, cx - bw / 2, yb(v), cx + bw / 2, base, BETS_LOW if low else BETS_PURPLE, r=3)
        status = ("below the floor" if low else "at or above the floor") + f" of {floor:.1f}"
        dl_txt = _bets_dlv_text(r)
        hx.append(cx)
        hy.append((yb(BETS_CAP) + base) / 2)
        htext.append(f"<b>{_corr_month(r['period'])}</b><br>Going in {_bets_fmt(r['pre'])} ({status})"
                     f"<br>{dl_txt}")
    fy = yb(floor)
    _cx_line(shapes, X0, fy, X1, fy, ANALYTICS_CELL_TEXT, 1.5, dash="5px,4px")
    label = f"Floor {floor:.1f}"
    lw = _dd_text_width(label, 12, True) + 16
    if tbill_idx:
        gx = X0 + (tbill_idx[0] + tbill_idx[-1] + 1) / 2 * step
        _cx_rect(shapes, gx - lw / 2, fy - 24, gx + lw / 2, fy - 5, "#FFFFFF", r=4, layer="above")
        _cx_text(ann, gx, fy - 14.5, label, anchor="center", size=12, color=ANALYTICS_CELL_TEXT, weight=700)
        _cx_text(ann, gx, fy + 24, "T-bills", anchor="center", size=12, color=TEXT_SECONDARY, weight=600)
    else:
        _cx_rect(shapes, X1 - lw, fy - 24, X1, fy - 5, "#FFFFFF", r=4, layer="above")
        _cx_text(ann, X1 - lw / 2, fy - 14.5, label, anchor="center", size=12,
                 color=ANALYTICS_CELL_TEXT, weight=700)
    for v in range(0, int(BETS_CAP) + 1):
        _cx_text(ann, X0 - 8, yb(v), str(v), anchor="right", size=12, color=TEXT_MUTED, weight=500)
    sy = base + 50
    SC = 14.0
    _cx_line(shapes, X0, sy, X1, sy, CORR_PILL_BORDER, 1)
    for i, r in enumerate(rows):
        if r["tbill"] or not (np.isfinite(r["pre"]) and np.isfinite(r["dlv"])):
            continue
        cx = X0 + (i + 0.5) * step
        d = cap(r["dlv"]) - cap(r["pre"])
        if abs(d) < CORR_STEADY:
            _cx_rect(shapes, cx - bw / 2, sy - 1, cx + bw / 2, sy + 1, CORR_RULE_GRAY, r=1)
            continue
        hh = abs(d) * SC
        y0, y1 = (sy - hh, sy) if d > 0 else (sy, sy + hh)
        _cx_rect(shapes, cx - bw / 2, y0, cx + bw / 2, y1, BETS_GOOD if d > 0 else BETS_LOW, r=2)
    _cx_text(ann, X0 - 8, sy - 12, "Better", anchor="right", size=12, color=BETS_GOOD, weight=700)
    _cx_text(ann, X0 - 8, sy + 12, "Worse", anchor="right", size=12, color=BETS_LOW, weight=700)
    for i, r in enumerate(rows):
        if r["period"].month == 1 or i == 0:
            _cx_text(ann, X0 + i * step + 2, sy + 50, str(r["period"].year), size=13,
                     color=TEXT_PRIMARY, weight=700)
    # Legend row
    ly = sy + 84
    lx = 0.0
    items = [("box", BETS_PURPLE, "Bets going in"), ("box", BETS_LOW, "Below the floor"),
             ("dash", ANALYTICS_CELL_TEXT, f"Floor of {floor:.1f} bets"),
             ("box", BETS_GOOD, "Month delivered more"), ("box", BETS_LOW, "Month delivered fewer")]
    for kind, color, text in items:
        if kind == "box":
            _cx_rect(shapes, lx, ly - 6, lx + 14, ly + 6, color, r=2)
            lx += 21
        else:
            _cx_line(shapes, lx, ly, lx + 22, ly, color, 1.5, dash="4px,3px")
            lx += 29
        _cx_text(ann, lx, ly, text, size=13, color=TEXT_SECONDARY)
        lx += _dd_text_width(text, 13) + 18
    H = int(ly + 14)
    fig = go.Figure()
    _cx_hover(fig, hx, hy, htext, bw)
    return _pixel_layout(fig, W, H, shapes, ann)


def build_bets_grid_figure(rows, floor):
    """Month by month: rows for each year, Jan to Dec plus an Average column.
    The big number and the cell color are bets going in; the stripe along the
    bottom is what the month delivered, on the same scale. Reds only, so months
    above the floor never read as a sea of red. A key sits above the grid."""
    W = ANALYTICS_WIDTH
    shapes, ann = [], []
    hx, hy, htext = [], [], []
    by = {r["period"]: r for r in rows}
    latest_p = rows[-1]["period"]
    shown = [r for r in rows if not r["tbill"] and np.isfinite(r["pre"])]
    sample = next((r for r in reversed(shown) if np.isfinite(r["dlv"])), shown[-1] if shown else None)

    # Key: the 1-to-4 scale with the floor marked, and a sample cell.
    kx, ky, kw = 10.0, 26.0, 312.0
    segs = 60
    for i in range(segs):
        b = 1 + 3 * (i + 0.5) / segs
        _cx_rect(shapes, kx + i * kw / segs, ky, kx + (i + 1) * kw / segs + 0.4, ky + 12, bets_color(b, floor))
    shapes.append(dict(type="rect", x0=kx, y0=ky, x1=kx + kw, y1=ky + 12, fillcolor="rgba(0,0,0,0)",
                       line=dict(color=CORR_PILL_BORDER, width=1), layer="above"))
    for b in (1, 2, 3, 4):
        xx = kx + (b - 1) / 3 * kw
        _cx_line(shapes, xx, ky + 12, xx, ky + 16, CORR_RULE_GRAY, 1)
        _cx_text(ann, xx, ky + 25, str(b), anchor="center", size=11, color=TEXT_MUTED, weight=500)
    xc = kx + (floor - 1) / 3 * kw
    _cx_line(shapes, xc, ky - 5, xc, ky + 17, ANALYTICS_CELL_TEXT, 2)
    _cx_text(ann, xc, ky - 14, f"Floor {floor:.1f}", anchor="center", size=12,
             color=ANALYTICS_CELL_TEXT, weight=700)
    _cx_text(ann, kx, ky + 41, "Too few bets", size=12, color=BETS_LOW, weight=600)
    _cx_text(ann, kx + kw, ky + 41, "At or above the floor", anchor="right", size=12,
             color=TEXT_SECONDARY, weight=600)
    CW_S, CH_S, SH = 52.0, 52.0, 17.0

    def stripe(x, y, w, v):
        """Delivered stripe: deep red with a white edge below the floor, else white."""
        if v is not None and np.isfinite(v) and bets_is_low(v, floor):
            fill = bets_color(v, floor)
            _cx_rect(shapes, x, y, x + w, y + SH, fill, r=4, line_color="#FFFFFF", line_width=1.5)
            return fill
        _cx_rect(shapes, x, y, x + w, y + SH, "#FFFFFF", r=4, line_color=BETS_STRIPE_EDGE, line_width=1)
        return "#FFFFFF"

    if sample is not None:
        sx, sy0 = 392.0, 14.0
        fill = bets_color(sample["pre"], floor)
        _cx_rect(shapes, sx, sy0, sx + CW_S, sy0 + CH_S, fill, r=6)
        _cx_text(ann, sx + CW_S / 2, sy0 + 17, _bets_fmt(sample["pre"]), anchor="center", size=15,
                 color=_cx_text_on(fill), weight=700)
        sfill = stripe(sx + 3, sy0 + CH_S - SH - 3, CW_S - 6, sample["dlv"])
        _cx_text(ann, sx + CW_S / 2, sy0 + CH_S - 3 - SH / 2, _bets_fmt(sample["dlv"]), anchor="center",
                 size=11, color=_cx_text_on(sfill), weight=700)
        lx = sx + CW_S + 8
        _cx_line(shapes, lx, sy0 + 17, lx + 16, sy0 + 17, CORR_RULE_GRAY, 1)
        _cx_text(ann, lx + 22, sy0 + 17, "Bets going in, which sets the cell color", size=13,
                 color=TEXT_PRIMARY, weight=600)
        _cx_line(shapes, lx, sy0 + CH_S - 11.5, lx + 16, sy0 + CH_S - 11.5, CORR_RULE_GRAY, 1)
        _cx_text(ann, lx + 22, sy0 + CH_S - 11.5, "What the month delivered, on the same scale", size=13,
                 color=TEXT_PRIMARY, weight=600)

    # Grid
    top = 92.0
    LW, GX, CH = 56.0, 4.0, 52.0
    AVG_W = 60.0
    cw = (W - LW - 12 * GX - AVG_W - 2) / 12
    x_avg = LW + 12 * (cw + GX) + 2
    for j, name in enumerate(BETS_MONTHS):
        _cx_text(ann, LW + j * (cw + GX) + cw / 2, top + 9, name, anchor="center", size=12,
                 color=TEXT_MUTED, weight=600)
    _cx_text(ann, x_avg + AVG_W / 2, top + 9, "Average", anchor="center", size=12,
             color=TEXT_PRIMARY, weight=700)
    years = list(range(rows[0]["period"].year, latest_p.year + 1))
    for k, year in enumerate(years):
        y = top + 22 + k * (CH + GX)
        _cx_text(ann, 0, y + CH / 2, str(year), size=14, color=TEXT_PRIMARY, weight=700)
        vals = []
        for j in range(12):
            p = pd.Period(year=year, month=j + 1, freq="M")
            x = LW + j * (cw + GX)
            r = by.get(p)
            if r is None:
                _cx_rect(shapes, x, y, x + cw, y + CH, HEAT_EMPTY, r=6)
                continue
            if r["tbill"]:
                _cx_rect(shapes, x, y, x + cw, y + CH, BETS_TBILL_FILL, r=6)
                _cx_text(ann, x + cw / 2, y + CH / 2, "T-bills", anchor="center", size=11,
                         color=TEXT_SECONDARY, weight=600)
                hx.append(x + cw / 2)
                hy.append(y + CH / 2)
                htext.append(f"<b>{_corr_month(p)}</b><br>Mostly T-bills; left out")
            elif not np.isfinite(r["pre"]):
                _cx_rect(shapes, x, y, x + cw, y + CH, BETS_TBILL_FILL, r=6)
                _cx_text(ann, x + cw / 2, y + CH / 2, "n/a", anchor="center", size=11, color=TEXT_MUTED)
            else:
                a, d = r["pre"], r["dlv"]
                vals.append(min(a, BETS_CAP))
                fill = bets_color(a, floor)
                _cx_rect(shapes, x, y, x + cw, y + CH, fill, r=6)
                _cx_text(ann, x + cw / 2, y + 17, _bets_fmt(a), anchor="center", size=15,
                         color=_cx_text_on(fill), weight=700)
                sfill = stripe(x + 3, y + CH - SH - 3, cw - 6, d)
                stripe_txt = _bets_fmt(d) if np.isfinite(d) else "–"
                _cx_text(ann, x + cw / 2, y + CH - 3 - SH / 2, stripe_txt, anchor="center", size=11,
                         color=_cx_text_on(sfill) if np.isfinite(d) else TEXT_MUTED, weight=700)
                status = "below the floor" if bets_is_low(a, floor) else "at or above the floor"
                dl_txt = _bets_dlv_text(r)
                hx.append(x + cw / 2)
                hy.append(y + CH / 2)
                htext.append(f"<b>{_corr_month(p)}</b><br>Going in {_bets_fmt(a)} ({status})<br>{dl_txt}")
            if p == latest_p:
                _cx_rect(shapes, x - 2.5, y - 2.5, x + cw + 2.5, y + CH + 2.5, "rgba(0,0,0,0)", r=7,
                         line_color=BRAND_PURPLE, line_width=2, layer="above")
        if vals:
            av = float(np.mean(vals))
            fill = bets_color(av, floor)
            _cx_rect(shapes, x_avg, y, x_avg + AVG_W, y + CH, fill, r=6)
            _cx_text(ann, x_avg + AVG_W / 2, y + CH / 2, f"{av:.1f}", anchor="center", size=15,
                     color=_cx_text_on(fill), weight=700)
    H = int(top + 22 + len(years) * (CH + GX) + 2)
    fig = go.Figure()
    _cx_hover(fig, hx, hy, htext, min(cw, CH))
    return _pixel_layout(fig, W, H, shapes, ann)


def _corr_subhead(title, sub):
    st.markdown(
        f'<div style="margin:1.6rem 0 0.4rem 0;">'
        f'<div style="font-size:1.12rem; font-weight:700; color:{TEXT_PRIMARY}; '
        f'letter-spacing:-0.01em;">{title}</div>'
        f'<div style="font-size:0.9rem; color:{TEXT_SECONDARY}; margin-top:0.15rem;">{sub}</div></div>',
        unsafe_allow_html=True,
    )


def _bets_minor_head(title, sub):
    st.markdown(
        f'<div style="margin:0.9rem 0 0.3rem 0;">'
        f'<div style="font-size:1rem; font-weight:700; color:{TEXT_PRIMARY};">{title}</div>'
        f'<div style="font-size:0.85rem; line-height:1.45; color:{TEXT_SECONDARY}; margin-top:0.1rem;">'
        f'{sub}</div></div>',
        unsafe_allow_html=True,
    )


# Streamlit draws sliders in its default red when no theme is set; this keeps
# the floor slider in brand purple without changing any other widget.
BETS_SLIDER_CSS = """
<style>
.st-key-div_floor [data-testid="stSliderThumbValue"],
.st-key-div_floor [data-testid="stSliderThumbValue"] p { color: #3A0CA3 !important; }
.st-key-div_floor [role="slider"],
.st-key-div_floor div:has(> div > input[type="range"]) {
    background-color: #3A0CA3 !important; border-color: #3A0CA3 !important; }
.st-key-div_floor [role="slider"]:focus,
.st-key-div_floor div:has(> div > input[type="range"]:focus) {
    box-shadow: 0 0 0 3.2px rgba(58, 12, 163, 0.3) !important; }
.st-key-div_floor div:has(+ div > div > input[type="range"]),
.st-key-div_floor div:has(> [role="slider"]) + div {
    background-image: none !important; background-color: rgba(151, 166, 195, 0.35) !important; }
</style>
"""


def bets_rows(ctx):
    """Bets going in and delivered for every month shown (cached)."""
    months = ctx["months"]
    spec = tuple(
        (str(m["period"]), m["date"], m["reading"],
         tuple(sorted((t, round(float(w), 10)) for t, w in m["weights"].items())),
         round(float(m["tbill"]), 10), bool(m["closed"]))
        for m in months
    )
    tickers = sorted({t for m in months for t in m["weights"] if t in ctx["returns"].columns})
    return compute_bets_rows(ctx["returns"][tickers], spec)


def render_bets_view(ctx):
    rows = bets_rows(ctx)
    if not any(np.isfinite(r["pre"]) for r in rows if not r["tbill"]):
        st.info("Did the Diversification Hold? needs daily prices for the funds each month held.")
        return
    st.markdown(BETS_SLIDER_CSS, unsafe_allow_html=True)
    col, note = st.columns([2, 3], vertical_alignment="bottom")
    with col:
        floor = st.slider("Floor", min_value=BETS_FLOOR_MIN, max_value=BETS_FLOOR_MAX,
                          value=BETS_FLOOR_DEFAULT, step=BETS_FLOOR_STEP, format="%.1f",
                          key="div_floor",
                          help="The fewest independent bets a month should go in with.")
    with note:
        st.markdown(f'<p style="font-size:0.85rem; color:{TEXT_SECONDARY}; margin:0 0 1.1rem 0;">'
                    'Minimum bets going in; both charts and the tiles follow it.</p>',
                    unsafe_allow_html=True)
    floor = round(float(floor), 1)
    st.plotly_chart(build_bets_tiles_figure(rows, floor), use_container_width=False,
                    config=chart_config("Did the Diversification Hold", static=True),
                    key=f"bets_tiles_fig_{floor:.1f}")
    _bets_minor_head(
        "Over time",
        "Bars are bets going in, against the floor. The strip underneath shows how each month did: "
        "green up when it delivered more bets than it went in with, red down when it delivered fewer."
    )
    st.plotly_chart(build_bets_floor_figure(rows, floor), use_container_width=False,
                    config=chart_config("Independent Bets Over Time", static=True),
                    key=f"bets_floor_fig_{floor:.1f}")
    _bets_minor_head(
        "Month by month",
        "Cell color and the big number are bets going in; the stripe is what the month delivered. "
        "Months below the floor turn deep red."
    )
    st.plotly_chart(build_bets_grid_figure(rows, floor), use_container_width=False,
                    config=chart_config("Independent Bets Month by Month", static=True),
                    key=f"bets_grid_fig_{floor:.1f}")
    tbill = [r["period"] for r in rows if r["tbill"]]
    tbill_txt = ""
    if tbill:
        span = (_corr_month(tbill[0]) if len(tbill) == 1 else
                f"{tbill[0].strftime('%B')} to {_corr_month(tbill[-1])}" if tbill[0].year == tbill[-1].year
                else f"{_corr_month(tbill[0])} to {_corr_month(tbill[-1])}")
        tbill_txt = f" {span} held mostly T-bills and {'is' if len(tbill) == 1 else 'are'} left out."
    last = rows[-1]
    open_txt = ""
    if not last["closed"]:
        open_txt = (f" {_corr_month(last['period'])} is month to date through "
                    f"{_long_date(last['reading_date'])}; what it delivered appears once it has "
                    f"{BETS_MIN_SESSIONS} sessions and settles when the month closes.")
    _footnote(
        "Independent bets is the diversification ratio squared (Choueifaty and Coignard, 2008) for each "
        "month's starting weights: 1 means the funds behaved as one bet; four unrelated, equally volatile "
        f"funds score 4. Going in uses the {BETS_WINDOW} trading days before the month; delivered uses the "
        "month's own daily returns. Starting weights are the holdings at the close of the prior month's "
        "final trading day, the same weights as Asset Allocation Over Time. 4+ marks readings above 4, "
        "when the funds moved against each other, mostly while holding the anti-beta fund BTAL."
        f"{tbill_txt} Floor tests use the one-decimal value shown, so a cell that reads 2.2 is never below "
        f"a 2.2 floor. The outlined cell is the latest month.{open_txt}"
    )


def corr_load_context(baskets):
    """Load prices for every fund the baskets held (plus next month's basket
    and SPY) through load_holding_prices, then build the shared context.
    Returns (context or None, prices)."""
    next_rows = load_next_allocation()
    tickers = corr_price_tickers(baskets, next_rows)
    start = (pd.Timestamp(ALLOC_HISTORY_START) - timedelta(days=CORR_PRICE_LEAD_DAYS)).strftime("%Y-%m-%d")
    end = local_now().strftime("%Y-%m-%d")
    prices = load_holding_prices(tuple(tickers), start, end)
    return corr_section_context(baskets, prices, next_rows), prices


def render_correlation_section(holdings_values, totals):
    """Correlation and Diversification: Ideas 1, 2 and 4, each guarded so a
    data problem in one view leaves the others standing."""
    st.markdown(
        f'<p style="font-size:0.92rem; color:{TEXT_SECONDARY}; margin:0 0 0.4rem 0;">How the basket\'s '
        'funds have moved together, and whether each month kept the diversification it went in with.</p>',
        unsafe_allow_html=True,
    )
    baskets = corr_going_in_baskets(holdings_values, totals)
    if not baskets:
        st.info("Correlation and diversification need holdings_daily_values.csv, which did not load.")
        return
    ctx, prices = corr_load_context(baskets)
    if ctx is None:
        st.info("Correlation and diversification need daily fund prices, which did not load right now. "
                "Reloading in a few minutes usually restores them.")
        return
    note = corr_missing_note(ctx, prices)
    if note:
        st.caption(note)
    _corr_subhead("Correlation Over Time", "How closely each pair of funds has moved together, month by month.")
    _render_guarded("Correlation Over Time", render_corr_calendar, ctx, heading=False)
    _corr_subhead("Correlation Matrix", "Today's readings below the diagonal, each pair's past year above it.")
    _render_guarded("Correlation Matrix", render_corr_matrix, ctx, heading=False)
    _corr_subhead("Did the Diversification Hold?",
                  "How many independent bets each month's basket went in with, and how many the month "
                  "delivered, against a floor you set.")
    _render_guarded("Did the Diversification Hold?", render_bets_view, ctx, heading=False)


# ===========================================================================
# 9. LOOK-THROUGH EXPOSURE (added October 31, 2026)
#
# Everything the basket's funds hold, combined, so overlap between funds is
# visible (chips held through both QQQ and EMXC, for example). Built from the
# mockups Tyler approved on October 31, 2026 (Look-Through Exposure Mockups
# canvas, boards Main, Table, Treemap and Risk):
#
#   Flow    funds on the left flowing into themes on the right (Option A)
#   Table   each theme for the selected basket against the basket before it,
#           with each fund's contribution and the largest single holdings
#           across funds (Option B)
#   Map     treemap of themes grouped into stocks, commodities and crypto,
#           with the largest single positions underneath (Option C)
#   Where the Risk Comes From   each fund's share of the money next to its
#           share of the basket's variance (the companion)
#
# Baskets. "Current" is the going-in basket from corr_going_in_baskets, the
# same rules as Current Allocation and Asset Allocation Over Time (month-start
# override and ALLOC_HISTORY_EXECUTION_CORRECTIONS included). "Next" is
# next_allocation.json when it differs from Current. While the holdings data
# ends on a month's final session without that rebalance's fills, the pending
# month is the month that just closed, drifted; Current then stays on the
# month that closed and next_allocation.json is Next (lt_baskets).
#
# Fund holdings. holdings_snapshot.json, written on the PC by
# make_holdings_snapshot.py in ae-dashboard-deploy from free issuer files
# (Invesco for QQQ, iShares for IWM and EMXC) and committed with the other
# data files, so the cloud app never calls the issuers. HGER uses the live
# Harbor fetch that What HGER Holds already makes (cached six hours), then
# the saved QCI snapshots, then the holdings snapshot. GLD, BIL and IBIT have
# fixed look-throughs; any other fund shows as one "Not broken down" block.
# Daily prices for the companion come through load_holding_prices with the
# same arguments as the correlation section, so the two share one fetch.
#
# Nothing here touches the return series.
# ===========================================================================

LT_SECTION_TITLE = "Look-Through Exposure"
LT_SNAPSHOT_NAME = "holdings_snapshot.json"
# The deploy working copy under the home folder. The local app on the PC
# reads the snapshot from there, so it needs no copy beside app.py.
LT_DEPLOY_DIR_PARTS = ("Claude", "Projects", "Asymmetric Edge Chart Dashboard", "ae-dashboard-deploy")
LT_VIEWS = ["Flow", "Table", "Map"]
LT_RISK_WINDOWS = {"3 months": 63, "12 months": 252}
LT_MIN_PCT = 0.05            # themes, funds and flows below this share of the portfolio are not drawn
LT_HELD_PCT = 0.5            # a fund counts as held at 0.5% of the basket, as in the Rebalance Log
LT_SAME_BASKET_PTS = 1.0     # baskets within a point on every fund are the same basket (fills vs. targets)
LT_MAP_NAME_PCT = 0.5        # Map names a single holding at 0.5% of the portfolio or more
LT_PILL_KEYS = ("lt_view", "lt_basket", "lt_risk_basket", "lt_risk_window")
LT_SNAPSHOT_FUNDS = ("QQQ", "IWM", "EMXC", "HGER")   # the funds make_holdings_snapshot.py fetches

# Theme key -> (label, color, family). Stocks are blues, commodities browns
# and crypto orange (mockup palette; gold, crops and bitcoin are the Asset
# Allocation Over Time category colors). Cash and "not broken down" are
# neutral grays that appear only when a basket holds them.
LT_THEMES = {
    "semis": ("Chips", "#1B365D", "stocks"),
    "other_tech": ("Software & other tech", "#35608F", "stocks"),
    "internet": ("Internet & media", "#5F87B8", "stocks"),
    "consumer": ("Consumer", "#8EABCF", "stocks"),
    "health": ("Health care", "#A9BFDA", "stocks"),
    "financials": ("Financials", "#B9CAE0", "stocks"),
    "industrials": ("Industrials", "#C6D4E6", "stocks"),
    "energy_mat": ("Energy & materials stocks", "#D2DDEC", "stocks"),
    "re_util": ("Real estate & utilities", "#DDE5F0", "stocks"),
    "oil": ("Oil & fuels", "#6E4318", "commod"),
    "gold": ("Gold", "#E4D294", "commod"),
    "agri": ("Crops", "#B07D45", "commod"),
    "livestock": ("Livestock", "#CDA67C", "commod"),
    "ind_metals": ("Industrial metals", "#8F7B66", "commod"),
    "commod_other": ("Other commodities", "#A8927A", "commod"),
    "bitcoin": ("Bitcoin", "#F59A3C", "crypto"),
    "cash": ("T-bills & cash", "#D3D6DD", "cash"),
    "not_broken": ("Not broken down", "#A9ADB7", "other"),
}
LT_FAMILIES = [("stocks", "Stocks"), ("commod", "Commodities"), ("crypto", "Crypto"),
               ("cash", "Cash"), ("other", "Other")]
LT_OTHER_STOCKS = ["consumer", "health", "financials", "industrials", "energy_mat", "re_util"]
LT_SHORT = {"semis": "chips", "other_tech": "tech", "internet": "internet", "consumer": "consumer",
            "health": "health care", "financials": "financials", "industrials": "industrials",
            "energy_mat": "energy and materials", "re_util": "real estate", "oil": "fuels",
            "gold": "gold", "agri": "crops", "livestock": "livestock", "ind_metals": "metals",
            "commod_other": "commodities", "bitcoin": "bitcoin", "cash": "cash", "not_broken": "holdings"}
# Shorter labels tried, in order, when a label does not fit its box or tile.
LT_ALT_LABELS = {
    "Software & other tech": ("Software & tech", "Software"),
    "Internet & media": ("Internet",),
    "Energy & materials stocks": ("Energy & materials", "Energy"),
    "Real estate & utilities": ("Real estate",),
    "Industrial metals": ("Metals",),
    "Health care": ("Health",),
    "Samsung Electronics": ("Samsung",),
    "Not broken down": ("Other",),
    "T-bills & cash": ("Cash",),
    "Emerging mkts": ("EM",),
    "Other commodities": ("Other",),
}
# Residual blocks on the Map: what a fund holds in a theme beyond its named holdings.
LT_RESIDUAL_LABEL = {"IWM": "Small caps", "EMXC": "Emerging mkts"}
LT_GOLD_EDGE = "#C9B87A"     # outline that keeps the pale gold swatch visible on white
LT_SHADE = "#CBBFEB"         # Table cell shading at the largest single contribution
LT_BAR = BAR_SERIES_COLORS["AsymEdge"]   # #4F2DB8, the bar-variant Asymmetric Edge purple
LT_TRACK = "#ECECF1"
LT_DOT = "#B9BBC4"           # Table placeholder for a fund that holds none of a theme
LT_CASH_COLOR = "#8C867C"    # the cash pseudo-fund, in BIL's warm gray

# Funds with a fixed look-through, so they need no holdings file. CASH is the
# account's money market and uninvested cash.
LT_FIXED = {"GLD": ("gold", "Gold"), "BIL": ("cash", "T-bills"), "IBIT": ("bitcoin", "Bitcoin"),
            "GBTC": ("bitcoin", "Bitcoin"), "BITO": ("bitcoin", "Bitcoin"), "CASH": ("cash", "Cash")}

# Harbor (Quantix Commodity Index) sector -> theme, as make_holdings_snapshot.py maps it.
LT_QCI_THEME = {
    "Petroleum": "oil", "Natural Gas": "oil", "Energy": "oil",
    "Precious": "gold",
    "Grains And Soybean Products": "agri", "Softs": "agri",
    "LivestockAndDairy": "livestock",
    "Industrial": "ind_metals",
}
LT_QCI_NAMES = {
    "Brent Crude Oil": "Brent crude", "WTI Crude Oil": "WTI crude", "Crude Oil": "WTI crude",
    "Gasoil": "Gasoil", "RBOB Gasoline": "Gasoline", "Heating Oil": "Heating oil",
    "Natural Gas": "Natural gas", "Gold": "Gold", "Silver": "Silver", "Platinum": "Platinum",
    "Palladium": "Palladium", "Corn": "Corn", "Wheat": "Wheat", "Kansas Wheat": "Wheat",
    "Soybeans": "Soybeans", "Soymeal": "Soymeal", "Bean Oil": "Soybean oil", "Cocoa": "Cocoa",
    "Sugar": "Sugar", "Coffee": "Coffee", "Cotton": "Cotton", "Comex Copper": "Copper",
    "Copper": "Copper", "Zinc": "Zinc", "Aluminum": "Aluminum", "Nickel": "Nickel", "Lead": "Lead",
    "Tin": "Tin", "Lean Hogs": "Lean hogs", "Live Cattle": "Live cattle", "Feeder Cattle": "Feeder cattle",
}

# DM Sans advance widths (thousandths of an em) for printable ASCII at
# weights 400 and 700, read from the font files, so labels are fitted to
# their boxes exactly. Other weights are interpolated.
LT_DM400 = (
    266, 250, 291, 804, 580, 786, 734, 159, 373, 373, 480, 550, 182, 541, 198, 392, 684, 312,
    576, 591, 607, 610, 628, 534, 608, 628, 202, 227, 550, 550, 550, 524, 1005, 664, 603, 717,
    688, 565, 535, 758, 681, 234, 501, 584, 527, 841, 691, 774, 580, 774, 594, 580, 561, 655,
    669, 968, 603, 580, 541, 314, 392, 314, 622, 660, 213, 544, 626, 572, 627, 568, 340, 558,
    575, 240, 243, 504, 223, 891, 574, 593, 626, 627, 370, 502, 392, 573, 527, 763, 496, 556,
    458, 427, 234, 427, 550
)
LT_DM700 = (
    235, 309, 367, 857, 604, 902, 781, 197, 405, 405, 513, 579, 246, 576, 252, 427, 704, 364,
    577, 603, 650, 622, 634, 537, 633, 635, 254, 278, 579, 579, 579, 538, 1046, 709, 638, 738,
    707, 583, 556, 778, 714, 272, 541, 653, 558, 886, 729, 784, 614, 784, 631, 604, 597, 685,
    706, 1018, 670, 635, 577, 377, 427, 377, 677, 725, 235, 586, 655, 607, 655, 602, 371, 596,
    618, 274, 274, 578, 267, 941, 617, 610, 655, 655, 409, 532, 433, 616, 565, 820, 571, 604,
    490, 470, 272, 470, 579
)


# ---------- small helpers ----------

def _lt_tw(text, size, weight=400):
    """Rendered DM Sans width in px (2% margin for kerning). Characters
    outside printable ASCII count 0.6 em."""
    t = (min(max(float(weight), 400.0), 700.0) - 400.0) / 300.0
    total = 0.0
    for ch in str(text):
        o = ord(ch)
        if 32 <= o <= 126:
            a, b = LT_DM400[o - 32], LT_DM700[o - 32]
            total += a + (b - a) * t
        else:
            total += 600.0
    return total * float(size) / 1000.0 * 1.02


def _lt_esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _lt_text(ann, x, y, text, anchor="left", size=13, color=TEXT_PRIMARY, weight=400):
    _cx_text(ann, x, y, _lt_esc(text), anchor=anchor, size=size, color=color, weight=weight)


def _lt_pct(v, digits=1):
    return f"{float(v):.{digits}f}%"


def _lt_contrast(a, b):
    def lum(h):
        def ch(v):
            v /= 255.0
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        r, g, bl = _cx_rgb(h)
        return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(bl)
    la, lb = sorted([lum(a), lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _lt_legible(color):
    """Keep the hue but lighten until white or dark text passes 4.5:1."""
    fill = color
    for i in range(20):
        fill = _cx_mix(color, "#FFFFFF", i / 20.0)
        if _lt_contrast(fill, "#FFFFFF") >= 4.5 or _lt_contrast(fill, ANALYTICS_CELL_TEXT) >= 4.5:
            return fill
    return fill


def _lt_rgba(color, alpha):
    r, g, b = _cx_rgb(color)
    return f"rgba({r},{g},{b},{alpha})"


def _lt_label(key):
    return LT_THEMES.get(key, (key, "#A9ADB7", "other"))[0]


def _lt_color(key):
    return LT_THEMES.get(key, (key, "#A9ADB7", "other"))[1]


def _lt_family(key):
    return LT_THEMES.get(key, (key, "#A9ADB7", "other"))[2]


def _lt_fund_color(ticker):
    return LT_CASH_COLOR if ticker == "CASH" else _corr_fund_color(ticker)


def _lt_fund_name(ticker):
    return "Cash" if ticker == "CASH" else _corr_fund_name(ticker)


def _lt_month(period):
    return pd.Period(period, freq="M").strftime("%B %Y")


def _lt_short_month(period):
    return pd.Period(period, freq="M").strftime("%b %Y")


def _lt_hover(fig, xs, ys, texts, sizes):
    """Invisible markers carrying hover text; sizes may differ per point."""
    if xs:
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers",
            marker=dict(size=[max(int(s), 4) for s in sizes], color="rgba(0,0,0,0)", symbol="square"),
            hovertext=texts, hovertemplate="%{hovertext}<extra></extra>", showlegend=False,
        ))


def _lt_spread(centers, heights, lo, hi, gap=2.0):
    """Nudge label centers apart so labels of the given heights never
    overlap, keeping them inside lo..hi where possible."""
    n = len(centers)
    if n == 0:
        return []
    pos = list(centers)
    for i in range(1, n):
        need = pos[i - 1] + (heights[i - 1] + heights[i]) / 2.0 + gap
        if pos[i] < need:
            pos[i] = need
    over = pos[-1] + heights[-1] / 2.0 - hi
    if over > 0:
        pos[-1] -= over
        for i in range(n - 2, -1, -1):
            need = pos[i + 1] - (heights[i + 1] + heights[i]) / 2.0 - gap
            if pos[i] > need:
                pos[i] = need
    under = lo - (pos[0] - heights[0] / 2.0)
    if under > 0:
        pos = [p + under for p in pos]
    return pos


def _lt_squarify(values, x, y, w, h):
    """Squarified treemap (Bruls, Huizing and van Wijk) of values sorted
    largest first. Returns [(x, y, w, h)] in the same order."""
    vals = [max(float(v), 0.0) for v in values]
    total = sum(vals)
    if total <= 0 or w <= 0 or h <= 0:
        return [(x, y, 0.0, 0.0) for _ in vals]
    sizes = [v * w * h / total for v in vals]

    def layout(row, x0, y0, dx, dy):
        covered = sum(row)
        out = []
        if dx >= dy:
            width = covered / dy if dy > 0 else 0.0
            for s in row:
                hh = s / width if width > 0 else 0.0
                out.append((x0, y0, width, hh))
                y0 += hh
        else:
            height = covered / dx if dx > 0 else 0.0
            for s in row:
                ww = s / height if height > 0 else 0.0
                out.append((x0, y0, ww, height))
                x0 += ww
        return out

    def leftover(row, x0, y0, dx, dy):
        covered = sum(row)
        if dx >= dy:
            width = covered / dy if dy > 0 else 0.0
            return x0 + width, y0, dx - width, dy
        height = covered / dx if dx > 0 else 0.0
        return x0, y0 + height, dx, dy - height

    def worst(row, x0, y0, dx, dy):
        ratios = []
        for (_x, _y, rw, rh) in layout(row, x0, y0, dx, dy):
            if rw <= 0 or rh <= 0:
                return float("inf")
            ratios.append(max(rw / rh, rh / rw))
        return max(ratios) if ratios else float("inf")

    out = []
    rest = sizes
    while rest:
        if len(rest) == 1:
            out += layout(rest, x, y, w, h)
            break
        i = 1
        while i < len(rest) and worst(rest[:i], x, y, w, h) >= worst(rest[:i + 1], x, y, w, h):
            i += 1
        row, rest = rest[:i], rest[i:]
        out += layout(row, x, y, w, h)
        x, y, w, h = leftover(row, x, y, w, h)
    return out


# ---------- data ----------

def _lt_snapshot_paths():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pipeline_dir = os.path.join(os.path.dirname(script_dir), "Portfolio Hist Val Reconstruction")
    paths = [os.path.join(script_dir, LT_SNAPSHOT_NAME), os.path.join(pipeline_dir, LT_SNAPSHOT_NAME)]
    home = os.path.expanduser("~")
    if home and home != "~":
        paths.append(os.path.join(home, *LT_DEPLOY_DIR_PARTS, LT_SNAPSHOT_NAME))
    return paths


@st.cache_data(ttl=3600, show_spinner=False)
def load_holdings_snapshot():
    """The newest readable holdings_snapshot.json: beside app.py (the cloud
    deploy), in the pipeline folder, or in the deploy working copy under the
    home folder (how the local app on the PC finds it). Returns a dict with
    funds, generated_at and path, or None."""
    best = None
    for path in _lt_snapshot_paths():
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except Exception:
            continue
        funds = data.get("funds") if isinstance(data, dict) else None
        if not isinstance(funds, dict) or not funds:
            continue
        stamp = str(data.get("generated_at", ""))
        if best is None or stamp > best["generated_at"]:
            best = {"funds": funds, "generated_at": stamp, "path": path}
    return best


def _lt_unbroken():
    return {"themes": {"not_broken": 100.0}, "top": [], "as_of": None, "source": "", "kind": "none"}


def _lt_snapshot_entry(snapshot, ticker):
    """One fund's entry from holdings_snapshot.json as a composition, or None
    when missing or malformed. Unknown theme keys fold into Not broken down."""
    if not snapshot:
        return None
    entry = snapshot["funds"].get(ticker)
    if not isinstance(entry, dict):
        return None
    themes = {}
    try:
        for k, v in (entry.get("themes") or {}).items():
            v = float(v)
            if v > 0:
                key = str(k) if str(k) in LT_THEMES else "not_broken"
                themes[key] = themes.get(key, 0.0) + v
        total = sum(themes.values())
        if not 95.0 <= total <= 105.0:
            return None
        scale = 100.0 / total
        top = []
        for item in entry.get("top") or []:
            name, _ticker, theme, w = item[0], item[1], item[2], float(item[3])
            if w > 0:
                top.append((str(name), str(theme) if str(theme) in LT_THEMES else "not_broken", w * scale))
    except (TypeError, ValueError, IndexError):
        return None
    return {"themes": {k: v * scale for k, v in themes.items()}, "top": top,
            "as_of": entry.get("as_of"), "source": str(entry.get("source", "")),
            "kind": str(entry.get("method", "live"))}


def _lt_from_qci(data):
    """HGER's composition from Harbor's QCI rows (the What HGER Holds feed)."""
    themes, names = {}, {}
    for r in (data or {}).get("rows") or []:
        try:
            w = float(r.get("weight") or 0.0)
        except (TypeError, ValueError):
            continue
        if w <= 0:
            continue
        theme = LT_QCI_THEME.get(str(r.get("sector", "")).strip(), "commod_other")
        themes[theme] = themes.get(theme, 0.0) + w
        commodity = str(r.get("commodity", "")).strip()
        name = LT_QCI_NAMES.get(commodity, commodity[:1].upper() + commodity[1:].lower() or "Other")
        cur = names.setdefault(name, [theme, 0.0])
        cur[1] += w
    total = sum(themes.values())
    if not 95.0 <= total <= 105.0:
        return None
    scale = 100.0 / total
    top = sorted(((n, th, w * scale) for n, (th, w) in names.items()), key=lambda x: -x[2])
    return {"themes": {k: v * scale for k, v in themes.items()}, "top": top}


def lt_hger_composition(snapshot, live_fetch=True):
    """HGER: the live Harbor fetch (cached six hours, shared with What HGER
    Holds), else the newer of the latest saved QCI snapshot and the holdings
    snapshot. What HGER Holds saves every successful fetch to qci_snapshots,
    so while that panel is on the page this is called with live_fetch=False
    and reads the panel's saved result; a Harbor outage is then waited out
    once per page instead of twice."""
    live = None
    if live_fetch:
        try:
            live = fetch_qci_weights()
        except Exception:
            live = None
    if live:
        comp = _lt_from_qci(live)
        if comp:
            comp.update(as_of=live.get("as_of"), source="Harbor", kind="live")
            return comp
    candidates = []
    saved = list_qci_snapshots()
    if saved:
        as_of, path = next(iter(saved.items()))
        comp = _lt_from_qci(load_qci_snapshot(path))
        if comp:
            comp.update(as_of=as_of, source="Harbor (saved snapshot)", kind="saved")
            candidates.append(comp)
    entry = _lt_snapshot_entry(snapshot, "HGER")
    if entry:
        candidates.append(entry)
    if not candidates:
        return None
    return max(candidates, key=lambda c: str(c.get("as_of") or ""))


def lt_compositions(tickers, snapshot, live_hger=True):
    """{ticker: composition} where a composition holds themes (percent of the
    fund), top [(name, theme, percent of the fund)], as_of, source and kind
    (live, saved, previous, hand-entered, fixed or none)."""
    comps = {}
    for t in tickers:
        if t in LT_FIXED:
            theme, name = LT_FIXED[t]
            comps[t] = {"themes": {theme: 100.0}, "top": [(name, theme, 100.0)],
                        "as_of": None, "source": "fixed", "kind": "fixed"}
        elif t == "HGER":
            comps[t] = lt_hger_composition(snapshot, live_hger) or _lt_unbroken()
        else:
            comps[t] = _lt_snapshot_entry(snapshot, t) or _lt_unbroken()
    return comps


def lt_exposure(weights, comps):
    """Look through a basket. weights: {ticker: percent of the portfolio}.
    Theme exposure is the sum over funds of fund weight times the theme's
    share of that fund; a single holding's exposure is fund weight times its
    weight in the fund, summed across funds. Single holdings come from each
    fund's stored top holdings."""
    flows, themes, singles = {}, {}, {}
    for t, w in weights.items():
        comp = comps.get(t) or _lt_unbroken()
        f = {}
        for th, share in comp["themes"].items():
            v = w * share / 100.0
            if v > 0:
                f[th] = f.get(th, 0.0) + v
                themes[th] = themes.get(th, 0.0) + v
        flows[t] = f
        for name, th, share in comp["top"]:
            v = w * share / 100.0
            s = singles.setdefault(name, {"pct": 0.0, "funds": [], "theme": th, "by_fund": {}})
            s["pct"] += v
            s["by_fund"][t] = s["by_fund"].get(t, 0.0) + v
            if t not in s["funds"]:
                s["funds"].append(t)
    single_list = sorted(((n, d["pct"], d["funds"], d["theme"], d["by_fund"]) for n, d in singles.items()),
                         key=lambda x: -x[1])
    return {"weights": dict(weights), "flows": flows, "themes": themes, "singles": single_list}


def _lt_normalize(weights):
    w = {t: float(v) for t, v in weights.items() if v is not None and float(v) > 0}
    total = sum(w.values())
    return {t: v * 100.0 / total for t, v in w.items()} if total > 0 else {}


def _lt_basket_weights(basket):
    """{ticker: percent} for a corr_going_in_baskets entry; money market and
    uninvested cash become CASH."""
    w = {t: v * 100.0 for t, v in basket["weights"].items() if v > 0}
    cash = (float(basket.get("tbill", 0.0)) - float(basket["weights"].get("BIL", 0.0))) * 100.0
    if cash >= LT_MIN_PCT:
        w["CASH"] = cash
    return _lt_normalize(w)


def _lt_next_weights(rows):
    w = {}
    for r in rows or []:
        t = str(r.get("ticker", "")).strip().upper()
        v = _sort_weight(r.get("weight"))
        if t and v > 0:
            w[t] = w.get(t, 0.0) + v
    return _lt_normalize(w)


def _lt_same_basket(a, b):
    if not a or not b:
        return False
    if {t for t, v in a.items() if v >= LT_HELD_PCT} != {t for t, v in b.items() if v >= LT_HELD_PCT}:
        return False
    return all(abs(a.get(t, 0.0) - b.get(t, 0.0)) < LT_SAME_BASKET_PTS for t in set(a) | set(b))


def lt_baskets(baskets, last_data_date, next_rows):
    """The baskets the section shows: {"current", "next", "prev"}, each None
    or a dict with period, weights ({ticker: percent}), date (the going-in
    close) and kind ("going-in" or "target").

    A basket whose month starts after the holdings data ends exists only
    when the data stops on a month's closed final session. If
    next_allocation.json matches it, the rebalance fills are in the data and
    it is Current. If next_allocation.json differs, the fills are not in the
    data yet: that "basket" is the closing month's holdings, drifted, so
    Current stays on the month that just closed and next_allocation.json is
    Next."""
    entries = [{"period": b["period"], "weights": _lt_basket_weights(b), "date": b["date"],
                "kind": "going-in"} for b in baskets or []]
    entries = [e for e in entries if e["weights"]]
    if not entries:
        return None
    last_month = pd.Timestamp(last_data_date).to_period("M")
    settled = [e for e in entries if e["period"] <= last_month]
    pending = [e for e in entries if e["period"] > last_month]
    nxt_w = _lt_next_weights(next_rows)
    cur = settled[-1] if settled else pending[-1]
    prev = settled[-2] if len(settled) > 1 else None
    if pending and cur is not pending[-1]:
        if not nxt_w or _lt_same_basket(pending[-1]["weights"], nxt_w):
            prev, cur = cur, pending[-1]
    nxt = None
    if nxt_w and not _lt_same_basket(cur["weights"], nxt_w):
        nxt = {"period": cur["period"] + 1, "weights": nxt_w, "date": None, "kind": "target"}
    return {"current": cur, "next": nxt, "prev": prev}


def lt_risk(returns, weights, window):
    """Risk share of each fund over the last `window` sessions:
    rc_i = w_i (S w)_i / (w' S w), S the annualized (x252) covariance of daily
    returns. Also the annualized volatility and independent bets (the
    diversification ratio squared). Cash counts as a fund that never moves;
    a fund with no price history is left out and named in "missing"."""
    if returns is None or returns.empty or not weights:
        return None
    order = canonical_order([t for t in weights if t != "CASH"])
    funds = [t for t in order if t in returns.columns and weights[t] > 0]
    missing = [t for t in order if t not in funds and weights[t] >= LT_HELD_PCT]
    if not funds:
        return None
    block = returns[funds].dropna().tail(int(window))
    if len(block) < max(20, int(window) // 3):
        return None
    cols = list(funds)
    if weights.get("CASH", 0.0) > 0:
        block = block.copy()
        block["CASH"] = 0.0
        cols.append("CASH")
    w = np.array([weights[t] for t in cols], dtype=float)
    w = w / w.sum()
    cov = block[cols].cov().values * 252.0
    if not np.all(np.isfinite(cov)):
        return None
    port_var = float(w @ cov @ w)
    if not np.isfinite(port_var) or port_var <= 0:
        return None
    rc = w * (cov @ w) / port_var
    vol = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    return {"funds": cols, "w": w * 100.0, "rc": rc * 100.0, "vol": vol * 100.0,
            "port_vol": float(np.sqrt(port_var) * 100.0), "bets": float((w @ vol) ** 2 / port_var),
            "start": block.index[0], "end": block.index[-1], "n": int(len(block)), "missing": missing}


# ---------- tiles ----------

def _lt_tile_fit(candidates, lines=2):
    """The first candidate that wraps to `lines` lines in a four-across tile
    (the same wrapping _cx_tiles uses)."""
    tile_w = (ANALYTICS_WIDTH - 36) / 4.0
    for text in candidates:
        if len(_cx_wrap(text, 12, tile_w - 30)) <= lines:
            return text
    return candidates[-1]


def _lt_chip_leaders(exp):
    names = [n for n, v, _f, th, _b in exp["singles"] if th == "semis" and v >= LT_MIN_PCT][:4]
    names = [LT_ALT_LABELS.get(n, (n,))[-1] if n in ("Samsung Electronics",) else n for n in names]
    if not names:
        return "Chip designers, makers and equipment"
    cands = [_cap_join(names[:k]) + (" lead" if k > 1 else " leads") for k in range(len(names), 0, -1)]
    return _lt_tile_fit(cands)


def _lt_commod_note(exp, comps):
    w = exp["weights"]
    if w.get("HGER", 0.0) >= LT_MIN_PCT and "HGER" in comps:
        shares = {k: v for k, v in comps["HGER"]["themes"].items() if _lt_family(k) == "commod"}
        if shares:
            k = max(shares, key=shares.get)
            phrase = {"oil": "Oil and fuels are", "gold": "Gold is", "agri": "Crops are",
                      "livestock": "Livestock is", "ind_metals": "Industrial metals are"}.get(
                k, f"{_lt_label(k)} is")
            return f"{phrase} {shares[k]:.0f}% of HGER"
    if w.get("GLD", 0.0) >= LT_MIN_PCT:
        return "All gold, through GLD"
    return "None in this basket"


def _lt_bitcoin_note(exp):
    held = [t for t in ("IBIT", "GBTC", "BITO") if exp["weights"].get(t, 0.0) >= LT_MIN_PCT]
    return f"All of {_cap_join(held)}" if held else "None in this basket"


def _lt_family_total(themes, family):
    return sum(v for k, v in themes.items() if _lt_family(k) == family)


def lt_flow_tiles(exp, comps):
    th = exp["themes"]
    chips = th.get("semis", 0.0)
    tech = chips + th.get("other_tech", 0.0) + th.get("internet", 0.0)
    com = _lt_family_total(th, "commod")
    btc = th.get("bitcoin", 0.0)
    unbroken = [t for t in canonical_order(list(exp["weights"]))
                if comps.get(t, {}).get("kind") == "none" and exp["weights"][t] >= LT_MIN_PCT]
    gap = _lt_tile_fit([f"{_cap_join(unbroken)} not broken down", "Some funds not broken down"]) if unbroken else ""
    # With a stock fund not broken down, a zero reading means unknown, not none.
    chips_val = "n/a" if chips < LT_MIN_PCT and gap else _lt_pct(chips)
    tech_val = "n/a" if tech < LT_MIN_PCT and gap else _lt_pct(tech)
    return [
        ("Chips", chips_val, _lt_chip_leaders(exp) if chips >= LT_MIN_PCT else (gap or "None in this basket")),
        ("All technology", tech_val, "Chips, software and internet" if tech >= LT_MIN_PCT or not gap else gap),
        ("Commodities", _lt_pct(com), _lt_commod_note(exp, comps)),
        ("Bitcoin", _lt_pct(btc), _lt_bitcoin_note(exp)),
    ]


def lt_table_tiles(exp, cmp_exp, cmp_period):
    th = exp["themes"]
    items = [("Stocks", _lt_family_total(th, "stocks"), lambda t: _lt_family_total(t, "stocks")),
             ("Chips", th.get("semis", 0.0), lambda t: t.get("semis", 0.0)),
             ("Commodities", _lt_family_total(th, "commod"), lambda t: _lt_family_total(t, "commod")),
             ("Bitcoin", th.get("bitcoin", 0.0), lambda t: t.get("bitcoin", 0.0))]
    tiles = []
    for i, (label, value, of) in enumerate(items):
        if cmp_exp is None:
            sub = "No earlier basket to compare"
        else:
            before = of(cmp_exp["themes"])
            when = f" in {pd.Period(cmp_period, freq='M').strftime('%B')}" if i == 0 else ""
            if abs(value - before) < LT_MIN_PCT:
                sub = f"Unchanged from {_lt_pct(before)}{when}"
            else:
                sub = f"{'Up' if value > before else 'Down'} from {_lt_pct(before)}{when}"
        tiles.append((label, _lt_pct(value), sub))
    return tiles


# ---------- Option A: Flow ----------

def build_lt_flow_figure(exp, comps, tiles):
    """Funds on the left flowing into themes on the right, ribbon width
    proportional to share of the portfolio. Pixel figure, 780 px wide."""
    W = ANALYTICS_WIDTH
    shapes, ann = [], []
    hx, hy, ht, hs = [], [], [], []
    tile_h = _cx_tiles(shapes, ann, tiles, 0)
    top = tile_h + 30.0
    Hp = 440.0
    nw = 14.0
    xL, xR = 118.0, 556.0
    gR = 8.0
    wts = exp["weights"]
    flows = exp["flows"]
    funds = [t for t in canonical_order([t for t in wts if t != "CASH"]) if wts[t] >= LT_MIN_PCT]
    if wts.get("CASH", 0.0) >= LT_MIN_PCT:
        funds.append("CASH")
    # "Not broken down" sits just below the stock nodes: the funds that land
    # there (DXJ, EZU, BTAL, COPX) are mostly stock funds, so their ribbons
    # cross the fewest others.
    groups = [("semis", ["semis"]), ("other_tech", ["other_tech"]), ("internet", ["internet"]),
              ("other_stocks", LT_OTHER_STOCKS), ("not_broken", ["not_broken"]), ("oil", ["oil"]),
              ("gold", ["gold"]), ("agri", ["agri"]), ("livestock", ["livestock"]),
              ("ind_metals", ["ind_metals"]), ("commod_other", ["commod_other"]), ("bitcoin", ["bitcoin"]),
              ("cash", ["cash"])]
    rv = {k: sum(exp["themes"].get(x, 0.0) for x in ks) for k, ks in groups}
    right = [(k, ks) for k, ks in groups if rv[k] >= LT_MIN_PCT]
    total = sum(rv[k] for k, _ in right) or 100.0
    s = (Hp - gR * max(len(right) - 1, 0)) / total
    left_total = sum(wts[f] for f in funds) or 100.0
    sL = s * total / left_total
    gL = (Hp - left_total * sL) / (len(funds) - 1) if len(funds) > 1 else 0.0

    ly, y = {}, top
    for f in funds:
        h = wts[f] * sL
        ly[f] = (y, y + h)
        y += h + gL
    ry, y = {}, top
    for k, _ks in right:
        h = rv[k] * s
        ry[k] = (y, y + h)
        y += h + gR

    links = []
    for f in funds:
        for k, ks in right:
            v = sum(flows.get(f, {}).get(x, 0.0) for x in ks)
            if v > 0.02:
                links.append((f, k, v))
    tgt = {}
    for k, _ks in right:
        yy = ry[k][0]
        for f in funds:
            for ff, kk, v in links:
                if ff == f and kk == k:
                    tgt[(f, k)] = yy
                    yy += v * s
    x0, x1 = xL + nw, xR
    xm = (x0 + x1) / 2.0
    for f in funds:
        yy = ly[f][0]
        for k, _ks in right:
            for ff, kk, v in links:
                if ff != f or kk != k:
                    continue
                h_src, h_tgt = v * sL, v * s
                t0 = tgt[(f, k)]
                path = (f"M {x0:.1f},{yy:.1f} C {xm:.1f},{yy:.1f} {xm:.1f},{t0:.1f} {x1:.1f},{t0:.1f} "
                        f"L {x1:.1f},{t0 + h_tgt:.1f} C {xm:.1f},{t0 + h_tgt:.1f} {xm:.1f},{yy + h_src:.1f} "
                        f"{x0:.1f},{yy + h_src:.1f} Z")
                shapes.append(dict(type="path", path=path, fillcolor=_lt_rgba(_lt_fund_color(f), 0.30),
                                   line=dict(width=0), layer="below"))
                hx.append(xm)
                hy.append((yy + h_src / 2.0 + t0 + h_tgt / 2.0) / 2.0)
                ht.append(f"<b>{f} into {_lt_esc(_lt_flow_name(k))}</b><br>{_lt_pct(v)} of the portfolio")
                hs.append(max(min(h_src, h_tgt), 6))
                yy += h_src

    # Left nodes and labels
    centers = [(ly[f][0] + ly[f][1]) / 2.0 for f in funds]
    pos = _lt_spread(centers, [34.0] * len(funds), top - 6, top + Hp + 6)
    for f, cy in zip(funds, pos):
        y0, y1 = ly[f]
        _cx_rect(shapes, xL, y0, xL + nw, max(y1, y0 + 1.5), _lt_fund_color(f), r=3)
        _lt_text(ann, xL - 12, cy - 8, f if f != "CASH" else "Cash", anchor="right", size=15,
                 color=TEXT_PRIMARY, weight=700)
        _lt_text(ann, xL - 12, cy + 9, _lt_pct(wts[f]), anchor="right", size=13, color=TEXT_SECONDARY)
        hx.append(xL + nw / 2.0)
        hy.append((y0 + y1) / 2.0)
        ht.append(f"<b>{f}</b> ({_lt_esc(_lt_fund_name(f))})<br>{_lt_pct(wts[f])} of the basket")
        hs.append(max(y1 - y0, 8))

    # Right nodes and labels
    single = [k for k, _ks in right if k not in ("other_stocks", "not_broken", "cash")]
    largest = max(single, key=lambda k: rv[k]) if single else None
    heights = [34.0 if k == "other_stocks" else 18.0 for k, _ in right]
    centers = [(ry[k][0] + ry[k][1]) / 2.0 for k, _ in right]
    pos = _lt_spread(centers, heights, top - 4, top + Hp + 4)
    xt = xR + nw + 10
    for (k, ks), cy, hgt in zip(right, pos, heights):
        y0, y1 = ry[k]
        color = "#C6D4E6" if k == "other_stocks" else _lt_color(k)
        _cx_rect(shapes, xR, y0, xR + nw, max(y1, y0 + 1.5), color, r=3,
                 line_color=LT_GOLD_EDGE if k == "gold" else None, line_width=1 if k == "gold" else 0)
        label = _lt_flow_name(k)
        ly_main = cy - 8 if k == "other_stocks" else cy
        _lt_text(ann, xt, ly_main, label, size=13.5, color=TEXT_PRIMARY, weight=600)
        _lt_text(ann, W, ly_main, _lt_pct(rv[k]), anchor="right", size=13.5, color=TEXT_SECONDARY, weight=500)
        if k == "other_stocks":
            _lt_text(ann, xt, cy + 9, _lt_other_stocks_note(exp, W - xt), size=11.5, color=TEXT_MUTED)
        if k == largest and len(right) > 1:
            lx = xt + _lt_tw(label, 13.5, 600) + 8
            if lx + 58 <= W - _lt_tw(_lt_pct(rv[k]), 13.5, 500) - 8:
                _cx_rect(shapes, lx, ly_main - 8.5, lx + 58, ly_main + 8.5, ANALYTICS_TINT, r=8.5)
                _lt_text(ann, lx + 29, ly_main, "Largest", anchor="center", size=11, color=BRAND_PURPLE,
                         weight=600)
        parts = []
        for f in funds:
            v = sum(flows.get(f, {}).get(x, 0.0) for x in ks)
            if v > 0.02:
                parts.append(f"{f} {v:.1f}")
        detail = ""
        if k == "other_stocks":
            detail = "<br>" + "<br>".join(f"{_lt_esc(_lt_label(x))} {exp['themes'].get(x, 0.0):.1f}%"
                                          for x in ks if exp["themes"].get(x, 0.0) >= LT_MIN_PCT)
        hx.append(xR + nw / 2.0)
        hy.append((y0 + y1) / 2.0)
        ht.append(f"<b>{_lt_esc(label)}</b> {_lt_pct(rv[k])} of the portfolio<br>"
                  + ", ".join(parts) + detail)
        hs.append(max(y1 - y0, 8))
    H = int(top + Hp + 16)
    fig = go.Figure()
    _lt_hover(fig, hx, hy, ht, hs)
    return _pixel_layout(fig, W, H, shapes, ann)


def _lt_flow_name(key):
    return "Other stock sectors" if key == "other_stocks" else _lt_label(key)


def _lt_other_stocks_note(exp, max_w):
    """'Consumer, financials and more': the two largest sectors in the group,
    or one, whichever fits max_w at 11.5 px."""
    parts = sorted(((exp["themes"].get(k, 0.0), k) for k in LT_OTHER_STOCKS), reverse=True)
    names = [LT_SHORT[k] for v, k in parts if v >= LT_MIN_PCT][:2]
    if not names:
        return ""
    cands = []
    if len(names) == 2:
        cands.append(f"{names[0]}, {names[1]} and more")
    cands.append(f"{names[0]} and more")
    for text in cands:
        text = text[:1].upper() + text[1:]
        if _lt_tw(text, 11.5) <= max_w:
            return text
    return ""


# ---------- Option B: Table ----------

def build_lt_table_figure(exp, cmp_exp, cmp_period, tiles):
    """Each theme's share of the portfolio with what every fund contributes,
    its bar, and the change from the comparison basket; then the largest
    single holdings across funds. Pixel figure, 780 px wide."""
    W = ANALYTICS_WIDTH
    shapes, ann = [], []
    hx, hy, ht, hs = [], [], [], []
    tile_h = _cx_tiles(shapes, ann, tiles, 0)
    y = tile_h + 22.0
    wts = exp["weights"]
    flows = exp["flows"]
    funds = [t for t in canonical_order([t for t in wts if t != "CASH"]) if wts[t] >= LT_MIN_PCT]
    if wts.get("CASH", 0.0) >= LT_MIN_PCT:
        funds.append("CASH")
    X_FUNDS, X_FUNDS_END = 214.0, 548.0
    cw = min(78.0, (X_FUNDS_END - X_FUNDS) / max(len(funds), 1))
    cx = {f: X_FUNDS + cw / 2.0 + i * cw for i, f in enumerate(funds)}
    xv, xb0, xb1, xd = 586.0, 598.0, 690.0, 774.0
    hdr, rh, gh = 54.0, 28.0, 32.0
    th = exp["themes"]
    tp = cmp_exp["themes"] if cmp_exp is not None else {}
    vs_label = f"vs {pd.Period(cmp_period, freq='M').strftime('%b')}" if cmp_exp is not None else ""

    groups = []
    for fam, fam_label in LT_FAMILIES:
        keys = [k for k, (_l, _c, f) in LT_THEMES.items() if f == fam
                and max(th.get(k, 0.0), tp.get(k, 0.0)) >= LT_MIN_PCT]
        if keys:
            groups.append((fam_label, keys))

    y0 = y
    _cx_rect(shapes, 0, y0, W, y0 + hdr, ANALYTICS_HEADER_BG)
    _cx_line(shapes, 0, y0 + hdr, W, y0 + hdr, BRAND_PURPLE, 2)
    _lt_text(ann, 12, y0 + hdr / 2.0, "Exposure", size=13.5, color=TEXT_PRIMARY, weight=700)
    for f in funds:
        _lt_text(ann, cx[f], y0 + 19, "Cash" if f == "CASH" else f, anchor="center", size=14,
                 color=TEXT_PRIMARY, weight=700)
        _lt_text(ann, cx[f], y0 + 37, _lt_pct(wts[f]), anchor="center", size=12, color=TEXT_MUTED)
    _lt_text(ann, xv, y0 + hdr / 2.0, "Portfolio", anchor="right", size=13.5, color=TEXT_PRIMARY, weight=700)
    if vs_label:
        _lt_text(ann, xd, y0 + hdr / 2.0, vs_label, anchor="right", size=13.5, color=TEXT_PRIMARY, weight=700)
    maxc = max([v for f in funds for v in flows.get(f, {}).values()] or [1.0])
    maxp = max(th.values()) if th else 1.0
    y = y0 + hdr

    def change(yc, d, big_cut=3.0, group=False):
        if cmp_exp is None:
            return
        if abs(d) >= LT_MIN_PCT:
            big = group or abs(d) >= big_cut
            amount = f"{abs(d):.1f}"
            weight = 700 if big else 400
            color = TEXT_PRIMARY if group else (ANALYTICS_CELL_TEXT if big else TEXT_SECONDARY)
            _lt_text(ann, xd, yc, amount, anchor="right", size=13, color=color, weight=weight)
            _cx_triangle(shapes, xd - _lt_tw(amount, 13, weight) - 8, yc, d > 0, 4.2, color)
        else:
            _lt_text(ann, xd, yc, "0.0", anchor="right", size=13, color=TEXT_MUTED)

    for gname, keys in groups:
        gt = sum(th.get(k, 0.0) for k in keys)
        gp = sum(tp.get(k, 0.0) for k in keys)
        _cx_line(shapes, 0, y, W, y, ANALYTICS_RULE, 1)
        yc = y + gh / 2.0 + 1
        _lt_text(ann, 12, yc, gname, size=13.5, color=TEXT_PRIMARY, weight=700)
        _lt_text(ann, xv, yc, _lt_pct(gt), anchor="right", size=13.5, color=TEXT_PRIMARY, weight=700)
        change(yc, gt - gp, group=True)
        y += gh
        for k in keys:
            yc = y + rh / 2.0
            _cx_rect(shapes, 14, yc - 5, 24, yc + 5, _lt_color(k), r=2,
                     line_color=LT_GOLD_EDGE if k == "gold" else None, line_width=1 if k == "gold" else 0)
            _lt_text(ann, 32, yc, _lt_label(k), size=13, color=ANALYTICS_CELL_TEXT)
            for f in funds:
                v = flows.get(f, {}).get(k, 0.0)
                if v >= LT_MIN_PCT:
                    t = min(1.0, v / maxc)
                    _cx_rect(shapes, cx[f] - cw / 2.0 + 6, y + 3, cx[f] + cw / 2.0 - 6, y + rh - 3,
                             _cx_mix("#FFFFFF", LT_SHADE, 0.15 + 0.85 * t), r=5)
                    _lt_text(ann, cx[f], yc, f"{v:.1f}", anchor="center", size=13,
                             color=ANALYTICS_CELL_TEXT, weight=500)
                    hx.append(cx[f])
                    hy.append(yc)
                    ht.append(f"<b>{_lt_esc(_lt_label(k))}</b> through {f}<br>{_lt_pct(v)} of the portfolio")
                    hs.append(min(cw - 12, rh - 6))
            pv = th.get(k, 0.0)
            _lt_text(ann, xv, yc, _lt_pct(pv), anchor="right", size=13, color=ANALYTICS_CELL_TEXT, weight=600)
            shapes.append(dict(type="path", path=_rounded_bar_path(xb0, xb1, yc, 10), fillcolor=LT_TRACK,
                               line=dict(width=0), layer="below"))
            if pv >= LT_MIN_PCT:
                shapes.append(dict(type="path",
                                   path=_rounded_bar_path(xb0, xb0 + max(10.0, (xb1 - xb0) * pv / maxp), yc, 10),
                                   fillcolor=LT_BAR, line=dict(width=0), layer="below"))
            change(yc, pv - tp.get(k, 0.0))
            y += rh
    _cx_rect(shapes, 0, y, W, y + 36, ANALYTICS_HEADER_BG)
    _cx_line(shapes, 0, y, W, y, TEXT_PRIMARY, 1)
    yc = y + 18
    _lt_text(ann, 12, yc, "Total", size=13.5, color=TEXT_PRIMARY, weight=700)
    for f in funds:
        _lt_text(ann, cx[f], yc, f"{wts[f]:.1f}", anchor="center", size=13.5, color=TEXT_PRIMARY, weight=700)
    _lt_text(ann, xv, yc, _lt_pct(sum(th.values())), anchor="right", size=13.5, color=TEXT_PRIMARY, weight=700)
    y += 36

    # Largest single holdings across funds
    singles = [s for s in exp["singles"] if s[1] >= LT_MIN_PCT][:10]
    if singles:
        y += 30
        _lt_text(ann, 0, y, "Largest single holdings across funds", size=14, color=TEXT_PRIMARY, weight=700)
        y += 22
        col_w = (W - 30) / 2.0
        per_col = (len(singles) + 1) // 2
        for i, (name, v, funds_of, theme, by_fund) in enumerate(singles):
            c, r = divmod(i, per_col)
            x0 = c * (col_w + 30)
            yc = y + r * 26 + 13
            if r > 0:
                _cx_line(shapes, x0, yc - 13, x0 + col_w, yc - 13, ANALYTICS_RULE, 1)
            _lt_text(ann, x0 + 2, yc, str(i + 1), size=12, color=TEXT_MUTED)
            _cx_rect(shapes, x0 + 24, yc - 4.5, x0 + 33, yc + 4.5, _lt_color(theme), r=2,
                     line_color=LT_GOLD_EDGE if theme == "gold" else None,
                     line_width=1 if theme == "gold" else 0)
            _lt_text(ann, x0 + 41, yc, name, size=13, color=ANALYTICS_CELL_TEXT, weight=600)
            via = "via " + _cap_join(["Cash" if f == "CASH" else f for f in funds_of])
            _lt_text(ann, x0 + 47 + _lt_tw(name, 13, 600), yc, via, size=12, color=TEXT_MUTED)
            _lt_text(ann, x0 + col_w, yc, _lt_pct(v), anchor="right", size=13, color=ANALYTICS_CELL_TEXT,
                     weight=600)
            hx.append(x0 + col_w / 2.0)
            hy.append(yc)
            ht.append(f"<b>{_lt_esc(name)}</b> ({_lt_esc(_lt_label(theme))})<br>{_lt_pct(v)} of the portfolio: "
                      + ", ".join(f"{f} {b:.2f}" for f, b in by_fund.items()))
            hs.append(20)
        y += per_col * 26
    H = int(y + 6)
    fig = go.Figure()
    _lt_hover(fig, hx, hy, ht, hs)
    return _pixel_layout(fig, W, H, shapes, ann)


# ---------- Option C: Map ----------

def _lt_wrap2(label):
    words = label.split(" ")
    if len(words) < 2:
        return [label]
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        m = max(len(a), len(b))
        if best is None or m < best[0]:
            best = (m, [a, b])
    return best[1]


def _lt_label_plan(w, h, name, val, size=12, bold=600):
    """The first label layout that fits a w x h box, as (layout, label), or
    None. Tries the full name with its value, then shorter names
    (LT_ALT_LABELS) with the value, then names alone at 11 and 10 px."""
    pad = 7
    names = (name,) + LT_ALT_LABELS.get(name, ()) + (("Other",) if name.startswith("Other ") else ())
    vw = _lt_tw(val, size)
    for nm in names:
        nw_ = _lt_tw(nm, size, bold)
        if w >= max(nw_, vw) + 2 * pad and h >= 36:
            return ("stack", nm)
        lines = _lt_wrap2(nm)
        if (len(lines) == 2 and h >= 50 and w >= vw + 2 * pad
                and w >= max(_lt_tw(t, size, bold) for t in lines) + 2 * pad):
            return ("wrap", nm)
        if w >= _lt_tw(f"{nm} {val}", 11, bold) + 2 * pad and h >= 20:
            return ("inline", nm)
        if w >= max(_lt_tw(nm, 11, bold), _lt_tw(val, 11)) + 10 and h >= 30:
            return ("small", nm)
    for nm in names:
        if w >= _lt_tw(nm, 11, bold) + 10 and h >= 16:
            return ("name11", nm)
        if w >= _lt_tw(nm, 10, bold) + 6 and h >= 14:
            return ("name10", nm)
    return None


def _lt_box_label(ann, x, y, w, h, name, val, fill, size=12, bold=600):
    """Draw the label _lt_label_plan picks; returns False when none fits."""
    plan = _lt_label_plan(w, h, name, val, size, bold)
    if plan is None:
        return False
    layout, nm = plan
    tc = _cx_text_on(fill)
    pad = 7
    if layout == "stack":
        _lt_text(ann, x + pad, y + 13, nm, size=size, color=tc, weight=bold)
        _lt_text(ann, x + pad, y + 28, val, size=size, color=tc)
    elif layout == "wrap":
        a, b = _lt_wrap2(nm)
        _lt_text(ann, x + pad, y + 13, a, size=size, color=tc, weight=bold)
        _lt_text(ann, x + pad, y + 27, b, size=size, color=tc, weight=bold)
        _lt_text(ann, x + pad, y + 42, val, size=size, color=tc)
    elif layout == "inline":
        _lt_text(ann, x + pad, y + h / 2.0, f"{nm} {val}", size=11, color=tc, weight=bold)
    elif layout == "small":
        _lt_text(ann, x + 5, y + 11, nm, size=11, color=tc, weight=bold)
        _lt_text(ann, x + 5, y + 24, val, size=11, color=tc)
    elif layout == "name11":
        _lt_text(ann, x + 5, y + h / 2.0, nm, size=11, color=tc, weight=bold)
    else:
        _lt_text(ann, x + 3, y + h / 2.0, nm, size=10, color=tc, weight=bold)
    return True


def _lt_layout_leaves(leaves, x, y, w, h, key=""):
    """Squarify a theme's leaves, folding any named holding whose box is too
    small to label into its fund's remainder, so every named box carries its
    name. Returns [(leaf, rect)]."""
    leaves = list(leaves)
    for _ in range(12):
        rects = _lt_squarify([lf[1] for lf in leaves], x, y, w, h)
        bad = [i for i, (lf, r) in enumerate(zip(leaves, rects))
               if not lf[2] and _lt_label_plan(r[2], r[3], lf[0], _lt_pct(lf[1])) is None]
        if not bad:
            return list(zip(leaves, rects))
        i = min(bad, key=lambda j: leaves[j][1])
        name, v, _rest, funds = leaves.pop(i)
        f = funds[0]
        for j, lf in enumerate(leaves):
            if lf[2] and lf[3] == [f]:
                leaves[j] = (lf[0], lf[1] + v, True, lf[3])
                break
        else:
            leaves.append((LT_RESIDUAL_LABEL.get(f, f"Other {LT_SHORT.get(key, 'holdings')}"), v, True, [f]))
        named = sorted([lf for lf in leaves if not lf[2]], key=lambda lf: -lf[1])
        rest = sorted([lf for lf in leaves if lf[2]], key=lambda lf: -lf[1])
        leaves = named + rest
    return list(zip(leaves, _lt_squarify([lf[1] for lf in leaves], x, y, w, h)))


def _lt_map_leaves(exp, key):
    """A theme's leaves: named holdings at LT_MAP_NAME_PCT of the portfolio or
    more, then what each fund holds beyond them. (name, pct, is_rest, funds)."""
    named, rest = [], []
    for f, wt in exp["weights"].items():
        c = exp["flows"].get(f, {}).get(key, 0.0)
        if c <= 0:
            continue
        got = 0.0
        for name, v, _funds, theme, by_fund in exp["singles"]:
            if theme != key or f not in by_fund:
                continue
            part = by_fund[f]
            if part >= LT_MAP_NAME_PCT:
                named.append((name, part, False, [f]))
                got += part
        left = c - got
        if left > 0.12:
            if key == "not_broken":
                label = "Cash" if f == "CASH" else f
            elif key == "cash":
                label = "T-bills" if f == "BIL" else "Cash"
            else:
                label = LT_RESIDUAL_LABEL.get(f, f"Other {LT_SHORT.get(key, 'holdings')}")
            rest.append((label, left, True, [f]))
    merged = {}
    for name, v, is_rest, funds in named:
        cur = merged.setdefault(name, [0.0, []])
        cur[0] += v
        cur[1] += funds
    named = [(n, v, False, fs) for n, (v, fs) in merged.items()]
    named.sort(key=lambda x: -x[1])
    rest.sort(key=lambda x: -x[1])
    return named + rest


def build_lt_map_figure(exp):
    """Treemap of themes sized by share of the portfolio, grouped into
    stocks, commodities and crypto side by side, with each theme's largest
    holdings inside it; the largest single positions follow underneath.
    Pixel figure, 780 px wide."""
    W = ANALYTICS_WIDTH
    shapes, ann = [], []
    hx, hy, ht, hs = [], [], [], []
    th = exp["themes"]
    H_MAP = 540.0
    gapF, gapT = 6.0, 4.0
    fams = []
    for fam, _label in LT_FAMILIES:
        keys = [k for k in LT_THEMES if _lt_family(k) == fam and th.get(k, 0.0) >= LT_MIN_PCT]
        if keys:
            fams.append((fam, keys, sum(th[k] for k in keys)))
    avail = W - gapF * max(len(fams) - 1, 0)
    grand = sum(v for _f, _k, v in fams) or 1.0
    x = 0.0
    for fam, keys, ftot in fams:
        fw = avail * ftot / grand
        keys = sorted(keys, key=lambda k: -th[k])
        rects = _lt_squarify([th[k] for k in keys], x, 0.0, fw, H_MAP)
        for k, (rx, ry, rw, rhh) in zip(keys, rects):
            bx, by, bw, bh = rx + gapT / 2.0, ry + gapT / 2.0, rw - gapT, rhh - gapT
            if bw <= 0.5 or bh <= 0.5:
                continue
            col, lab, tv = _lt_color(k), _lt_label(k), th[k]
            leaves = _lt_map_leaves(exp, k)
            header_ok = (_lt_tw(lab, 12.5, 700) + _lt_tw(_lt_pct(tv), 12.5) + 20 <= bw
                         and bh >= 70 and len(leaves) > 1)
            placed = []
            if header_ok:
                placed = _lt_layout_leaves(leaves, bx + 2, by + 23, bw - 4, bh - 25, k)
                labelled = [lf for lf, (qx, qy, qw, qh) in placed
                            if _lt_label_plan(qw, qh, lf[0], _lt_pct(lf[1])) is not None]
                header_ok = len(placed) > 1 and bool(labelled)
            if header_ok:
                _cx_rect(shapes, bx, by, bx + bw, by + bh, col, r=4)
                tc = _cx_text_on(col)
                _lt_text(ann, bx + 8, by + 12, lab, size=12.5, color=tc, weight=700)
                _lt_text(ann, bx + 8 + _lt_tw(lab, 12.5, 700) + 6, by + 12, _lt_pct(tv), size=12.5, color=tc)
                for (name, v, is_rest, funds), (qx, qy, qw, qh) in placed:
                    if qw <= 0.5 or qh <= 0.5:
                        continue
                    fill = _lt_legible(_cx_mix(col, "#FFFFFF", 0.28) if is_rest else col)
                    _cx_rect(shapes, qx, qy, qx + qw, qy + qh, fill, r=3, line_color="#FFFFFF", line_width=1.5)
                    _lt_box_label(ann, qx, qy, qw, qh, name, _lt_pct(v), fill)
                    hx.append(qx + qw / 2.0)
                    hy.append(qy + qh / 2.0)
                    ht.append(f"<b>{_lt_esc(name)}</b> ({_lt_esc(lab)})<br>{_lt_pct(v, 2)} of the portfolio, "
                              f"through {_cap_join(['Cash' if f == 'CASH' else f for f in funds])}")
                    hs.append(max(min(qw, qh) - 4, 6))
            else:
                fill = _lt_legible(col)
                _cx_rect(shapes, bx, by, bx + bw, by + bh, fill, r=4,
                         line_color=LT_GOLD_EDGE if k == "gold" else None, line_width=1 if k == "gold" else 0)
                _lt_box_label(ann, bx, by, bw, bh, lab, _lt_pct(tv), fill, 12.5, 700)
                contrib = [f"{('Cash' if f == 'CASH' else f)} {exp['flows'].get(f, {}).get(k, 0.0):.1f}"
                           for f in exp["weights"] if exp["flows"].get(f, {}).get(k, 0.0) > 0.02]
                hx.append(bx + bw / 2.0)
                hy.append(by + bh / 2.0)
                ht.append(f"<b>{_lt_esc(lab)}</b> {_lt_pct(tv)} of the portfolio<br>" + ", ".join(contrib))
                hs.append(max(min(bw, bh) - 4, 6))
        x += fw + gapF

    # Largest single positions
    y = H_MAP + 30.0
    singles = [s for s in exp["singles"] if s[1] >= LT_MIN_PCT][:10]
    if singles:
        _lt_text(ann, 0, y, "Largest single positions", size=14, color=TEXT_PRIMARY, weight=700)
        y += 20.0
        cx0, row_h, chip_h = 0.0, 38.0, 28.0
        rows = 0
        for i, (name, v, funds, theme, by_fund) in enumerate(singles):
            rank, val = str(i + 1), _lt_pct(v)
            wchip = 11 + _lt_tw(rank, 12) + 6 + _lt_tw(name, 13, 600) + 6 + _lt_tw(val, 13) + 11
            if cx0 > 0 and cx0 + wchip > W:
                cx0 = 0.0
                rows += 1
            yy = y + rows * row_h
            _cx_rect(shapes, cx0, yy, cx0 + wchip, yy + chip_h, ANALYTICS_HEADER_BG, r=14,
                     line_color=ANALYTICS_RULE, line_width=1)
            tx = cx0 + 11
            _lt_text(ann, tx, yy + chip_h / 2.0, rank, size=12, color=TEXT_MUTED)
            tx += _lt_tw(rank, 12) + 6
            _lt_text(ann, tx, yy + chip_h / 2.0, name, size=13, color=ANALYTICS_CELL_TEXT, weight=600)
            tx += _lt_tw(name, 13, 600) + 6
            _lt_text(ann, tx, yy + chip_h / 2.0, val, size=13, color=ANALYTICS_CELL_TEXT)
            hx.append(cx0 + wchip / 2.0)
            hy.append(yy + chip_h / 2.0)
            ht.append(f"<b>{_lt_esc(name)}</b> ({_lt_esc(_lt_label(theme))})<br>{_lt_pct(v, 2)} of the portfolio, "
                      f"through {_cap_join(['Cash' if f == 'CASH' else f for f in funds])}")
            hs.append(chip_h - 4)
            cx0 += wchip + 8
        y += (rows + 1) * row_h - 10
    H = int(y + 4)
    fig = go.Figure()
    _lt_hover(fig, hx, hy, ht, hs)
    return _pixel_layout(fig, W, H, shapes, ann)


# ---------- Companion: Where the Risk Comes From ----------

def build_lt_risk_figure(rk, other, other_name):
    """Each fund's share of the money (left bar) next to its share of the
    risk (right bar), linked by ribbons, with three tiles at the right."""
    W = ANALYTICS_WIDTH
    shapes, ann = [], []
    hx, hy, ht, hs = [], [], [], []
    top, bh, bw, gap = 34.0, 380.0, 112.0, 196.0
    xa, xb = 0.0, bw + gap
    _lt_text(ann, xa + bw / 2.0, 14, "Share of money", anchor="center", size=13, color=TEXT_PRIMARY, weight=600)
    _lt_text(ann, xb + bw / 2.0, 14, "Share of risk", anchor="center", size=13, color=TEXT_PRIMARY, weight=600)
    funds, w, rc, vol = rk["funds"], list(rk["w"]), list(rk["rc"]), list(rk["vol"])
    pos_total = sum(max(r, 0.0) for r in rc) or 1.0
    ya = yb = top
    segs = []
    for t, wi, ri, vi in zip(funds, w, rc, vol):
        ha = bh * wi / 100.0
        hb = bh * max(ri, 0.0) / pos_total
        segs.append((t, ya, ha, yb, hb, wi, ri, vi))
        ya += ha
        yb += hb
    x0, x1 = xa + bw, xb
    xm = (x0 + x1) / 2.0
    for t, a0, ha, b0, hb, wi, ri, vi in segs:
        path = (f"M {x0},{a0:.1f} C {xm},{a0:.1f} {xm},{b0:.1f} {x1},{b0:.1f} L {x1},{b0 + hb:.1f} "
                f"C {xm},{b0 + hb:.1f} {xm},{a0 + ha:.1f} {x0},{a0 + ha:.1f} Z")
        shapes.append(dict(type="path", path=path, fillcolor=_lt_rgba(_lt_fund_color(t), 0.20),
                           line=dict(width=0), layer="below"))
    negatives = []
    for t, a0, ha, b0, hb, wi, ri, vi in segs:
        label = "Cash" if t == "CASH" else t
        fill = _lt_legible(_lt_fund_color(t))
        tc = _cx_text_on(fill)
        for xx, y0, hh, val in ((xa, a0, ha, wi), (xb, b0, hb, ri)):
            if hh <= 0.5:
                continue
            _cx_rect(shapes, xx, y0 + 1, xx + bw, y0 + hh - 1, fill, r=4)
            if hh >= 40:
                _lt_text(ann, xx + bw / 2.0, y0 + hh / 2.0 - 8, label, anchor="center", size=13.5, color=tc,
                         weight=700)
                _lt_text(ann, xx + bw / 2.0, y0 + hh / 2.0 + 9, _lt_pct(val), anchor="center", size=13, color=tc)
            elif hh >= 14:
                _lt_text(ann, xx + bw / 2.0, y0 + hh / 2.0, f"{label} {_lt_pct(val)}", anchor="center",
                         size=12.5, color=tc, weight=600)
        if ri < -0.05:
            negatives.append(f"{label} {MINUS}{abs(ri):.1f}%")
        text = (f"<b>{label}</b> ({_lt_esc(_lt_fund_name(t))})<br>{_lt_pct(wi)} of the money<br>"
                f"{(MINUS if ri < 0 else '')}{abs(ri):.1f}% of the risk<br>Volatility {vi:.1f}% a year")
        hx += [xa + bw / 2.0, xb + bw / 2.0]
        hy += [a0 + ha / 2.0, b0 + hb / 2.0]
        ht += [text, text]
        hs += [max(ha - 4, 6), max(hb - 4, 6)]
    y_end = top + bh
    if negatives:
        _lt_text(ann, xb + bw / 2.0, y_end + 16, "Offsets risk: " + ", ".join(negatives), anchor="center",
                 size=11.5, color=TEXT_MUTED)
        y_end += 22

    # Tiles at the right
    tx0, tx1 = xb + bw + 40.0, float(W)
    tw_ = tx1 - tx0
    n = len([t for t in funds if t != "CASH"])
    idx = int(np.argmax([r / wi if wi > 0 else -np.inf for r, wi in zip(rc, w)]))
    tiles = [
        ("Expected swings", f"{rk['port_vol']:.1f}% a year",
         f"{other_name}'s basket: {other['port_vol']:.1f}%" if other else "Annualized volatility"),
        ("Independent bets", f"{rk['bets']:.1f} of {n}",
         (f"{other_name}'s basket: {other['bets']:.1f}. " if other else "")
         + "One means the funds move as a single bet."),
        ("Most risk per dollar", "Cash" if funds[idx] == "CASH" else funds[idx],
         f"{w[idx]:.0f}% of the money but {rc[idx]:.0f}% of the risk"),
    ]
    ty = top
    for label, value, sub in tiles:
        lines = _cx_wrap(sub, 12.5, tw_ - 32)[:3]
        th_ = 76 + 16 * len(lines)
        _cx_rect(shapes, tx0, ty, tx1, ty + th_, ANALYTICS_TINT, r=10)
        _lt_text(ann, tx0 + 16, ty + 20, label, size=13, color=TEXT_SECONDARY)
        _lt_text(ann, tx0 + 16, ty + 47, value, size=26, color=BRAND_PURPLE, weight=700)
        for j, line in enumerate(lines):
            _lt_text(ann, tx0 + 16, ty + 74 + 16 * j, line, size=12.5, color=TEXT_SECONDARY)
        ty += th_ + 12
    H = int(max(y_end, ty - 12) + 10)
    fig = go.Figure()
    _lt_hover(fig, hx, hy, ht, hs)
    return _pixel_layout(fig, W, H, shapes, ann)


# ---------- rendering ----------

def _lt_pill_css():
    """Brand-purple pills for this section's controls only. Streamlit 1.54
    marks the selected pill with data-testid stBaseButton-pillsActive and
    1.61 with aria-checked on data-variant pills; the app-wide pill CSS
    targets older markup, so selected pills would otherwise draw in red."""
    keys = LT_PILL_KEYS
    sel = ", ".join(f'.st-key-{k} button[data-testid="stBaseButton-pillsActive"], '
                    f'.st-key-{k} button[data-variant="pills"][aria-checked="true"]' for k in keys)
    sel_p = ", ".join(f'.st-key-{k} button[data-testid="stBaseButton-pillsActive"] p, '
                      f'.st-key-{k} button[data-variant="pills"][aria-checked="true"] p' for k in keys)
    off = ", ".join(f'.st-key-{k} button[data-testid="stBaseButton-pills"], '
                    f'.st-key-{k} button[data-variant="pills"][aria-checked="false"]' for k in keys)
    off_hover = ", ".join(f'.st-key-{k} button[data-testid="stBaseButton-pills"]:hover, '
                          f'.st-key-{k} button[data-variant="pills"][aria-checked="false"]:hover' for k in keys)
    return (
        "<style>"
        f"{off} {{ border: 1px solid #ddd !important; border-radius: 8px !important; "
        f"background-color: #ffffff !important; color: {TEXT_SECONDARY} !important; font-weight: 500 !important; }}"
        f"{off_hover} {{ border-color: #bbb !important; background-color: #f5f5f8 !important; }}"
        f"{sel} {{ border: 1px solid {BRAND_PURPLE} !important; border-radius: 8px !important; "
        f"background-color: {ANALYTICS_TINT} !important; color: {BRAND_PURPLE} !important; font-weight: 600 !important; }}"
        f"{sel_p} {{ color: {BRAND_PURPLE} !important; font-weight: 600 !important; }}"
        "</style>"
    )


def _lt_pick(label, options, key, default, fmt=None):
    """Single-select pills keyed in session state. A stale or cleared value
    falls back to the default, which stays selected."""
    if key in st.session_state and st.session_state[key] not in options:
        del st.session_state[key]
    if key not in st.session_state:
        st.session_state[key] = default
    value = st.pills(label, options, selection_mode="single", key=key, format_func=fmt or str)
    return value if value in options else default


def _lt_basket_label(bk, which):
    b = bk[which]
    return _lt_short_month(b["period"]) if b else which


def _lt_basket_phrase(b):
    month = _lt_month(b["period"])
    if b["kind"] == "target":
        return f"{month} target weights, as in the Next Allocation table"
    if b.get("date") is not None:
        return f"{month} going-in weights, the holdings at the {_long_date(b['date'])} close"
    return f"{month} weights"


def _lt_sources_text(comps, tickers):
    """Where each fund's holdings came from, e.g. 'IWM and EMXC from iShares
    as of 10/29/2026'. Funds with a fixed look-through are named at the end."""
    seen, groups, fixed = set(), {}, []
    for t in tickers:
        if t in seen or t == "CASH":
            continue
        seen.add(t)
        c = comps.get(t)
        if not c or c["kind"] == "none":
            continue
        if c["kind"] == "fixed":
            fixed.append(t)
            continue
        if c["kind"] == "hand-entered":
            src = "hand-entered late-October 2026 holdings, because no issuer file loaded"
        elif t == "HGER":
            src = "Harbor"
        elif "Invesco" in c["source"]:
            src = "Invesco (GICS sectors from iShares' Nasdaq-100 fund)"
        elif "iShares" in c["source"]:
            src = "iShares"
        else:
            src = "the holdings file"
        when = f" as of {_cap_date(c['as_of'])}" if c.get("as_of") else ""
        groups.setdefault((src, when), []).append(t)
    parts = []
    for (src, when), ts in groups.items():
        if ts == ["HGER"] and src == "Harbor":
            parts.append(f"HGER's mix is the Quantix Commodity Index it tracks, from Harbor{when}")
        else:
            parts.append(f"{_cap_join(ts)} from {src}{when}")
    text = ("Fund holdings: " + "; ".join(parts) + ".") if parts else ""
    if fixed:
        what = {"GLD": "gold", "BIL": "T-bills", "IBIT": "bitcoin", "GBTC": "bitcoin", "BITO": "bitcoin"}
        text += " " + "; ".join(f"{t} is all {what.get(t, t)}" for t in fixed) + "."
    return text.strip()


def _lt_gap_notes(comps, tickers, snapshot):
    """Caption naming funds that show as one Not broken down block, and why."""
    none = [t for t in tickers if comps.get(t, {}).get("kind") == "none" and t != "CASH"]
    if not none:
        return ""
    no_file = [t for t in none if snapshot is None and t in LT_SNAPSHOT_FUNDS]
    others = [t for t in none if t not in no_file]
    parts = []
    if no_file:
        verb = "shows" if len(no_file) == 1 else "show"
        parts.append(f"{_cap_join(no_file)} {verb} as Not broken down because the fund holdings file "
                     "(holdings_snapshot.json) did not load.")
    if others:
        verb, pron, block = (("shows", "its", "a single Not broken down block") if len(others) == 1
                             else ("show", "their", "one Not broken down block"))
        parts.append(f"{_cap_join(others)} {verb} as {block} because {pron} holdings aren't loaded here.")
    return " ".join(parts)


def render_lt_views(bk, comps, snapshot, view, which):
    basket = bk[which]
    exp = lt_exposure(basket["weights"], comps)
    cmp_key = "current" if which == "next" else "prev"
    cmp_basket = bk.get(cmp_key)
    cmp_exp = lt_exposure(cmp_basket["weights"], comps) if cmp_basket else None
    note = _lt_gap_notes(comps, list(basket["weights"]), snapshot)
    if view == "Table" and cmp_basket:
        cmp_none = [t for t in canonical_order(list(cmp_basket["weights"]))
                    if t != "CASH" and t not in basket["weights"] and comps.get(t, {}).get("kind") == "none"]
        if cmp_none:
            period = pd.Period(cmp_basket["period"], freq="M")
            share = sum(cmp_basket["weights"][t] for t in cmp_none)
            verb, pron = ("is", "it counts") if len(cmp_none) == 1 else ("are", "they count")
            note += ((" " if note else "") + f"{period.strftime('%B')}'s {_cap_join(cmp_none)} ({share:.1f}% of "
                     f"that basket) {verb} not broken down, so {pron} in no theme in the vs "
                     f"{period.strftime('%b')} column or the tiles.")
    if note:
        st.caption(note)
    if view == "Table":
        fig = build_lt_table_figure(exp, cmp_exp, cmp_basket["period"] if cmp_basket else None,
                                    lt_table_tiles(exp, cmp_exp, cmp_basket["period"] if cmp_basket else None))
        name = "Look-Through Exposure Table"
    elif view == "Map":
        fig = build_lt_map_figure(exp)
        name = "Look-Through Exposure Map"
    else:
        fig = build_lt_flow_figure(exp, comps, lt_flow_tiles(exp, comps))
        name = "Look-Through Exposure Flow"
    st.plotly_chart(fig, use_container_width=False, config=chart_config(name, static=True),
                    key=f"lt_fig_{view}_{which}")
    shown = canonical_order([t for t in basket["weights"] if t != "CASH"])
    if view == "Table" and cmp_basket:
        shown += [t for t in canonical_order(list(cmp_basket["weights"])) if t not in shown]
    lead = f"{_lt_basket_phrase(basket)}, looked through to each fund's holdings."
    if view == "Table":
        how = ("Percentage points of the whole portfolio. Each fund column shows what that fund contributes "
               "to the row.")
        if cmp_basket:
            how += (f" vs {pd.Period(cmp_basket['period'], freq='M').strftime('%b')} is the change from the "
                    f"{_lt_month(cmp_basket['period'])} basket; both baskets are looked through to the same, "
                    "latest fund holdings, so the change reflects only the new weights.")
        how += (" Largest single holdings add up each name across funds; Alphabet's two share classes and "
                "Samsung's common and preferred shares count as one.")
    elif view == "Map":
        how = ("Box size is share of the portfolio. Blue boxes are stocks, brown are commodities, orange is "
               f"bitcoin. Holdings of {LT_MAP_NAME_PCT:.1f}% of the portfolio or more are named; lighter boxes "
               "are the rest of a fund's holdings in that group.")
    else:
        how = "Percentages are shares of the whole portfolio; each ribbon is one fund's holdings in a theme."
    _footnote(
        f"{lead} {how} Chips include chip designers, makers and equipment suppliers (for example NVIDIA, "
        "Broadcom, TSMC, Samsung Electronics and SK hynix); the rest of information technology is Software "
        "&amp; other tech. Each fund's small cash and derivatives sleeve is spread across its holdings. "
        + _lt_esc(_lt_sources_text(comps, shown))
    )


def render_lt_risk(bk, returns):
    _corr_subhead("Where the Risk Comes From",
                  "Each fund's share of the money next to its share of the basket's day-to-day swings.")
    options = ["current", "next"] if bk["next"] else ["current"]
    c1, c2 = st.columns(2)
    with c1:
        which = _lt_pick("Basket", options, "lt_risk_basket", options[-1],
                         fmt=lambda k: _lt_basket_label(bk, k))
    with c2:
        win_label = _lt_pick("Window", list(LT_RISK_WINDOWS), "lt_risk_window", "3 months")
    window = LT_RISK_WINDOWS[win_label]
    if returns is None or returns.empty:
        st.info("Where the Risk Comes From needs daily fund prices, which did not load right now. "
                "Reloading in a few minutes usually restores them.")
        return
    rk = lt_risk(returns, bk[which]["weights"], window)
    if rk is None:
        st.info("Where the Risk Comes From needs at least a month of daily prices for the basket's funds.")
        return
    other_key = "current" if which == "next" else ("next" if bk["next"] else "prev")
    other_b = bk.get(other_key)
    other = lt_risk(returns, other_b["weights"], window) if other_b else None
    other_name = pd.Period(other_b["period"], freq="M").strftime("%B") if other_b else ""
    fig = build_lt_risk_figure(rk, other, other_name)
    st.plotly_chart(fig, use_container_width=False,
                    config=chart_config("Where the Risk Comes From", static=True),
                    key=f"lt_risk_fig_{which}_{window}")
    ratios = {t: r / wi for t, r, wi in zip(rk["funds"], rk["rc"], rk["w"]) if t != "CASH" and wi > 0}
    zig = min(ratios, key=ratios.get) if ratios else None
    zig_txt = (f", like {zig} lately," if zig and ratios[zig] < 0.6 else "")
    missing = ""
    if rk["missing"]:
        missing = f" Prices did not load for {_cap_join(rk['missing'])}, so the shares cover the other funds."
    short = ""
    if rk["n"] < window * 0.9:
        short = f" Only {rk['n']} sessions of history are available for this basket's funds."
    _footnote(
        f"Risk share is each fund's contribution to the basket's variance, from daily returns over the chosen "
        f"window: 3 months is the last {LT_RISK_WINDOWS['3 months']} trading days, 12 months the last "
        f"{LT_RISK_WINDOWS['12 months']}, here {_long_date(rk['start'])} through {_long_date(rk['end'])}, using "
        f"{_lt_basket_phrase(bk[which])}. A fund that tends to zig when the others zag{zig_txt} takes up less "
        "risk than money. Expected swings is the basket's annualized volatility over the same days. "
        "Independent bets is the diversification ratio squared (Choueifaty and Coignard, 2008): 1 means the "
        f"funds move as one bet; {len([t for t in rk['funds'] if t != 'CASH'])} unrelated, equally volatile "
        f"funds would score {len([t for t in rk['funds'] if t != 'CASH'])}. Daily returns come from adjusted "
        f"closes on U.S. equity trading days.{short}{missing}"
    )


def render_lookthrough_section(holdings_values):
    """Look-Through Exposure: a Flow / Table / Map switcher over the current
    or next basket, then Where the Risk Comes From. Each part is guarded so a
    data problem in one leaves the other standing."""
    st.markdown(
        f'<p style="font-size:0.92rem; color:{TEXT_SECONDARY}; margin:0 0 0.4rem 0;">Everything the funds '
        'hold, combined, so overlap between them is visible.</p>',
        unsafe_allow_html=True,
    )
    if holdings_values is None or holdings_values.empty:
        st.info("Look-Through Exposure needs holdings_daily_values.csv, which did not load.")
        return
    totals = _load_reconstructed_totals()
    next_rows = load_next_allocation()
    baskets = corr_going_in_baskets(holdings_values, totals)
    bk = lt_baskets(baskets, holdings_values.index.max(), next_rows)
    if bk is None:
        st.info("Look-Through Exposure needs a completed rebalance in holdings_daily_values.csv.")
        return
    snapshot = load_holdings_snapshot()
    tickers = []
    for key in ("current", "next", "prev"):
        if bk[key]:
            tickers += [t for t in bk[key]["weights"] if t not in tickers]
    # What HGER Holds (just above) already fetched Harbor when it is showing.
    hger_panel_shown = _hger_is_held(derive_current_allocation(holdings_values)[0])
    comps = lt_compositions(tickers, snapshot, live_hger=not hger_panel_shown)
    st.markdown(_lt_pill_css(), unsafe_allow_html=True)
    options = ["current", "next"] if bk["next"] else ["current"]
    c1, c2 = st.columns(2)
    with c1:
        which = _lt_pick("Basket", options, "lt_basket", options[-1], fmt=lambda k: _lt_basket_label(bk, k))
    with c2:
        view = _lt_pick("View", LT_VIEWS, "lt_view", LT_VIEWS[0])
    _render_guarded(f"Look-Through Exposure ({view})", render_lt_views, bk, comps, snapshot, view, which,
                    heading=False)
    start = (pd.Timestamp(ALLOC_HISTORY_START) - timedelta(days=CORR_PRICE_LEAD_DAYS)).strftime("%Y-%m-%d")
    end = local_now().strftime("%Y-%m-%d")
    try:
        prices = load_holding_prices(tuple(corr_price_tickers(baskets, next_rows)), start, end)
        returns = corr_equity_returns(prices)
    except Exception:
        returns = pd.DataFrame()
    _render_guarded("Where the Risk Comes From", render_lt_risk, bk, returns, heading=False)


def main():
    # Branded header
    st.markdown("""
    <div class="brand-header">
        <span class="brand-name">Asymmetric Edge</span>
        <span class="brand-tag">Market Performance</span>
    </div>
    """, unsafe_allow_html=True)

    # One-time-per-session reset of stale session-state date fields.
    # Streamlit's `value=` widget defaults only apply on first render;
    # after that, session state owns the value. Across dashboard restarts
    # this means values like an as-of date set days ago can stick around
    # and quietly drift out of date. Bumping DATE_RESET_VERSION forces a
    # one-time clear on each user's first load of the new version. User
    # changes within the same session still persist normally.
    #
    # We also PRE-POPULATE the MTD return and as-of date here so the
    # partial-month extension below runs on this same render, which is
    # what advances `latest_date` past the CSV's last row and lets the
    # Performance Summary date pickers default to today rather than to
    # the CSV's stale endpoint.
    DATE_RESET_VERSION = "v2026_06_07a"
    if st.session_state.get("_dates_reset_version") != DATE_RESET_VERSION:
        for _k in ("upd_as_of", "upd_mtd_return", "summary_end_date", "summary_start_date"):
            st.session_state.pop(_k, None)
        # MTD return not seeded; field defaults to empty after a full rebuild.
        st.session_state["upd_as_of"] = local_now().date()
        st.session_state["_dates_reset_version"] = DATE_RESET_VERSION

    # Load data
    portfolio_df = load_portfolio_data()

    # Apply partial-month extension if the user has entered a MTD return.
    # Session state is populated by the update expander (rendered below); on
    # the first run the keys won't exist yet, which is fine -- the extension
    # only kicks in after the user enters values and the page reruns.
    _mtd_ret = st.session_state.get("upd_mtd_return")
    _mtd_as_of = st.session_state.get("upd_as_of")
    if _mtd_ret is not None and _mtd_as_of is not None:
        portfolio_df = extend_with_partial_month(portfolio_df, _mtd_ret, _mtd_as_of)

    inception_date = portfolio_df["date"].iloc[0]
    latest_date = portfolio_df["date"].iloc[-1]

    bench_close = load_benchmark_data(
        inception_date.strftime("%Y-%m-%d"),
        latest_date.strftime("%Y-%m-%d"),
    )

    portfolio_series = portfolio_df.set_index("date")["portfolio_value"]
    portfolio_series.index = pd.to_datetime(portfolio_series.index)

    all_series = {"AsymEdge": portfolio_series}
    _missing_benchmarks = []
    for name, ticker in BENCHMARK_TICKERS.items():
        raw = bench_close[ticker].dropna() if ticker in bench_close.columns else pd.Series(dtype="float64")
        norm = normalize_to_10k(raw)
        if norm.dropna().empty:
            _missing_benchmarks.append(f"{name} ({ticker})")
            continue
        all_series[name] = norm

    if _missing_benchmarks:
        st.warning(
            "Price data unavailable for " + ", ".join(_missing_benchmarks)
            + ". Yahoo Finance rate-limits shared cloud hosts; these lines are "
            "hidden for now. Reloading in a few minutes usually restores them."
        )

    combined = pd.DataFrame(all_series)
    combined = combined.sort_index()

    # Clip every series to the portfolio's own lifespan. load_benchmark_data
    # fetches a 7-day lead buffer before inception (so a trading day always
    # exists at/before any period start), which leaves the benchmark columns
    # holding a few late-December 2023 rows that the Asymmetric Edge column
    # does not have. The Performance Comparison, Portfolio Growth, and Total
    # Return charts re-base each series to the first value on/after the
    # selected period start, so those extra rows are harmless there. But
    # compute_summary_metrics anchors monthly returns on the prior month-end,
    # so for the benchmarks it would anchor the Inception figure on the
    # December 2023 month-end instead of the 01/02/2024 inception date. That
    # made the Performance Summary table's benchmark Inception returns
    # disagree with the Inception bars in the other charts. Clipping here
    # removes the pre-inception rows so all five views anchor on the same
    # inception date and tie out.
    combined = combined[
        (combined.index >= inception_date) & (combined.index <= latest_date)
    ]

    latest_str = latest_date.strftime("%B %d, %Y")
    st.markdown(
        f'<p class="brand-sub">Data through {latest_str} &nbsp;&middot;&nbsp; '
        f'Refreshed {format_clock(local_now())} MT &nbsp;&middot;&nbsp; '
        f'<span style="color:#9CA3AF; font-size:0.78rem;">Build v2026-05-27c</span></p>',
        unsafe_allow_html=True,
    )

    # Partial-month update expander (collapsed by default). Placed near the
    # top of the page so the workflow instructions sit next to the freshness
    # indicator above. The MTD return entered here feeds back into the
    # portfolio series at the top of main() via session state, extending the
    # data for all charts on the next rerun.
    render_update_section(portfolio_df)

    # ================================================================
    # PERFORMANCE SUMMARY (above-the-fold executive summary table)
    # ================================================================
    st.markdown("## Performance Summary")

    # Default custom range to full inception â†’ latest. The date pickers below
    # let the user narrow this without affecting the rest of the dashboard.
    #
    # Auto-advance the End date so it tracks the latest data date. Streamlit
    # caches a widget's value in session state and ignores the `value=` default
    # on later reruns, so once the series is extended the End date would stay
    # pinned to the old last date. We bump it forward automatically, but ONLY
    # when the user has not deliberately picked an earlier end date -- i.e.,
    # when the stored end date still equals the latest date we last aligned it
    # to. A manual custom end date is detected (stored < tracked) and left
    # untouched. This removes the need to bump DATE_RESET_VERSION on each
    # data refresh just to move the End date.
    _latest_end = latest_date.date()
    if "summary_end_date" not in st.session_state:
        # First render (or just after a version reset): the widget will fall
        # back to value=latest_date this render. Record what we aligned to.
        st.session_state["_summary_end_tracked_latest"] = _latest_end
    else:
        _tracked_end = st.session_state.get("_summary_end_tracked_latest")
        _stored_end = st.session_state["summary_end_date"]
        if _tracked_end is None:
            # Session predating this feature: adopt the current value as the
            # baseline so future advances are detected, without overriding now.
            st.session_state["_summary_end_tracked_latest"] = _stored_end
        elif _stored_end == _tracked_end and _latest_end > _stored_end:
            # User never moved the picker off the previous latest date and the
            # data has advanced, so follow it forward.
            st.session_state["summary_end_date"] = _latest_end
            st.session_state["_summary_end_tracked_latest"] = _latest_end

    col_sd, col_ed = st.columns(2)
    with col_sd:
        summary_start = st.date_input(
            "Start date",
            value=inception_date.date(),
            min_value=inception_date.date(),
            max_value=latest_date.date(),
            key="summary_start_date",
        )
    with col_ed:
        summary_end = st.date_input(
            "End date",
            value=latest_date.date(),
            min_value=inception_date.date(),
            max_value=latest_date.date(),
            key="summary_end_date",
        )

    summary_start_ts = pd.Timestamp(summary_start)
    summary_end_ts = pd.Timestamp(summary_end)

    if summary_start_ts >= summary_end_ts:
        st.warning("Start date must be before end date.")
    else:
        # Load BIL once for the full available range, then let
        # compute_summary_metrics reindex into each series' window.
        rf_monthly = load_bil_data(
            inception_date.strftime("%Y-%m-%d"),
            latest_date.strftime("%Y-%m-%d"),
        )

        summary_metrics_by_series = {}
        for name in SERIES_ORDER:
            if name in combined.columns:
                summary_metrics_by_series[name] = compute_summary_metrics(
                    combined[name],
                    rf_monthly=rf_monthly,
                    start_date=summary_start_ts,
                    end_date=summary_end_ts,
                )

        if any(summary_metrics_by_series.values()):
            table_html = build_summary_table_html(summary_metrics_by_series, SERIES_ORDER)
            st.markdown(table_html, unsafe_allow_html=True)
        else:
            st.info("Not enough data in the selected range to compute summary metrics.")

        footnote_summary = (
            f"Metrics computed from daily portfolio values over the selected period. "
            f"Monthly-based figures (CAGR, Sortino, Calmar, Annualized Vol, Best/Worst Year, Win Rate) "
            f"resample to month-end values and anchor on the prior month-end, so the first monthly "
            f"return covers the full calendar month of the selected start date. "
            f"Sortino ratio uses BIL (1-3 Month T-Bill ETF) as the risk-free rate where available; "
            f"months outside BIL's history default to 0%. "
            f"Max DD (Daily), Worst/Best Single Day, and Worst/Best Week are computed from the daily series over the "
            f"literal selected range, with the date of occurrence shown beneath each figure (and on hover). Worst/Best "
            f"Week use week-ending (Friday) closes. Worst/Best Month use the anchored monthly returns. "
            f"Asymmetric Edge monthly and trailing-period returns are anchored to Fidelity's reported "
            f"time-weighted returns and tie exactly, so Worst/Best Month are exact for Asymmetric Edge. Within-month "
            f"daily and weekly values (including Max DD Daily and Worst/Best Single Day and Week) are approximations "
            f"derived from a close-only reconstruction. The most recent month may be partial when the end date falls mid-month. "
            f"S&P 500 (SPY), 60/40 (AOR), and 80/20 (AOA) total return data sourced from Yahoo Finance (adjusted close, dividends reinvested). "
            f"All figures are pre-tax and pre-fee."
        )
        st.markdown(f'<p class="footer-text">{footnote_summary}</p>', unsafe_allow_html=True)

    st.divider()

    # Load asset class data once
    asset_start = (pd.Timestamp(latest_date) - timedelta(days=400)).strftime("%Y-%m-%d")
    asset_close = load_asset_class_data(
        tuple(ASSET_CLASS_TICKERS.values()), asset_start, latest_date.strftime("%Y-%m-%d")
    )

    # ================================================================
    # ASSET UNIVERSE
    # ================================================================
    render_asset_universe_section()

    st.divider()

    # ================================================================
    # CURRENT ALLOCATION
    # ================================================================
    st.markdown("## Current Allocation")

    # Auto-derive the current allocation from actual end-of-day holdings at the
    # most recent rebalance, the same source the Allocation Drift table uses for
    # its Month Start column. The table updates itself every time the pipeline
    # regenerates holdings_daily_values.csv, so it can never disagree with the
    # drift table's Month Start. There is no hardcoded fallback, if the holdings
    # data is missing the dashboard shows an error rather than stale numbers.
    _holdings_for_alloc = load_holdings_values()
    current_alloc_rows, current_alloc_date = derive_current_allocation(_holdings_for_alloc)

    if current_alloc_rows is None:
        current_alloc_date = None
        st.error(
            "Current allocation unavailable. The dashboard could not read a current "
            "allocation from holdings_daily_values.csv (the file is missing or contains "
            "no completed rebalance yet). Run portfolio_valuation.py in the pipeline "
            "folder to generate it, then refresh. No fallback figures are shown on "
            "purpose, so you are never looking at stale, hand-entered percentages."
        )
    else:
        alloc_config = chart_config("Current Allocation", static=True)
        st.plotly_chart(build_allocation_table(current_alloc_rows), use_container_width=False, config=alloc_config)

        footnote_alloc = (
            f"Current portfolio allocation as of the {current_alloc_date.strftime('%b %d, %Y')} "
            f"rebalance, computed automatically from your reconstructed end-of-day holdings, the "
            f"same source as the Allocation Drift table's Month Start column. It refreshes whenever "
            f"the pipeline regenerates holdings_daily_values.csv, so there is nothing to update by "
            f"hand. Holdings and weights are subject to change based on regime signals and market conditions."
        )
        st.markdown(f'<p class="footer-text">{footnote_alloc}</p>', unsafe_allow_html=True)

    # ================================================================
    # WHAT HGER HOLDS (QCI look-through, shown only while HGER is held)
    # ================================================================
    if _hger_is_held(current_alloc_rows):
        render_hger_lookthrough_section()

    # ================================================================
    # LOOK-THROUGH EXPOSURE (added October 31, 2026)
    # Everything the current and next baskets hold, combined across
    # funds (Flow, Table and Map views), then Where the Risk Comes From.
    # Fund holdings come from holdings_snapshot.json (written by
    # make_holdings_snapshot.py in ae-dashboard-deploy) and HGER's
    # live Harbor feed above.
    # ================================================================
    _render_guarded(LT_SECTION_TITLE, render_lookthrough_section, _holdings_for_alloc)

    # ================================================================
    # LIVE POSITION DRIFT (intramonth, for deposit / withdrawal sizing)
    # ================================================================
    st.markdown("## Live Position Drift")

    _ld_weights = _parse_current_allocation_weights(current_alloc_rows)
    if not _ld_weights:
        st.info(
            "Live position drift unavailable. It is derived from the current "
            "allocation, which could not be read from holdings_daily_values.csv. "
            "Run the pipeline to generate that file, then refresh."
        )
    else:
        _ld_tickers = canonical_order(list(_ld_weights.keys()))
        _ld_start = tuple(_ld_weights[t] for t in _ld_tickers)
        _ld_today = pd.Timestamp.today().strftime("%Y-%m-%d")
        live_drift, live_drift_msg = compute_live_position_drift(
            tuple(_ld_tickers), _ld_start, _ld_today
        )

        if live_drift is None:
            st.info(
                "Live position drift could not be computed right now. The live "
                f"price fetch did not return usable data. Detail: {live_drift_msg}"
            )
        else:
            live_drift_config = chart_config("Live Position Drift", static=True)
            st.plotly_chart(
                build_live_drift_table(live_drift),
                use_container_width=False,
                config=live_drift_config,
            )

            footnote_live = (
                f"How the current month's going-in weights have drifted, using "
                f"live dividend-adjusted prices, so a mid-month deposit or "
                f"withdrawal can be sized against where the positions sit now. "
                f"<b>Month Start</b> is each holding's going-in target weight as of "
                f"{live_drift['anchor_date'].strftime('%b %d, %Y')} close, the most "
                f"recent month-end rebalance. <b>Return</b> is each holding's total "
                f"return from that date through "
                f"{live_drift['as_of_date'].strftime('%b %d, %Y')} close. "
                f"<b>Current</b> is the weight each position has drifted to, found by "
                f"growing every month-start weight by its return and renormalizing so "
                f"the column sums to 100%. A holding that has outpaced the others "
                f"reads above its month-start weight, and one that has lagged reads "
                f"below it, so the gap between Month Start and Current shows where to "
                f"steer new cash. Prices refresh through the trading day. Weights come "
                f"from the Current Allocation table above, which now updates automatically "
                f"from your holdings data, so there is nothing to update by hand."
            )
            st.markdown(f'<p class="footer-text">{footnote_live}</p>', unsafe_allow_html=True)

    # ================================================================
    # NEXT ALLOCATION (editable)
    # ================================================================
    st.markdown("## Next Allocation")

    st.markdown(
        '<p style="background-color:#FFF3CD; color:#856404; padding:0.6rem 1rem; '
        'border-radius:6px; font-size:0.88rem; font-weight:500; '
        'border-left:4px solid #F4D35E; margin-bottom:1rem;">'
        '\u26A0\uFE0F  Remember to update <b>next_allocation.json</b> (via the editor below) '
        'whenever the planned allocation changes. This table is manually maintained.</p>',
        unsafe_allow_html=True,
    )

    # --- Load saved rows ---
    saved_rows = load_next_allocation()

    # --- Editor expander ---
    available_tickers = sorted(ASSET_CATALOG.keys())
    with st.expander("Edit Next Allocation"):
        st.caption(
            "Select tickers and enter weights below. Asset name and purpose auto-populate "
            "from the asset catalog. Click **Save** to persist changes to next_allocation.json."
        )

        num_rows = st.number_input(
            "Number of holdings",
            min_value=1,
            max_value=12,
            value=max(len(saved_rows), 4),
            step=1,
            key="next_alloc_num_rows",
        )

        editor_rows = []
        for i in range(int(num_rows)):
            cols = st.columns([2, 1])
            # Pre-fill from saved data if available
            default_ticker_idx = 0
            default_weight = ""
            if i < len(saved_rows):
                saved_ticker = saved_rows[i].get("ticker", "")
                if saved_ticker in available_tickers:
                    default_ticker_idx = available_tickers.index(saved_ticker)
                default_weight = saved_rows[i].get("weight", "").replace("%", "")

            with cols[0]:
                ticker = st.selectbox(
                    f"Ticker {i + 1}",
                    options=available_tickers,
                    index=default_ticker_idx,
                    key=f"next_alloc_ticker_{i}",
                )
            with cols[1]:
                weight = st.text_input(
                    f"Weight % {i + 1}",
                    value=default_weight,
                    placeholder="e.g. 25.00",
                    key=f"next_alloc_weight_{i}",
                )

            info = ASSET_CATALOG.get(ticker, {})
            editor_rows.append({
                "ticker": ticker,
                "asset": info.get("asset", ticker),
                "emoji": info.get("emoji", ""),
                "purpose": info.get("purpose", ""),
                "weight": f"{weight}%" if weight else "",
            })

        # --- Weight total (live sum check) ---
        total_weight = 0.0
        for row in editor_rows:
            w_str = row["weight"].replace("%", "").strip()
            if w_str:
                try:
                    total_weight += float(w_str)
                except ValueError:
                    pass

        is_balanced = abs(total_weight - 100.0) < 0.01
        if is_balanced:
            status_html = (
                f"<div style='margin-top:8px; margin-bottom:12px; "
                f"padding:10px 14px; background-color:#D6E8DF; color:#14543E; "
                f"border-radius:6px; font-weight:600;'>"
                f"Total weight: {total_weight:.2f}% &nbsp;\u2713</div>"
            )
        else:
            diff = total_weight - 100.0
            sign = "+" if diff > 0 else ""
            status_html = (
                f"<div style='margin-top:8px; margin-bottom:12px; "
                f"padding:10px 14px; background-color:#F4E5C5; color:#7E4A0A; "
                f"border-radius:6px; font-weight:600;'>"
                f"Total weight: {total_weight:.2f}% &nbsp;({sign}{diff:.2f})</div>"
            )
        st.markdown(status_html, unsafe_allow_html=True)

        if st.button("Save Next Allocation", key="save_next_alloc"):
            save_next_allocation(editor_rows)
            st.success("Saved to next_allocation.json.")
            st.rerun()

    # --- Render the table ---
    display_rows = saved_rows if saved_rows else editor_rows
    display_rows = [r for r in display_rows if r.get("ticker")]

    # Row order (largest weight first, like the other allocation tables) is
    # applied inside build_next_allocation_table.

    if display_rows:
        next_alloc_config = chart_config("Next Allocation", static=True)
        st.plotly_chart(
            build_next_allocation_table(display_rows),
            use_container_width=False,
            config=next_alloc_config,
        )
    else:
        st.info("No next allocation configured yet. Use the editor above to add holdings.")

    # ================================================================
    # ALLOCATION DRIFT
    # ================================================================
    st.markdown("## Allocation Drift")

    holdings_values_df = load_holdings_values()

    if holdings_values_df.empty:
        st.info(
            "Allocation drift data unavailable. Run `portfolio_valuation.py` in the "
            "pipeline folder to generate **holdings_daily_values.csv**. The dashboard "
            "reads it automatically from the pipeline folder."
        )
    else:
        drift_summary = compute_drift_summary(holdings_values_df)

        if drift_summary is None:
            st.info("No rebalance found in the holdings history yet.")
        else:
            # New Target column reads from next_allocation.json. If it's
            # empty, the table renders with em-dashes in Target and Trade.
            next_allocation_rows = load_next_allocation()
            if not next_allocation_rows:
                st.markdown(
                    '<p style="background-color:#FFF3CD; color:#856404; padding:0.6rem 1rem; '
                    'border-radius:6px; font-size:0.88rem; font-weight:500; '
                    'border-left:4px solid #F4D35E; margin-bottom:1rem;">'
                    '\u26A0\uFE0F  No upcoming allocation set. Use the Next Allocation '
                    'editor above to populate the <b>New Target</b> and <b>Trim/Add</b> columns.</p>',
                    unsafe_allow_html=True,
                )

            drift_config = chart_config("Allocation Drift", static=True)
            st.plotly_chart(
                build_drift_table(drift_summary, next_allocation_rows),
                use_container_width=False,
                config=drift_config,
            )

            footnote_drift = (
                f"<b>Month Start</b> shows allocations as of "
                f"{drift_summary['period_start_date'].strftime('%b %d, %Y')} close, the most "
                f"recent rebalance, which set the going-in weights for the current period. "
                f"<b>Drift</b> shows where those allocations had drifted to by "
                f"{drift_summary['drift_date'].strftime('%b %d, %Y')} close, the latest "
                f"trading day in the data, just before the upcoming rebalance executes. "
                f"<b>New Target</b> is the upcoming allocation read from next_allocation.json "
                f"(edit it in the Next Allocation section above). <b>Trim/Add</b> is Drift &rarr; "
                f"New Target, the buy or sell that will execute on the next rebalance day. "
                f"Month Start weights are computed from actual end-of-day holdings, so they "
                f"may differ from the clean planned target percentages by a few hundredths of "
                f"a percent because of intraday price movement during the rebalance trades."
            )
            st.markdown(f'<p class="footer-text">{footnote_drift}</p>', unsafe_allow_html=True)

    st.divider()

    # ================================================================
    # ASSET ALLOCATION OVER TIME
    # ================================================================
    st.markdown("## Asset Allocation Over Time")

    if holdings_values_df.empty:
        st.info(
            "Allocation history unavailable. Run `portfolio_valuation.py` in the "
            "pipeline folder to generate **holdings_daily_values.csv**. The dashboard "
            "reads it automatically from the pipeline folder."
        )
    else:
        alloc_history_fig = build_allocation_history_figure(holdings_values_df)
        if alloc_history_fig is None:
            st.info("No allocation history could be computed from the holdings data yet.")
        else:
            st.plotly_chart(
                alloc_history_fig,
                use_container_width=True,
                config=chart_config("Asset Allocation Over Time"),
            )
            footnote_alloc_history = (
                "Portfolio allocation by asset class since inception, one bar per month. "
                "Each bar shows the weights the portfolio entered that month with: the "
                "holdings at the close of the prior month's final trading day, when the "
                "month-end rebalance executes. Trades placed on a month's last trading day "
                "therefore appear in the following month's bar. The last bar is the current "
                "month's going-in allocation, matching the Current Allocation table. Bars are "
                "computed from the same reconstructed end-of-day holdings, so the chart "
                "refreshes automatically whenever the pipeline regenerates "
                "holdings_daily_values.csv. <b>T-bills &amp; Cash</b> combines BIL, "
                "money-market positions, and uninvested cash. Hover a bar to see the exact "
                "weights and the underlying tickers inside each asset class. Holdings and "
                "weights are subject to change based on regime signals and market conditions."
            )
            st.markdown(f'<p class="footer-text">{footnote_alloc_history}</p>', unsafe_allow_html=True)
            newsletter_caption(
                f"Asymmetric Edge allocation by asset class at the start of each month, "
                f"{pd.Timestamp(inception_date):%B %Y} through {pd.Timestamp(latest_date):%B %Y}, "
                "from actual end-of-day holdings in my account. T-bills & Cash includes BIL and "
                "money market funds."
            )

    st.divider()

    # ================================================================
    # REBALANCE LOG (added October 22, 2026)
    # ================================================================
    _analytics_totals = _load_reconstructed_totals()
    _held = _held_tickers(holdings_values_df, since=inception_date)
    holding_prices = (
        load_holding_prices(
            tuple(sorted(_held)),
            (inception_date - timedelta(days=10)).strftime("%Y-%m-%d"),
            latest_date.strftime("%Y-%m-%d"),
        )
        if _held else pd.DataFrame()
    )
    _render_guarded("Rebalance Log", render_rebalance_log_section,
                    holdings_values_df, _analytics_totals, holding_prices)

    st.divider()

    # ================================================================
    # CORRELATION AND DIVERSIFICATION (added October 31, 2026)
    # Correlation Over Time, Correlation Matrix, and Did the
    # Diversification Hold?, from the same holdings and prices as the
    # allocation sections above.
    # ================================================================
    _render_guarded(CORR_SECTION_TITLE, render_correlation_section,
                    holdings_values_df, _analytics_totals)

    st.divider()

    # ================================================================
    # 1. PERFORMANCE COMPARISON
    # ================================================================
    st.markdown("## Performance Comparison")

    periods = ["YTD", "MTD", "3M", "6M", "1Y", "2025", "2024", "Inception"]
    selected_periods = st.pills(
        "Select periods",
        periods,
        default=["YTD", "6M", "1Y", "Inception"],
        selection_mode="multi",
        key="perf_periods",
    )
    if not selected_periods:
        selected_periods = ["YTD", "6M", "1Y", "Inception"]

    bar_data = []
    for period in selected_periods:
        start, end = get_period_dates(latest_date, period, inception_date)
        for name in SERIES_ORDER:
            if name in combined.columns:
                ret = compute_return(combined[name], start, end)
                bar_data.append({"Period": period, "Series": name, "Return": ret if ret is not None else 0})

    bar_df = pd.DataFrame(bar_data)
    st.plotly_chart(build_performance_chart(bar_df, SERIES_ORDER), use_container_width=True, config=chart_config("Performance Comparison"))

    # Build a "Period (start to end)" list so the footnote states the exact
    # date range each bar group is measured over.
    perf_period_ranges = []
    for period in selected_periods:
        p_start, p_end = get_period_dates(latest_date, period, inception_date)
        perf_period_ranges.append(
            f"{period} ({p_start.strftime('%m/%d/%Y')} to {p_end.strftime('%m/%d/%Y')})"
        )

    footnote = (
        f"Total returns for each selected period: {', '.join(perf_period_ranges)}. "
        f"Each period's return is measured from the close on its start date. "
        f"Asymmetric Edge monthly and trailing-period returns are anchored to Fidelity's reported "
        f"time-weighted returns for a personal portfolio. "
        f"S&P 500 (SPY), 60/40 (AOR), and 80/20 (AOA) total return data sourced from Yahoo Finance (adjusted close, dividends reinvested). "
        f"All performance figures are shown before taxes and advisory fees, which would reduce returns."
    )
    st.markdown(f'<p class="footer-text">{footnote}</p>', unsafe_allow_html=True)
    newsletter_caption(
        f"{_cap_vs(SERIES_ORDER)}, data through {_cap_date(latest_date)}. Strategy live since "
        f"{_cap_date(inception_date)}. " + NEWSLETTER_RETURNS_SENTENCES
    )

    st.divider()

    # ================================================================
    # 2. PORTFOLIO GROWTH
    # ================================================================
    st.markdown("## Portfolio Growth")

    growth_periods = ["3M", "6M", "YTD", "1Y", "2025", "2024", "Inception"]
    selected_growth = st.pills(
        "Select period",
        growth_periods,
        default="Inception",
        selection_mode="single",
        key="growth_period",
    )
    if not selected_growth:
        selected_growth = "Inception"

    start_g, end_g = get_period_dates(latest_date, selected_growth, inception_date)

    # Determine which series are available to plot. Toggle controls below the
    # chart let the user show/hide each one.
    all_possible_series = [s for s in SERIES_ORDER if s in combined.columns]

    # Initialize toggle state once per series (default on). After this, the
    # widget below owns the state via its key.
    for name in all_possible_series:
        key = f"growth_toggle_{name}"
        if key not in st.session_state:
            st.session_state[key] = True

    # Only plot series whose toggle is currently on.
    enabled_series = [
        name for name in all_possible_series
        if st.session_state.get(f"growth_toggle_{name}", True)
    ]

    growth_fig, _ = build_growth_chart(combined, enabled_series, start_g, end_g)
    st.plotly_chart(growth_fig, use_container_width=True, config=chart_config("Portfolio Growth"))

    # Compact toggle row for show/hide. The series labels, color swatches,
    # and dollar values are baked into the Plotly figure itself (see
    # build_growth_chart), so they're captured in the toolbar's PNG export.
    if all_possible_series:
        toggle_cols = st.columns(len(all_possible_series))
        for i, name in enumerate(all_possible_series):
            with toggle_cols[i]:
                st.toggle(series_label(name), key=f"growth_toggle_{name}")

    footnote_growth = (
        f"Growth of $10,000 invested on {start_g.strftime('%m/%d/%Y')}, the start of the selected "
        f"{selected_growth} period, through {end_g.strftime('%m/%d/%Y')} (total return, dividends reinvested). "
        f"Asymmetric Edge data anchored to Fidelity's reported monthly time-weighted returns for a personal portfolio. "
        f"S&P 500 (SPY), 60/40 (AOR), and 80/20 (AOA) total return data sourced from Yahoo Finance (adjusted close). "
        f"All performance figures are shown before taxes and advisory fees, which would reduce returns."
    )
    st.markdown(f'<p class="footer-text">{footnote_growth}</p>', unsafe_allow_html=True)
    newsletter_caption(
        f"Growth of $10,000, {_cap_date(start_g)} through {_cap_date(end_g)}. "
        + newsletter_returns_sentences(enabled_series)
    )

    # Partial-month extension status. Surfaced here so it's visible alongside
    # the chart whose shape it controls, not just in the collapsed Update
    # expander. Always rendered, even when no extension is active, so it
    # also functions as a sanity check that the latest code is running.
    _gs_mtd = st.session_state.get("upd_mtd_return")
    _gs_asof = st.session_state.get("upd_as_of")
    _growth_status = get_partial_month_status(portfolio_df, _gs_mtd, _gs_asof)
    _gs_bg_map = {
        "daily_shape_full": "#D6E8DF",
        "daily_shape_full_via_yahoo": "#D6E8DF",
        "daily_shape_partial": "#F4E5C5",
        "daily_shape_partial_via_yahoo": "#F4E5C5",
        "single_endpoint": "#F4E5C5",
        "noop": "#E5E7EB",
        "none": "#E5E7EB",
    }
    _gs_fg_map = {
        "daily_shape_full": "#14543E",
        "daily_shape_full_via_yahoo": "#14543E",
        "daily_shape_partial": "#7E4A0A",
        "daily_shape_partial_via_yahoo": "#7E4A0A",
        "single_endpoint": "#7E4A0A",
        "noop": "#4B5563",
        "none": "#4B5563",
    }
    _gs_bg = _gs_bg_map.get(_growth_status["mode"], "#E5E7EB")
    _gs_fg = _gs_fg_map.get(_growth_status["mode"], TEXT_SECONDARY)
    st.markdown(
        f"<div style='margin-top:6px; padding:8px 12px; background-color:{_gs_bg}; "
        f"color:{_gs_fg}; border-radius:6px; font-size:0.82rem;'>"
        f"<b>Partial-month extension ({_growth_status['mode']}):</b> {_growth_status['detail']}</div>",
        unsafe_allow_html=True,
    )

    # Diagnostic expander: shows the raw last-N portfolio_df rows and their
    # day-to-day returns. Lets you see directly whether the data feeding the
    # chart is genuinely jagged or has flat/smooth stretches near the as-of
    # date.
    with st.expander("Diagnostic: last 15 portfolio values", expanded=False):
        _last = portfolio_df.tail(15).copy()
        _last["date"] = pd.to_datetime(_last["date"]).dt.strftime("%Y-%m-%d")
        _last["daily_return_%"] = (
            portfolio_df["portfolio_value"].pct_change().tail(15) * 100
        ).round(3)
        _last["value"] = _last["portfolio_value"].round(2)
        _last = _last[["date", "value", "daily_return_%"]].rename(
            columns={"date": "Date", "value": "Value ($)", "daily_return_%": "Daily Return (%)"}
        )
        st.dataframe(_last, hide_index=True, use_container_width=True)

        # Surface the recon CSV's last date directly so you can see at a glance
        # where the canonical reconstruction stops and Yahoo extension takes over.
        _recon_df_for_diag = load_reconstruction_data()
        if _recon_df_for_diag is None:
            st.caption("Reconstruction CSV: not found.")
        else:
            _recon_first = pd.Timestamp(_recon_df_for_diag["date"].iloc[0]).strftime("%Y-%m-%d")
            _recon_last = pd.Timestamp(_recon_df_for_diag["date"].iloc[-1]).strftime("%Y-%m-%d")
            st.caption(
                f"Reconstruction CSV: {len(_recon_df_for_diag)} rows, "
                f"{_recon_first} → {_recon_last}. "
                f"Final portfolio_df last date: {pd.Timestamp(portfolio_df['date'].iloc[-1]).strftime('%Y-%m-%d')}."
            )

    st.divider()

    # ================================================================
    # MONTHLY RETURNS and WHAT DROVE THE MONTH (added October 22, 2026)
    # ================================================================
    _render_guarded("Monthly Returns", render_monthly_returns_section, combined, latest_date)

    st.divider()

    _render_guarded("Where the Month's Return Came From", render_attribution_section,
                    portfolio_series, holdings_values_df, _analytics_totals,
                    holding_prices, latest_date, heading=False)

    st.divider()

    # ================================================================
    # 3. MAXIMUM DRAWDOWN
    # ================================================================
    st.markdown("## Maximum Drawdown")

    dd_periods = ["YTD", "6M", "1Y", "2025", "2024", "Inception"]
    selected_dd = st.pills(
        "Select periods",
        dd_periods,
        default=["YTD", "1Y", "Inception"],
        selection_mode="multi",
        key="dd_periods",
    )
    if not selected_dd:
        selected_dd = ["YTD", "1Y", "Inception"]

    dd_data = []
    for period in selected_dd:
        start, end = get_period_dates(latest_date, period, inception_date)
        for name in SERIES_ORDER:
            if name in combined.columns:
                dd = compute_max_drawdown(combined[name], start, end)
                dd_data.append({"Period": period, "Series": name, "Drawdown": dd if dd is not None else 0})

    dd_df = pd.DataFrame(dd_data)
    st.plotly_chart(build_drawdown_chart(dd_df, SERIES_ORDER), use_container_width=True, config=chart_config("Maximum Drawdown"))

    # Build a "Period (start to end)" list so the footnote states the exact
    # date range each drawdown bar is measured over.
    dd_period_ranges = []
    for period in selected_dd:
        p_start, p_end = get_period_dates(latest_date, period, inception_date)
        dd_period_ranges.append(
            f"{period} ({p_start.strftime('%m/%d/%Y')} to {p_end.strftime('%m/%d/%Y')})"
        )

    footnote_dd = (
        f"Maximum drawdown measures the largest peak-to-trough decline within each selected period: "
        f"{', '.join(dd_period_ranges)}. "
        f"Asymmetric Edge drawdowns are computed from daily values derived from a close-only reconstruction "
        f"anchored to Fidelity's monthly time-weighted returns and are therefore approximations. "
        f"S&P 500 (SPY), 60/40 (AOR), and 80/20 (AOA) total return data sourced from Yahoo Finance (adjusted close). "
        f"All performance figures are shown before taxes and advisory fees, which would reduce returns."
    )
    st.markdown(f'<p class="footer-text">{footnote_dd}</p>', unsafe_allow_html=True)
    newsletter_caption(
        f"Maximum decline from a previous high within each period shown, {_cap_vs(SERIES_ORDER)}, "
        f"data through {_cap_date(latest_date)}. Strategy live since {_cap_date(inception_date)}. "
        + NEWSLETTER_RETURNS_SENTENCES
    )

    st.divider()

    # ================================================================
    # DRAWDOWNS OVER TIME, THE ASYMMETRY, ROLLING 12-MONTH RETURN,
    # RISK VS. RETURN (added October 22, 2026)
    # ================================================================
    _render_guarded("Drawdowns Over Time", render_underwater_section, combined, latest_date)

    st.divider()

    _render_guarded("The Asymmetry", render_capture_section, combined, latest_date)

    st.divider()

    _render_guarded("Rolling 12-Month Return", render_rolling_section, combined, latest_date)

    st.divider()

    _render_guarded("Risk vs. Return", render_risk_return_section, combined, latest_date)

    st.divider()

    # ================================================================
    # 4. ASSET CLASS RETURNS
    # ================================================================
    st.markdown("## Asset Class Returns")

    asset_periods = ["1M", "6M", "1Y", "YTD"]
    selected_asset_period = st.pills(
        "Select period",
        asset_periods,
        default="YTD",
        selection_mode="single",
        key="asset_period",
    )
    if not selected_asset_period:
        selected_asset_period = "YTD"

    if not asset_close.empty:
        ac_start, ac_end = get_period_dates(latest_date, selected_asset_period)
        returns_dict = {}
        for label, ticker in ASSET_CLASS_TICKERS.items():
            if ticker in asset_close.columns:
                ret = compute_return(asset_close[ticker], ac_start, ac_end)
                if ret is not None:
                    returns_dict[label] = ret
        if returns_dict:
            st.plotly_chart(
                build_asset_class_chart(returns_dict),
                use_container_width=True,
                config=chart_config("Asset Class Returns"),
            )
        else:
            st.warning("Could not compute returns for asset classes.")
    else:
        st.warning("Could not load asset class data from Yahoo Finance.")

    # Compute the period range for the footnote independently of the data
    # branch above, so the dates are always available even if asset_close
    # failed to load (ac_start/ac_end are scoped to the if-block).
    af_start, af_end = get_period_dates(latest_date, selected_asset_period)
    # Built from ASSET_CLASS_TICKERS and ASSET_CLASS_FOOTNOTES so the ticker
    # list and notes can never drift from the chart.
    asset_ticker_list = "; ".join(
        f"{label}: {ticker}" for label, ticker in ASSET_CLASS_TICKERS.items()
    )
    asset_notes = "".join(
        " " + ASSET_CLASS_FOOTNOTES[ticker].format(label=label)
        for label, ticker in ASSET_CLASS_TICKERS.items()
        if ticker in ASSET_CLASS_FOOTNOTES
    )
    footnote_asset = (
        f"{selected_asset_period} returns from {af_start.strftime('%m/%d/%Y')} through "
        f"{af_end.strftime('%m/%d/%Y')}, using adjusted close prices from Yahoo Finance, so fund returns "
        f"include reinvested distributions.{asset_notes} Tickers: {asset_ticker_list}."
    )
    st.markdown(f'<p class="footer-text">{footnote_asset}</p>', unsafe_allow_html=True)
    _ac_rets = locals().get("returns_dict") or {}
    _ac_order = (sorted(_ac_rets, key=lambda k: -_ac_rets[k]) if _ac_rets
                 else list(ASSET_CLASS_TICKERS))
    _ac_tickers = [ASSET_CLASS_TICKERS[l] for l in _ac_order if l in ASSET_CLASS_TICKERS]
    _ac_notes = [note for t, note in (("EMXC", "EMXC excludes China"),
                                      ("DXJ", "DXJ hedges out the yen")) if t in _ac_tickers]
    newsletter_caption(
        f"Total returns, {_cap_date(af_start)} through {_cap_date(af_end)}, from Yahoo Finance "
        "adjusted closes. Tickers, top to bottom: " + ", ".join(_ac_tickers) + "."
        + (" " + ", and ".join(_ac_notes) + "." if _ac_notes else "")
        + " Past performance does not guarantee future results."
    )

    st.divider()

    # ================================================================
    # 5. TOTAL RETURN COMPARISON
    # ================================================================
    st.markdown("## Total Return Comparison")

    tr_periods = ["1M", "3M", "6M", "YTD", "1Y", "2025", "2024", "Inception"]
    selected_tr_period = st.pills(
        "Select period",
        tr_periods,
        default="YTD",
        selection_mode="single",
        key="tr_period",
    )
    if not selected_tr_period:
        selected_tr_period = "YTD"

    # Ticker input
    ticker_input = st.text_input(
        "Enter tickers (comma-separated)",
        value="BTC-USD, SPY",
        key="tr_tickers",
        placeholder="e.g. BTC-USD, QQQ, GLD, AAPL",
    )

    # Parse tickers
    raw_tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    # Deduplicate while preserving order
    seen = set()
    tickers = []
    for t in raw_tickers:
        if t not in seen:
            seen.add(t)
            tickers.append(t)

    # Build the list of all labels (AE first if toggled, then tickers)
    include_ae = st.checkbox("Include Asymmetric Edge", value=True, key="tr_include_ae")

    all_labels = []
    if include_ae:
        all_labels.append("Asymmetric Edge")
    all_labels.extend(tickers)

    # Color pickers for each series
    color_map = {}
    if all_labels:
        st.markdown(
            f'<p style="font-size:0.82rem; color:{TEXT_MUTED}; margin-bottom:0.25rem;">Line colors</p>',
            unsafe_allow_html=True,
        )
        # Arrange color pickers in rows of up to 4
        for row_start in range(0, len(all_labels), 4):
            row_labels = all_labels[row_start:row_start + 4]
            cols = st.columns(len(row_labels))
            for i, label in enumerate(row_labels):
                idx = row_start + i
                default_color = COMPARE_PALETTE[idx % len(COMPARE_PALETTE)]
                with cols[i]:
                    color_map[label] = st.color_picker(
                        label,
                        value=default_color,
                        key=f"tr_color_{label}",
                    )

    tr_start, tr_end = get_period_dates(latest_date, selected_tr_period, inception_date)

    if tickers:
        custom_close = load_custom_ticker_data(tuple(tickers), tr_start.strftime("%Y-%m-%d"), tr_end.strftime("%Y-%m-%d"))
    else:
        custom_close = pd.DataFrame()

    # Build series dict for the chart
    tr_series = {}

    if include_ae:
        tr_series["Asymmetric Edge"] = portfolio_series

    for ticker in tickers:
        if not custom_close.empty and ticker in custom_close.columns:
            tr_series[ticker] = custom_close[ticker]

    if tr_series:
        tr_fig = build_total_return_chart(tr_series, tr_start, tr_end, color_map)
        st.plotly_chart(tr_fig, use_container_width=True, config=chart_config("Total Return Comparison"))
    else:
        st.info("Enter one or more valid tickers above to see the comparison chart.")

    footnote_tr = (
        f"Total return measured as percentage change from {tr_start.strftime('%m/%d/%Y')}, the start of "
        f"the selected {selected_tr_period} period, through {tr_end.strftime('%m/%d/%Y')}. "
        f"Ticker data sourced from Yahoo Finance (adjusted close, dividends reinvested). "
        f"Asymmetric Edge returns are anchored to Fidelity's reported time-weighted returns for a personal portfolio. "
        f"All performance figures are shown before taxes and advisory fees."
    )
    st.markdown(f'<p class="footer-text">{footnote_tr}</p>', unsafe_allow_html=True)

    # Bottom footer
    st.markdown(
        f'<p style="text-align:center; color:{TEXT_MUTED}; font-size:0.72rem; margin-top:2rem;">'
        f'asymmetricedge.io &nbsp;&middot;&nbsp; Data refreshed {format_clock(local_now(), with_year=True)} MT'
        f'</p>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
