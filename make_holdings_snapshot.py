"""Build holdings_snapshot.json, the fund look-through data behind the
dashboard's Look-Through Exposure section (added October 31, 2026).

Run it on the PC inside ae-dashboard-deploy before pushing, next to
make_price_snapshot.py:

    python make_holdings_snapshot.py

It fetches every fund the section breaks down from free issuer files (no
sign-in, no paid service), groups each fund's holdings into the section's
themes, and writes holdings_snapshot.json beside this script. The cloud app
reads that committed file, so it never has to reach the issuers itself.

Sources:
  QQQ   Invesco's holdings feed (dng-api.invesco.com) for QQQ's own weights.
        Invesco publishes no sector per stock, so each stock's GICS sector
        comes from the iShares Nasdaq 100 UCITS ETF holdings file, which
        tracks the same index. If Invesco cannot be reached, that iShares
        file supplies the weights too, and the entry says so.
  IWM   iShares latest-holdings.csv (Russell 2000).
  EMXC  iShares latest-holdings.csv (MSCI Emerging Markets ex China).
  HGER  Harbor's HGER page data (Quantix Commodity Index sector weights),
        the same feed as the What HGER Holds panel. The app prefers its own
        live Harbor fetch; this entry is the fallback.

Themes: Information Technology splits into Chips (chip designers, makers and
equipment suppliers, from the CHIP_* lists below) and Software & other tech.
Communication Services is Internet & media; Consumer Discretionary and
Staples are Consumer; Energy and Materials are Energy & materials stocks;
Real Estate and Utilities are Real estate & utilities. Each fund's small
cash, money market and derivatives sleeve (and any holding with no sector)
is spread proportionally across its classified holdings, so every fund's
themes add up to 100%.

A fund that cannot be fetched keeps its entry from the previous snapshot.
With no previous entry it gets the hand-entered late-October 2026 values
from the design session, marked "hand-entered". Prints a PASS/FAIL line per
fund and exits 1 when any fund did not come from a live fetch.
"""
import csv
import io
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "holdings_snapshot.json")
SCHEMA = 1
TOP_N = 40

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

URLS = {
    "QQQ_invesco": ("https://dng-api.invesco.com/cache/v1/accounts/en_US/shareclasses/QQQ/holdings/"
                    "fund?idType=ticker&interval=monthly&productType=ETF"),
    "QQQ_warmup": "https://www.invesco.com/qqq-etf/en/about.html",
    "NDX_ishares": ("https://www.ishares.com/uk/individual/en/products/253741/"
                    "ishares-nasdaq-100-ucits-etf/latest-holdings.csv"),
    "IWM": "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/latest-holdings.csv",
    "EMXC": ("https://www.ishares.com/us/products/288504/"
             "ishares-msci-emerging-markets-ex-china-etf/latest-holdings.csv"),
    "HGER": "https://www.harborcapital.com/page-data/etf/hger/page-data.json",
}

# GICS sector -> theme. Information Technology is split into chips and the
# rest further down; anything else (cash, derivatives, blanks) is "spread".
SECTOR_THEME = {
    "Information Technology": "other_tech",
    "Communication": "internet",
    "Communication Services": "internet",
    "Consumer Discretionary": "consumer",
    "Consumer Staples": "consumer",
    "Health Care": "health",
    "Financials": "financials",
    "Industrials": "industrials",
    "Energy": "energy_mat",
    "Materials": "energy_mat",
    "Real Estate": "re_util",
    "Utilities": "re_util",
}
# Harbor (Quantix) sector -> theme.
QCI_SECTOR_THEME = {
    "Petroleum": "oil", "Natural Gas": "oil", "Energy": "oil",
    "Precious": "gold",
    "Grains And Soybean Products": "agri", "Softs": "agri",
    "LivestockAndDairy": "livestock",
    "Industrial": "ind_metals",
}
QCI_NAMES = {
    "Brent Crude Oil": "Brent crude", "WTI Crude Oil": "WTI crude", "Crude Oil": "WTI crude",
    "Gasoil": "Gasoil", "RBOB Gasoline": "Gasoline", "Heating Oil": "Heating oil",
    "Natural Gas": "Natural gas", "Gold": "Gold", "Silver": "Silver", "Platinum": "Platinum",
    "Palladium": "Palladium", "Corn": "Corn", "Wheat": "Wheat", "Kansas Wheat": "Wheat",
    "Soybeans": "Soybeans", "Soymeal": "Soymeal", "Bean Oil": "Soybean oil", "Cocoa": "Cocoa",
    "Sugar": "Sugar", "Coffee": "Coffee", "Cotton": "Cotton", "Comex Copper": "Copper",
    "Copper": "Copper", "Zinc": "Zinc", "Aluminum": "Aluminum", "Nickel": "Nickel", "Lead": "Lead",
    "Tin": "Tin", "Lean Hogs": "Lean hogs", "Live Cattle": "Live cattle", "Feeder Cattle": "Feeder cattle",
}

# Chips: chip designers, makers and equipment suppliers. Only Information
# Technology holdings are tested, so materials suppliers stay with materials.
CHIP_US = {
    "NVDA", "AVGO", "AMD", "MU", "QCOM", "TXN", "INTC", "AMAT", "LRCX", "KLAC", "ADI", "MRVL",
    "ASML", "ARM", "NXPI", "MCHP", "ON", "GFS", "MPWR", "TER", "ALAB", "SNDK", "SWKS", "QRVO",
    "ENTG", "MKSI", "ONTO", "LSCC", "RMBS", "CRUS", "SLAB", "SMTC", "POWI", "DIOD", "AMKR",
    "FORM", "ACLS", "COHU", "UCTT", "ICHR", "VECO", "PLAB", "KLIC", "AEHR", "AMBA", "MXL",
    "SITM", "CRDO", "MTSI", "ALGM", "WOLF", "NVTS", "INDI", "AOSL", "ACMR", "CAMT", "NVMI",
    "TSEM", "SYNA", "PI", "QUIK", "CEVA", "SKYT", "GSIT", "NVEC", "AXTI", "ATOM", "PXLW",
    "MRAM", "AMBQ", "VLN", "HIMX", "SIMO", "IMOS", "ASX", "UMC", "TSM", "SGH", "NLST",
}
CHIP_TAIWAN = {
    "2330", "2454", "2303", "3711", "2379", "3034", "3443", "3661", "5274", "6415", "2408",
    "5347", "6770", "3105", "2449", "3529", "4966", "3035", "8299", "2337", "2344", "6147",
    "5483", "6488", "3532", "6239", "2441", "6531", "8016", "3006", "2401", "6533", "3374",
    "6643", "8150", "3014", "6202", "4919", "2458", "6182", "3583", "6510", "6223", "3131",
}
CHIP_KOREA = {
    "005930", "005935", "000660", "042700", "058470", "095340", "240810", "036930", "403870",
    "084370", "039030", "000990", "140860", "166090", "089030", "067310", "064760", "108320",
    "319660", "095610", "101490", "131970",
}
CHIP_MALAYSIA = {"0166", "0097", "3867", "0128", "5005"}
CHIP_NAME_WORDS = ("SEMICONDUCTOR", "MICROELECTRONICS", "MICRO ELECTRONICS", "MICRO DEVICES",
                   "MICROCHIP", "SK HYNIX", "SAMSUNG ELECTRONICS")

# Display names for the largest holdings. Keys are US tickers, or local codes
# prefixed with the iShares location. Alphabet's two share classes and
# Samsung's common and preferred shares combine under one name.
DISPLAY = {
    "NVDA": "NVIDIA", "AAPL": "Apple", "MSFT": "Microsoft", "MU": "Micron", "AMZN": "Amazon",
    "AMD": "AMD", "TSLA": "Tesla", "META": "Meta", "SPCX": "SpaceX", "GOOGL": "Alphabet",
    "GOOG": "Alphabet", "AVGO": "Broadcom", "WMT": "Walmart", "INTC": "Intel", "PLTR": "Palantir",
    "COST": "Costco", "CSCO": "Cisco", "AMAT": "Applied Materials", "LRCX": "Lam Research",
    "PANW": "Palo Alto Networks", "TXN": "Texas Instruments", "CRWD": "CrowdStrike",
    "NFLX": "Netflix", "AMGN": "Amgen", "LIN": "Linde", "KLAC": "KLA", "ADI": "Analog Devices",
    "GILD": "Gilead", "SHOP": "Shopify", "SNDK": "Sandisk", "QCOM": "Qualcomm", "MRVL": "Marvell",
    "PEP": "PepsiCo", "STX": "Seagate", "ISRG": "Intuitive Surgical", "TMUS": "T-Mobile US",
    "ASML": "ASML", "WDC": "Western Digital", "VRTX": "Vertex", "SBUX": "Starbucks", "ADP": "ADP",
    "BKNG": "Booking", "MAR": "Marriott", "FTNT": "Fortinet", "ARM": "Arm", "ADBE": "Adobe",
    "CSX": "CSX", "CDNS": "Cadence", "SNPS": "Synopsys", "CEG": "Constellation Energy",
    "MNST": "Monster Beverage", "INTU": "Intuit", "DDOG": "Datadog", "MRNA": "Moderna",
    "CTAS": "Cintas", "MELI": "MercadoLibre", "REGN": "Regeneron", "LITE": "Lumentum",
    "MDLZ": "Mondelez", "CMCSA": "Comcast", "APP": "AppLovin", "ROST": "Ross Stores",
    "DASH": "DoorDash", "ORLY": "O'Reilly", "AEP": "American Electric Power", "HON": "Honeywell",
    "ABNB": "Airbnb", "NXPI": "NXP", "FAST": "Fastenal", "MPWR": "Monolithic Power",
    "FANG": "Diamondback", "BKR": "Baker Hughes", "PCAR": "Paccar", "PDD": "PDD",
    "MSTR": "Strategy", "HONA": "Honeywell Aerospace", "ADSK": "Autodesk", "ALAB": "Astera Labs",
    "XEL": "Xcel Energy", "PYPL": "PayPal", "CCEP": "Coca-Cola Europacific", "KDP": "Keurig Dr Pepper",
    "EXC": "Exelon", "TER": "Teradyne", "IDXX": "Idexx", "ROP": "Roper", "MCHP": "Microchip",
    "TRI": "Thomson Reuters", "FER": "Ferrovial", "NBIS": "Nebius", "PAYX": "Paychex",
    "WDAY": "Workday", "TTWO": "Take-Two", "ODFL": "Old Dominion", "AXON": "Axon",
    "RKLB": "Rocket Lab", "GEHC": "GE HealthCare", "DXCM": "Dexcom", "CRWV": "CoreWeave",
    "CPRT": "Copart", "ALNY": "Alnylam",
    "Taiwan:2330": "TSMC", "Korea (South):005930": "Samsung Electronics",
    "Korea (South):005935": "Samsung Electronics", "Korea (South):000660": "SK hynix",
    "Taiwan:2454": "MediaTek", "Taiwan:2317": "Hon Hai", "Taiwan:2308": "Delta Electronics",
    "Taiwan:3711": "ASE Technology", "Taiwan:2303": "UMC", "Taiwan:2382": "Quanta Computer",
    "Korea (South):009150": "Samsung Electro-Mechanics", "India:HDFCBANK": "HDFC Bank",
    "India:RELIANCE": "Reliance Industries", "India:ICICIBANK": "ICICI Bank", "India:INFY": "Infosys",
    "India:BHARTIARTL": "Bharti Airtel", "India:TCS": "Tata Consultancy Services",
    "Taiwan:2881": "Fubon Financial", "Taiwan:2882": "Cathay Financial", "Taiwan:2891": "CTBC Financial",
}
_SUFFIXES = re.compile(
    r"(\s+(inc|corp|corporation|co|company|ltd|limited|plc|nv|sa|ag|se|holdings?|holding|group|"
    r"class [a-c]|cl [a-c]|adr|ads|non voting pre|non-v|non voting|pref|the|lp|/md|/de))+\.?$",
    re.IGNORECASE)
_KEEP_UPPER = {"AI", "ATM", "BJ", "CBIZ", "CSG", "ESCO", "II", "III", "IT", "LG", "NL", "NV", "SK",
               "UMB", "USA", "US"}


def display_name(name, ticker, location=""):
    """Short display name: the DISPLAY map first, then a cleaned-up issuer name."""
    for key in (f"{location}:{ticker}", ticker):
        if key in DISPLAY:
            return DISPLAY[key]
    text = re.sub(r"\s+", " ", str(name or ticker)).strip()
    if text.isupper():
        words = []
        for w in text.split(" "):
            keep = w in _KEEP_UPPER or not re.search(r"[AEIOUY]", w)
            words.append(w if keep else w.capitalize())
        text = " ".join(words)
    prev = None
    while prev != text:
        prev = text
        text = _SUFFIXES.sub("", text).strip(" ,.")
    return text or str(ticker)


def is_chip(sector, ticker, name, location):
    if sector != "Information Technology":
        return False
    t = str(ticker or "").strip().upper()
    if location == "Taiwan" and t in CHIP_TAIWAN:
        return True
    if location == "Korea (South)" and t in CHIP_KOREA:
        return True
    if location == "Malaysia" and t in CHIP_MALAYSIA:
        return True
    if location not in ("Taiwan", "Korea (South)", "Malaysia") and t in CHIP_US:
        return True
    upper = str(name or "").upper()
    return any(w in upper for w in CHIP_NAME_WORDS)


# ---------------------------------------------------------------- fetching

def http_get(url, json_wanted=False):
    """GET with curl_cffi's browser impersonation (a warmed session), then plain requests."""
    errors = []
    try:
        from curl_cffi import requests as cr
        for imp in ("chrome", "chrome124", "safari17_0"):
            try:
                s = cr.Session(impersonate=imp)
                if "invesco.com" in url:
                    try:
                        s.get(URLS["QQQ_warmup"], timeout=25)
                    except Exception:
                        pass
                r = s.get(url, timeout=30)
                if r.status_code == 200 and r.content:
                    return r.text
                errors.append(f"curl_cffi[{imp}] HTTP {r.status_code}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"curl_cffi[{imp}] {type(e).__name__}: {e}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"curl_cffi unavailable: {e}")
    try:
        import requests
        r = requests.get(url, timeout=30, headers={"User-Agent": UA, "Accept": "*/*"})
        if r.status_code == 200 and r.content:
            return r.text
        errors.append(f"requests HTTP {r.status_code}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"requests {type(e).__name__}: {e}")
    raise RuntimeError("; ".join(errors))


def _num(s):
    s = str(s or "").replace(",", "").replace('"', "").strip()
    if s in ("", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _ishares_as_of(text):
    m = re.search(r'Fund Holdings as of,"?([^"\n]+)"?', text)
    if not m:
        return None
    raw = m.group(1).strip()
    for fmt in ("%b %d, %Y", "%d/%b/%Y", "%d-%b-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_ishares_csv(text):
    """Rows of an iShares holdings CSV (US or UK layout) with market-value weights."""
    text = text.lstrip("\ufeff")
    lines = text.splitlines()
    try:
        head = next(i for i, line in enumerate(lines) if line.startswith("Ticker,"))
    except StopIteration:
        raise RuntimeError("no holdings table in the iShares file (layout changed?)")
    rows = []
    for r in csv.DictReader(io.StringIO("\n".join(lines[head:]))):
        mv = _num(r.get("Market Value"))
        if mv is None or not r.get("Name"):
            continue
        rows.append({
            "ticker": str(r.get("Ticker") or "").strip(),
            "name": str(r.get("Name") or "").strip(),
            "sector": str(r.get("Sector") or "").strip(),
            "asset_class": str(r.get("Asset Class") or "").strip(),
            "location": str(r.get("Location") or "").strip(),
            "mv": mv,
        })
    total = sum(r["mv"] for r in rows)
    if total <= 0 or len(rows) < 20:
        raise RuntimeError(f"iShares file parsed to {len(rows)} rows, total {total}")
    for r in rows:
        r["weight"] = r["mv"] / total * 100.0
    return rows, _ishares_as_of(text)


def build_fund(rows, as_of, source, method="live"):
    """Group holdings into themes, spreading cash and unclassified rows
    proportionally. rows: dicts with ticker, name, sector, location, weight."""
    themes, names, spread, unclassified = {}, {}, 0.0, {}
    for r in rows:
        sector = r.get("sector", "")
        theme = SECTOR_THEME.get(sector)
        is_equity = r.get("asset_class", "Equity") in ("Equity", "", None)
        if theme is None or not is_equity:
            spread += r["weight"]
            if is_equity and sector not in ("Cash and/or Derivatives",):
                unclassified[f"{r['ticker']} {r['name']}".strip()] = r["weight"]
            continue
        if theme == "other_tech" and is_chip(sector, r["ticker"], r["name"], r.get("location", "")):
            theme = "semis"
        themes[theme] = themes.get(theme, 0.0) + r["weight"]
        disp = display_name(r["name"], r["ticker"], r.get("location", ""))
        cur = names.setdefault(disp, {"ticker": r["ticker"], "theme": theme, "weight": 0.0})
        cur["weight"] += r["weight"]
    classified = sum(themes.values())
    if classified <= 0:
        raise RuntimeError("no classified holdings")
    scale = 100.0 / classified
    top = sorted(names.items(), key=lambda kv: -kv[1]["weight"])[:TOP_N]
    return {
        "as_of": as_of,
        "source": source,
        "method": method,
        "holdings_count": len(names),
        "cash_and_other_pct": round(100.0 - classified, 4),
        "themes": {k: round(v * scale, 4) for k, v in sorted(themes.items(), key=lambda kv: -kv[1])},
        "top": [[n, d["ticker"], d["theme"], round(d["weight"] * scale, 4)] for n, d in top],
        "_unclassified": unclassified,
    }


def fetch_ishares(ticker):
    rows, as_of = parse_ishares_csv(http_get(URLS[ticker]))
    return build_fund(rows, as_of, f"iShares {ticker} holdings file ({URLS[ticker]})")


def fetch_qqq():
    """QQQ weights from Invesco, sectors from the same-index iShares file."""
    ndx_rows, ndx_as_of = parse_ishares_csv(http_get(URLS["NDX_ishares"]))
    sector_of = {r["ticker"]: r["sector"] for r in ndx_rows if r["ticker"]}
    try:
        payload = json.loads(http_get(URLS["QQQ_invesco"], json_wanted=True))
        rows = []
        for h in payload.get("holdings") or []:
            w = h.get("percentageOfTotalNetAssets")
            if w is None:
                continue
            code = str(h.get("securityTypeCode") or "")
            t = str(h.get("ticker") or "").strip()
            equity = code in ("COM", "ADR", "DRNY", "REIT", "PFD")
            rows.append({
                "ticker": t, "name": str(h.get("issuerName") or t),
                "sector": sector_of.get(t, "") if equity else "Cash and/or Derivatives",
                "asset_class": "Equity" if equity else "Cash", "location": "United States",
                "weight": float(w),
            })
        total = sum(r["weight"] for r in rows)
        if not 95.0 <= total <= 105.0 or len(rows) < 80:
            raise RuntimeError(f"Invesco holdings sum to {total:.2f}% over {len(rows)} rows")
        as_of = str(payload.get("effectiveDate") or payload.get("effectiveBusinessDate") or "")[:10]
        source = ("Invesco QQQ holdings (dng-api.invesco.com); GICS sectors from the iShares "
                  "Nasdaq 100 UCITS ETF holdings file, which tracks the same index")
        fund = build_fund(rows, as_of, source)
        fund["sector_file_as_of"] = ndx_as_of
        return fund
    except Exception as e:  # noqa: BLE001
        print(f"  QQQ: Invesco feed failed ({e}); using the iShares Nasdaq 100 file's weights")
        source = ("iShares Nasdaq 100 UCITS ETF holdings file (same index as QQQ; Invesco's feed "
                  f"was unavailable) ({URLS['NDX_ishares']})")
        return build_fund(ndx_rows, ndx_as_of, source)


def _find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find_key(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_key(v, key)
            if found is not None:
                return found
    return None


def fetch_hger():
    payload = json.loads(http_get(URLS["HGER"], json_wanted=True))
    sectors = _find_key(payload, "etfCommodityIndexSectors")
    if not sectors:
        raise RuntimeError("Harbor page data has no etfCommodityIndexSectors")
    themes, names, as_of = {}, {}, None
    for sector in sectors:
        as_of = as_of or str(sector.get("calendarDate") or "")[:10]
        theme = QCI_SECTOR_THEME.get(str(sector.get("sectorName") or "").strip(), "commod_other")
        for c in sector.get("commodities") or []:
            w = float(c.get("weight") or 0) * 100.0
            commodity = str(c.get("commodityName") or "").strip()
            themes[theme] = themes.get(theme, 0.0) + w
            disp = QCI_NAMES.get(commodity, commodity.capitalize())
            cur = names.setdefault(disp, {"ticker": str(c.get("ticker") or "").strip(), "theme": theme,
                                          "weight": 0.0})
            cur["weight"] += w
    total = sum(themes.values())
    if not 95.0 <= total <= 105.0:
        raise RuntimeError(f"Harbor weights sum to {total:.2f}%")
    scale = 100.0 / total
    top = sorted(names.items(), key=lambda kv: -kv[1]["weight"])[:TOP_N]
    return {
        "as_of": as_of, "method": "live",
        "source": f"Harbor HGER page data, Quantix Commodity Index sector weights ({URLS['HGER']})",
        "holdings_count": len(names), "cash_and_other_pct": 0.0,
        "themes": {k: round(v * scale, 4) for k, v in sorted(themes.items(), key=lambda kv: -kv[1])},
        "top": [[n, d["ticker"], d["theme"], round(d["weight"] * scale, 4)] for n, d in top],
        "_unclassified": {},
    }


# ------------------------------------------------- hand-entered fallback
# Late-October 2026 issuer and index pages, entered by hand during the
# October 30-31, 2026 design session (data.py). Used only for a fund with no
# live fetch and no previous snapshot entry.
HAND_SOURCE = ("Hand-entered from late-October 2026 issuer and index pages during the October 30-31, "
               "2026 design session (data.py)")
HAND_AS_OF = "2026-10-30"
HAND = {
    "QQQ": ({"semis": 28.65, "other_tech": 31.68, "internet": 12.59, "consumer": 15.63, "health": 3.79,
             "financials": 0.19, "industrials": 5.11, "energy_mat": 1.37, "re_util": 1.01},
            [("Apple", "AAPL", "other_tech", 12.49), ("NVIDIA", "NVDA", "semis", 12.24),
             ("Microsoft", "MSFT", "other_tech", 9.62), ("Alphabet", "GOOGL", "internet", 8.54),
             ("Amazon", "AMZN", "consumer", 6.44), ("SpaceX", "SPCX", "industrials", 4.54),
             ("Tesla", "TSLA", "consumer", 3.92), ("Meta", "META", "internet", 3.90),
             ("Broadcom", "AVGO", "semis", 3.86), ("Micron", "MU", "semis", 2.49),
             ("Walmart", "WMT", "consumer", 2.43), ("AMD", "AMD", "semis", 2.05), ("ASML", "ASML", "semis", 1.50)]),
    "IWM": ({"other_tech": 14.55, "internet": 2.33, "consumer": 11.17, "health": 20.93, "financials": 17.97,
             "industrials": 13.29, "energy_mat": 10.64, "re_util": 9.11},
            [("Twist Bioscience", "TWST", "health", 0.43)]),
    "EMXC": ({"semis": 41.10, "other_tech": 11.12, "internet": 2.81, "consumer": 6.08, "health": 1.94,
              "financials": 18.68, "industrials": 6.36, "energy_mat": 9.29, "re_util": 2.63},
             [("TSMC", "2330", "semis", 19.42), ("Samsung Electronics", "005930", "semis", 10.56),
              ("SK hynix", "000660", "semis", 7.33), ("MediaTek", "2454", "semis", 2.25),
              ("Delta Electronics", "2308", "other_tech", 1.17), ("Hon Hai", "2317", "other_tech", 0.98)]),
    "HGER": ({"oil": 43.45, "gold": 17.65, "ind_metals": 5.82, "agri": 22.27, "livestock": 10.79},
             [("Brent crude", "CO", "oil", 18.23), ("Gold", "GC", "gold", 17.65), ("Heating oil", "HO", "oil", 13.29),
              ("Gasoil", "QS", "oil", 11.93), ("Lean hogs", "LH", "livestock", 5.41),
              ("Live cattle", "LC", "livestock", 5.38), ("Cocoa", "CC", "agri", 3.64), ("Sugar", "SB", "agri", 2.74),
              ("Coffee", "KC", "agri", 2.61), ("Soybeans", "S", "agri", 2.51)]),
}


def hand_entry(ticker):
    themes, top = HAND[ticker]
    total = sum(themes.values())
    scale = 100.0 / total
    return {
        "as_of": HAND_AS_OF, "source": HAND_SOURCE, "method": "hand-entered",
        "holdings_count": None, "cash_and_other_pct": None,
        "themes": {k: round(v * scale, 4) for k, v in themes.items()},
        "top": [[n, t, th, round(w * scale, 4)] for n, t, th, w in top],
    }


FETCHERS = {"QQQ": fetch_qqq, "IWM": lambda: fetch_ishares("IWM"),
            "EMXC": lambda: fetch_ishares("EMXC"), "HGER": fetch_hger}


def main():
    previous = {}
    if os.path.exists(OUT_PATH):
        try:
            with open(OUT_PATH, "r", encoding="utf-8-sig") as f:
                previous = (json.load(f) or {}).get("funds", {}) or {}
        except Exception as e:  # noqa: BLE001
            print("previous snapshot unreadable:", e)
    funds, all_live = {}, True
    for ticker, fetch in FETCHERS.items():
        try:
            entry = fetch()
            unclassified = entry.pop("_unclassified", {})
            t = entry["themes"]
            print(f"PASS {ticker}: as of {entry['as_of']}, {entry['holdings_count']} holdings, "
                  f"cash and other spread {entry['cash_and_other_pct']:.2f}%")
            print("     themes: " + ", ".join(f"{k} {v:.2f}" for k, v in t.items()))
            print("     top: " + ", ".join(f"{n} {w:.2f}" for n, _t, _th, w in entry["top"][:8]))
            if unclassified:
                big = sorted(unclassified.items(), key=lambda kv: -kv[1])[:5]
                print("     no sector, spread: " + ", ".join(f"{k} {v:.3f}" for k, v in big))
            funds[ticker] = entry
        except Exception as e:  # noqa: BLE001
            all_live = False
            old = previous.get(ticker)
            if old and old.get("method") == "live":
                old = dict(old)
                old["method"] = "previous"
                funds[ticker] = old
                print(f"FAIL {ticker}: {e}. Kept the previous snapshot's entry (as of {old.get('as_of')}).")
            elif old:
                funds[ticker] = old
                print(f"FAIL {ticker}: {e}. Kept the previous entry ({old.get('method')}, as of {old.get('as_of')}).")
            else:
                funds[ticker] = hand_entry(ticker)
                print(f"FAIL {ticker}: {e}. Wrote the hand-entered values (as of {HAND_AS_OF}).")
    out = {
        "schema": SCHEMA,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "generated_by": "make_holdings_snapshot.py",
        "note": ("Theme weights are percent of each fund and add to 100; each fund's cash, money market and "
                 "derivatives sleeve is spread proportionally across its holdings. top lists the largest "
                 "holdings as [display name, ticker, theme, percent of fund] on the same basis."),
        "funds": funds,
    }
    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, OUT_PATH)
    print(f"WROTE {OUT_PATH} ({len(funds)} funds)")
    return 0 if all_live else 1


if __name__ == "__main__":
    sys.exit(main())
