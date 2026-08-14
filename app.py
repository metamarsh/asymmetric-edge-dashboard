import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta
import os
import json
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
    "EM ex-China": "EMXC",
    "Japan (Hedged)": "DXJ",
    "S&P 500": "SPY",
    "Nasdaq-100": "QQQ",
    "Russell 2000": "IWM",
    "U.S. Dollar": "DX-Y.NYB",
    "LT Treasuries": "TLT",
    "Crude Oil": "CL=F",
    "Bitcoin": "BTC-USD",
}

SERIES_ORDER = ["AsymEdge", "80/20", "60/40", "S&P 500"]

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
    now = datetime.now()
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
#   3. Stooq, which needs no API key and sits on a different network path
#      than Yahoo. Stooq closes are split- but NOT dividend-adjusted, so they
#      are only ever chained onto the end of an adjusted series as returns.
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


_STOOQ_OVERRIDES = {
    "CL=F": "cl.f",
    "BTC-USD": "btcusd",
    "DX-Y.NYB": None,
}


def _stooq_symbol(ticker: str):
    if ticker in _STOOQ_OVERRIDES:
        return _STOOQ_OVERRIDES[ticker]
    if any(ch in ticker for ch in ("=", "^")):
        return None
    return ticker.lower().replace(".", "-") + ".us"


def _stooq_closes(tickers, fetch_start, fetch_end) -> dict:
    """Last-resort daily closes from Stooq. Returns {ticker: Series}."""
    collected = {}
    d1 = pd.Timestamp(fetch_start).strftime("%Y%m%d")
    d2 = pd.Timestamp(fetch_end).strftime("%Y%m%d")
    for t in dict.fromkeys(tickers):
        sym = _stooq_symbol(t)
        if not sym:
            continue
        url = "https://stooq.com/q/d/l/?s=%s&d1=%s&d2=%s&i=d" % (sym, d1, d2)
        try:
            df = pd.read_csv(url)
        except Exception:
            continue
        if df is None or df.empty or "Date" not in df.columns or "Close" not in df.columns:
            continue
        try:
            s = pd.Series(df["Close"].values, index=pd.to_datetime(df["Date"]))
        except Exception:
            continue
        s = _clean_series(s)
        if len(s):
            collected[t] = s
    return collected


def _chain_onto(base: pd.Series, extra: pd.Series, ratio_link: bool) -> pd.Series:
    """Extend ``base`` with the part of ``extra`` that falls after base's end.

    With ratio_link=True the two series sit on different adjustment bases
    (Stooq is not dividend-adjusted), so ``extra`` is converted into a return
    chain off its own overlapping value rather than being used at face value.
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
    not return, and Stooq tops up the most recent days when Yahoo is rate
    limited. Returns an empty DataFrame rather than raising if all three fail.
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

    # Anything Yahoo would not give us gets a Stooq top-up so the most recent
    # session is not missing just because the host is rate limited.
    stale = [t for t in tickers if t not in live]
    if stale:
        for t, s in _stooq_closes(stale, fetch_start, fetch_end).items():
            if t in series:
                series[t] = _chain_onto(series[t], s, ratio_link=True)
            else:
                series[t] = s

    if not series:
        return pd.DataFrame()

    df = pd.DataFrame(series).sort_index()
    df = df[(df.index >= lo) & (df.index <= hi)]
    return df


@st.cache_data(ttl=3600)
def load_benchmark_data(start_date: str, end_date: str):
    return _fetch_closes(list(BENCHMARK_TICKERS.values()), start_date, end_date)


@st.cache_data(ttl=3600)
def load_asset_class_data(start_date: str, end_date: str):
    return _fetch_closes(list(ASSET_CLASS_TICKERS.values()), start_date, end_date)


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
            name=name,
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
        xaxis=dict(type="category", tickfont=dict(size=20, color=TEXT_SECONDARY, weight=700)),
        legend=dict(
            orientation="h", yanchor="top", y=-0.18,
            xanchor="center", x=0.5,
            font=dict(size=22, color=TEXT_SECONDARY, weight=500),
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
            "name": name,
            "value": final_val,
            "pct": pct_return,
            "color": rgba,
            "value_text": f"${final_val:,.0f} ({pct_return:.1f}%)",
        })

        fig.add_trace(go.Scatter(
            x=normed.index,
            y=normed.values,
            mode="lines",
            name=name,
            line=dict(color=rgba, width=4 if name == "AsymEdge" else 3),
            hovertemplate="%{x|%b %d, %Y}<br>$%{y:,.0f}<extra>" + name + "</extra>",
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
        ITEM_GAP_PX = 140         # space between adjacent legend items
        FIG_W_PX = 1060           # typical chart width inside the 1100px-max container
        NAME_CHAR_PX = 12.1       # 22pt DM Sans medium, average char width
        VALUE_CHAR_PX = 8.6       # 16pt DM Sans regular, average char width

        # Vertical positions in paper-y. y_name is further from the plot
        # than the prior version to leave a comfortable gap between the
        # x-axis date labels and the legend.
        y_name = -0.16
        y_value = -0.24

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
                font=dict(size=22, color=TEXT_SECONDARY,
                          family="DM Sans, sans-serif", weight=500),
                xanchor="left", yanchor="middle",
            ))
            # Value + percentage, centered horizontally under the name's center
            legend_annotations.append(dict(
                xref="paper", yref="paper",
                x=name_center_x, y=y_value,
                text=item["value_text"],
                showarrow=False,
                font=dict(size=16, color=TEXT_MUTED,
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
        margin=dict(t=15, b=140, l=70, r=30),
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
            name=name,
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
        xaxis=dict(type="category", tickfont=dict(size=20, color=TEXT_SECONDARY, weight=700)),
        legend=dict(
            orientation="h", yanchor="top", y=-0.18,
            xanchor="center", x=0.5,
            font=dict(size=22, color=TEXT_SECONDARY, weight=500),
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

    header_cells = "".join(f"<th>{name}</th>" for name in series_order)

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


def build_allocation_table(rows):
    """Build a Plotly table figure for the current allocation so it can be
    exported as PNG via the toolbar download button.

    rows is the auto-derived current allocation (from actual holdings at the
    most recent rebalance). There is no hardcoded fallback, callers invoke this
    only when rows is available.
    """
    header_values = ["Asset", "Ticker", "Weight", "Purpose"]
    assets = [f'{row["emoji"]}  {row["asset"]}' for row in rows]
    tickers = [row["ticker"] for row in rows]
    weights = [row["weight"] for row in rows]
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
# The INSERTION ORDER of this dict is the canonical sort order used across
# all three allocation tables (Current, Last Rebalance, Next). Assets are
# grouped by category, matching asset_universe.json: U.S. equities, then
# International, then Commodities, then Crypto, then Defensive. To add a new
# asset, insert it in the slot for its category so the tables stay sorted.
ASSET_CATALOG = {
    # U.S. equities
    "QQQ":  {"asset": "Nasdaq-100",              "emoji": "\U0001F4BB", "purpose": "Growth from U.S. tech leaders"},
    "IWM":  {"asset": "Russell 2000",            "emoji": "\U0001F537", "purpose": "Small-cap U.S. exposure"},
    # International
    "EMXC": {"asset": "EM ex-China",             "emoji": "\U0001F30F", "purpose": "Emerging markets ex-China"},
    "DXJ":  {"asset": "Japan Hedged Equity",     "emoji": "\u26E9\uFE0F", "purpose": "Japan equity, currency-hedged"},
    # Commodities
    "GLD":  {"asset": "Gold",                    "emoji": "\U0001F7E8", "purpose": "Gold, store of value"},
    "HGER": {"asset": "Active Commodities",      "emoji": "\U0001F3ED", "purpose": "Broad commodities, inflation hedge"},
    # Crypto
    "IBIT": {"asset": "Bitcoin",                 "emoji": "\U0001F7E0", "purpose": "Bitcoin spot exposure"},
    # Defensive
    "BIL":  {"asset": "Short-Term Treasuries",   "emoji": "\U0001F4B5", "purpose": "Ultra-short Treasuries, cash proxy"},
    "TLT":  {"asset": "Long-Term Treasuries",    "emoji": "\U0001F3E6", "purpose": "Long-duration U.S. Treasuries"},
    "BTAL": {"asset": "Defensive Equity",        "emoji": "\U0001F6E1\uFE0F", "purpose": "Market-neutral, tail-risk hedge"},
}


def canonical_order(tickers):
    """Sort tickers by ASSET_CATALOG insertion order.

    Unknown tickers appear at the end in alphabetical order. Used so every
    allocation table on the dashboard lists assets in the same category-
    grouped order.
    """
    catalog = list(ASSET_CATALOG.keys())
    known = [t for t in catalog if t in tickers]
    unknown = sorted([t for t in tickers if t not in catalog])
    return known + unknown

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
# checks). The defensive sleeve and T-bills/cash fade toward gray so
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
    ("crypto", "Crypto",            "#9D91CE"),  # muted violet
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

    One 100% stacked bar per month, computed from actual end-of-day holdings
    on the last trading day of each month (the rebalance close), the same
    source the Current Allocation table uses. The current open month appears
    as the final bar, computed at the latest trading day in the data. The
    cash sleeve comes from reconstructed_account_value.csv when available.

    Returns a Plotly figure, or None if there is no usable data.
    """
    if holdings_values.empty:
        return None
    hv = holdings_values[holdings_values.index >= pd.Timestamp(ALLOC_HISTORY_START)]
    hv = hv.fillna(0.0)
    if hv.empty:
        return None

    # Last trading day of each calendar month (includes the open month's
    # latest day, so the chart always shows the current allocation too).
    month_rows = hv.groupby([hv.index.year, hv.index.month]).tail(1)
    totals = _load_reconstructed_totals()

    cat_keys = [k for k, _label, _color in ALLOC_HISTORY_CATEGORIES]
    labels = []
    weights = {k: [] for k in cat_keys}   # percent values per month
    details = {k: [] for k in cat_keys}   # per-month ticker breakdown strings

    for date, row in month_rows.iterrows():
        securities_total = float(row.sum())
        total = securities_total
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
        for ticker, value in row.items():
            value = float(value)
            if value <= 0:
                continue
            key = ALLOC_HISTORY_TICKER_CATEGORY.get(ticker, "us")
            w = value / total
            month_w[key] += w
            month_parts[key].append((ticker, w))
        month_w["cash"] += cash_dollars / total

        labels.append(date.strftime("%b-%y"))
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
    Current Allocation table style."""

    header_values = ["Asset", "Ticker", "Weight", "Purpose"]
    assets = [f'{row["emoji"]}  {row["asset"]}' for row in rows]
    tickers = [row["ticker"] for row in rows]
    weights = [row["weight"] for row in rows]
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


def find_rebalance_dates(holdings_values):
    """Return rebalance dates from the holdings_values index.

    The Asymmetric Edge strategy rebalances on the last trading day of each
    calendar month, regardless of how much the targets shift versus the
    prior month. This function returns the last trading day of every month
    that has been fully completed in the dataset, sorted most recent first.

    A month is treated as completed when the data extends past its last
    trading day (i.e., the next month has begun). The current open month,
    whose rebalance has not happened yet, is excluded. This is robust to
    months where the new targets are similar to the old ones, which a
    turnover-threshold approach would miss.
    """
    if holdings_values.empty:
        return []
    idx = holdings_values.index
    # Last trading day of each calendar month present in the data
    month_ends = idx.to_series().groupby([idx.year, idx.month]).max()
    # Keep only month-ends that have at least one trading day after them
    completed = [d for d in month_ends.tolist() if (idx > d).any()]
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

    return {
        "period_start_date": period_start,
        "drift_date": drift_date,
        "start_weights": start_weights,
        "drift_weights": drift_weights,
    }


def derive_current_allocation(holdings_values):
    """Derive Current Allocation rows from actual holdings at the most recent
    rebalance close, the same source the Allocation Drift table uses for its
    Month Start column.

    Returns (rows, rebalance_date). rows is a list of allocation-row dicts
    (emoji, asset, ticker, weight, purpose) with weight as a 2-decimal percent
    string. Returns (None, None) if holdings data is unavailable, so callers
    can show an error instead of stale numbers.

    By reusing the same start_weights, threshold, ordering, and number
    formatting as build_drift_table, the Current Allocation table is
    guaranteed to match the drift table's Month Start column exactly.
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

    ordered = canonical_order(list(union))

    asset_cells, start_cells, drift_cells, target_cells, trade_cells = [], [], [], [], []
    for ticker in ordered:
        info = ASSET_CATALOG.get(ticker, {"asset": ticker, "emoji": ""})
        start_w = start.get(ticker, 0.0) * 100.0
        drift_w = drift.get(ticker, 0.0) * 100.0
        target_w = new_target_map.get(ticker, 0.0)
        trade = target_w - drift_w

        asset_cells.append(f'{info["emoji"]}  {info["asset"]} ({ticker})')
        start_cells.append(f"{start_w:.2f}%")
        drift_cells.append(f"{drift_w:.2f}%")

        if target_is_set:
            target_cells.append(f"{target_w:.2f}%")
            is_new = start_w < 0.005 and drift_w < 0.005 and target_w > 0
            is_exit = target_w < 0.005 and drift_w >= 0.005
            if is_new:
                trade_cells.append(f"+{target_w:.2f}% (new)")
            elif is_exit:
                trade_cells.append(f"-{drift_w:.2f}% (exit)")
            else:
                trade_sign = "+" if trade > 0 else ""
                trade_cells.append(f"{trade_sign}{trade:.2f}%")
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
    # This table is laid out at width=860 rather than the 790 used by the
    # other tables because five columns at those minimums do not fit in 790.
    # The container is 1100px wide, so 860 still has room.
    # If any cell or header wraps to a second line, the table renders taller
    # than the figure height set below and the final row gets clipped, so
    # these widths and that height calculation have to stay in sync.
    fig = go.Figure(data=[go.Table(
        columnwidth=[230, 130, 90, 115, 135],
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
        width=860,
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

    # Yahoo first, then the committed snapshot, then Stooq. Partial results are
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
        close_map.update(_stooq_closes(still_missing, fetch_start, fetch_end))

    if not close_map:
        return None, "no price data from Yahoo, snapshot, or Stooq"

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
    performers stand out at a glance.
    """
    rows = result["rows"]
    ordered = canonical_order(list(rows.keys()))

    asset_cells, ticker_cells = [], []
    start_cells, ret_cells, cur_cells = [], [], []
    ret_colors = []
    for ticker in ordered:
        info = ASSET_CATALOG.get(ticker, {"asset": ticker, "emoji": ""})
        r = rows[ticker]
        ret_pct = r["ret"] * 100.0
        asset_cells.append(f'{info["emoji"]}  {info["asset"]}')
        ticker_cells.append(ticker)
        start_cells.append(f'{r["start_w"] * 100.0:.2f}%')
        ret_sign = "+" if ret_pct >= 0 else ""
        ret_cells.append(f"{ret_sign}{ret_pct:.2f}%")
        cur_cells.append(f'{r["drift_w"] * 100.0:.2f}%')
        ret_colors.append(GAIN_GREEN if ret_pct >= 0 else LOSS_RED)

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
    # committed snapshot, then Stooq for anything still missing. A ticker with
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
        close_map.update(_stooq_closes(still_missing, fetch_start, fetch_end))

    if not close_map:
        return empty, "no price data from Yahoo, snapshot, or Stooq"

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
    days_stale = (datetime.now().date() - last_date.date()).days

    # Decide which workflow the user is likely going to need based on the
    # calendar. If a full calendar month has elapsed since the last data
    # point, recommend Workflow 2 (permanent pipeline refresh). Otherwise
    # the open month is still in progress and Workflow 1 (quick MTD extend)
    # is the typical move. This is a soft recommendation, not a hard rule.
    today = datetime.now().date()
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
                value=datetime.now().date(),
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
            'cd "C:\\Users\\tyler\\OneDrive\\Asymmetric Edge\\Portfolio Hist Val Reconstruction"\n'
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
            'cd "C:\\Users\\tyler\\OneDrive\\Asymmetric Edge\\Portfolio Hist Val Reconstruction"\n'
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
                {"name": "Japan hedged", "ticker": "DXJ"},
                {"name": "EM ex-China", "ticker": "EMXC"},
            ],
        },
        {
            "name": "Commodities",
            "visible": True,
            "color_bg": "#F4E5C5",
            "color_text": "#7E4A0A",
            "assets": [
                {"name": "Gold", "ticker": "GLD"},
                {"name": "All-weather", "ticker": "HGER"},
            ],
        },
        {
            "name": "Crypto",
            "visible": True,
            "color_bg": "#E2DDF0",
            "color_text": "#443D7F",
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


def build_asset_universe_chart(universe):
    """Build a Plotly figure that renders the asset universe grid.

    Uses pixel-based coordinates (xaxis 0 to WIDTH, yaxis HEIGHT to 0 so
    y=0 sits at the top) so font sizes, card dimensions, and the rounded-
    corner radius stay consistent between the on-screen render and the PNG
    export from Plotly's toolbar download button.

    Plotly shape rectangles don't natively support rounded corners, so each
    card is drawn as an SVG path with quadratic Bezier curves at the four
    corners. Card backgrounds sit on layer='below' so the text annotations
    render cleanly on top.
    """
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

    HEIGHT = TOP_PAD + n_rows * ROW_HEIGHT + (n_rows - 1) * ROW_GAP + BOT_PAD

    shapes = []
    annotations = []

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
            font=dict(size=15, color="#4D4D48", family="DM Sans, sans-serif"),
        ))

        assets = cat.get("assets", [])
        n_assets = len(assets)
        bg = cat.get("color_bg", "#E8E4DA")
        txt = cat.get("color_text", "#4A463D")

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

            r = CORNER_RADIUS
            x0, y0 = card_left, row_top
            x1, y1 = card_right, row_bottom
            path = (
                f"M {x0+r},{y0} L {x1-r},{y0} "
                f"Q {x1},{y0} {x1},{y0+r} L {x1},{y1-r} "
                f"Q {x1},{y1} {x1-r},{y1} L {x0+r},{y1} "
                f"Q {x0},{y1} {x0},{y1-r} L {x0},{y0+r} "
                f"Q {x0},{y0} {x0+r},{y0} Z"
            )
            shapes.append(dict(
                type="path", path=path,
                fillcolor=bg, line=dict(width=0),
                layer="below",
            ))

            card_center_x = (card_left + card_right) / 2

            # Asset name above center, medium weight to match the HTML version
            annotations.append(dict(
                x=card_center_x, y=row_center_y - 6,
                text=asset.get("name", ""),
                showarrow=False,
                xanchor="center", yanchor="middle",
                font=dict(size=15, color=txt, family="DM Sans, sans-serif", weight=500),
            ))
            # Ticker below name at 70% opacity, mirroring the HTML version
            annotations.append(dict(
                x=card_center_x, y=row_center_y + 14,
                text=asset.get("ticker", ""),
                showarrow=False,
                xanchor="center", yanchor="middle",
                font=dict(size=12, color=txt, family="DM Sans, sans-serif"),
                opacity=0.7,
            ))

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
    fig = build_asset_universe_chart(universe)
    au_config = chart_config("Asset Universe", static=True)
    _, center, _ = st.columns([1, 6, 1])
    with center:
        st.plotly_chart(fig, use_container_width=False, config=au_config)

    footnote_au = (
        "Current asset universe used by the Asymmetric Edge strategy. "
        "Holdings rotate based on regime signals and are rebalanced as market conditions evolve."
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
        st.session_state["upd_as_of"] = datetime.now().date()
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
        f'Refreshed {datetime.now().strftime("%b %d, %I:%M %p")} &nbsp;&middot;&nbsp; '
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
            f"All figures are pre-tax, pre-fee, and pre-transaction-cost."
        )
        st.markdown(f'<p class="footer-text">{footnote_summary}</p>', unsafe_allow_html=True)

    st.divider()

    # Load asset class data once
    asset_start = (pd.Timestamp(latest_date) - timedelta(days=400)).strftime("%Y-%m-%d")
    asset_close = load_asset_class_data(asset_start, latest_date.strftime("%Y-%m-%d"))

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

    # Sort by the same canonical order used by Current Allocation and
    # Allocation Drift so all three tables list assets identically.
    if display_rows:
        display_tickers = [r["ticker"] for r in display_rows]
        order = canonical_order(display_tickers)
        order_index = {t: i for i, t in enumerate(order)}
        display_rows = sorted(display_rows, key=lambda r: order_index.get(r["ticker"], len(order)))

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
                "Each bar shows the mix at that month's final trading-day close (the "
                "rebalance close), computed from the same reconstructed end-of-day "
                "holdings that drive the Current Allocation table, so it refreshes "
                "automatically whenever the pipeline regenerates holdings_daily_values.csv. "
                "The last bar is the current open month at the latest trading day in the "
                "data. <b>T-bills &amp; Cash</b> combines BIL, money-market positions, and "
                "uninvested cash. Hover a bar to see the exact weights and the underlying "
                "tickers inside each asset class. Holdings and weights are subject to "
                "change based on regime signals and market conditions."
            )
            st.markdown(f'<p class="footer-text">{footnote_alloc_history}</p>', unsafe_allow_html=True)

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
        f"All performance figures are shown before taxes, advisory fees, and transaction costs, which would reduce returns."
    )
    st.markdown(f'<p class="footer-text">{footnote}</p>', unsafe_allow_html=True)

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
                st.toggle(name, key=f"growth_toggle_{name}")

    footnote_growth = (
        f"Growth of $10,000 invested on {start_g.strftime('%m/%d/%Y')}, the start of the selected "
        f"{selected_growth} period, through {end_g.strftime('%m/%d/%Y')} (total return, dividends reinvested). "
        f"Asymmetric Edge data anchored to Fidelity's reported monthly time-weighted returns for a personal portfolio. "
        f"S&P 500 (SPY), 60/40 (AOR), and 80/20 (AOA) total return data sourced from Yahoo Finance (adjusted close). "
        f"All performance figures are shown before taxes, advisory fees, and transaction costs, which would reduce returns."
    )
    st.markdown(f'<p class="footer-text">{footnote_growth}</p>', unsafe_allow_html=True)

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
        f"All performance figures are shown before taxes, advisory fees, and transaction costs, which would reduce returns."
    )
    st.markdown(f'<p class="footer-text">{footnote_dd}</p>', unsafe_allow_html=True)

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
                build_asset_class_chart(
                    returns_dict,
                    periods=asset_periods,
                    selected_period=selected_asset_period,
                ),
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
    footnote_asset = (
        f"{selected_asset_period} total returns from {af_start.strftime('%m/%d/%Y')} through "
        f"{af_end.strftime('%m/%d/%Y')}, using adjusted close prices (dividends reinvested) from Yahoo Finance. "
        f"Tickers: GLD (Gold), EMXC (EM ex-China), DXJ (Japan, Hedged), SPY (S&P 500), QQQ (Nasdaq-100), "
        f"IWM (Russell 2000), DX-Y.NYB (U.S. Dollar Index), TLT (LT Treasuries), CL=F (Crude Oil), BTC-USD (Bitcoin)."
    )
    st.markdown(f'<p class="footer-text">{footnote_asset}</p>', unsafe_allow_html=True)

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
    include_ae = st.checkbox("Include AsymEdge", value=True, key="tr_include_ae")

    all_labels = []
    if include_ae:
        all_labels.append("AsymEdge")
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
        tr_series["AsymEdge"] = portfolio_series

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
        f"All performance figures are shown before taxes, advisory fees, and transaction costs."
    )
    st.markdown(f'<p class="footer-text">{footnote_tr}</p>', unsafe_allow_html=True)

    # Bottom footer
    st.markdown(
        f'<p style="text-align:center; color:{TEXT_MUTED}; font-size:0.72rem; margin-top:2rem;">'
        f'asymmetricedge.io &nbsp;&middot;&nbsp; Data refreshed {datetime.now().strftime("%b %d, %Y %I:%M %p")}'
        f'</p>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
