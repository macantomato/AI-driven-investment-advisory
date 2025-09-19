import os
import finnhub
from datetime import datetime, timedelta, timezone
import math

API_BASE = "https://finnhub.io/api/v1"
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
if not FINNHUB_API_KEY:
    raise SystemExit("Set FINNHUB_API_KEY env variable first")

finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)


def fetch_finnhub_recommendation(ticker: str):
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {}
    try:
        records = finnhub_client.recommendation_trends(symbol=symbol) or []
        return records
    except Exception:
        return []
    
def fetch_company_news(ticker: str, days: int = 30, limit: int = 365, ) -> list[dict]:
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return []
    now = datetime.now(timezone.utc).date()  
    start = now - timedelta(days=max(1, min(days, 365)))
    try:
        news = finnhub_client.company_news(symbol, _from=start.isoformat(), to=now.isoformat()) or []
    except Exception:
        return []
    # most recent first
    news.sort(key=lambda x: x.get("datetime", 0), reverse=True)

    out = []
    for it in news[:max(1, min(limit, 200))]:
        ts = it.get("datetime")
        out.append({
            "datetime": ts,
            "date": (datetime.utcfromtimestamp(ts).isoformat() + "Z") if ts else None,
            "headline": it.get("headline"),
            "source": it.get("source"),
            "url": it.get("url"),
            "summary": it.get("summary"),
        })
    return out     

def fetch_profiles(tickers: list[str]) -> list[dict]:
    if not tickers:
        return []
    rows: list[dict] = []
    seen: set[str] = set()

    for t in tickers:
        sym = (t or "").strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)

        try:
            profile = finnhub_client.company_profile2(symbol=sym) or {}
        except Exception:
            continue

        # get basic props 
        name = (profile.get("name") or sym).strip()
        sector = (profile.get("finnhubIndustry") or "Unknown").strip()

        # extra props from profile
        props = {
            "exchange": profile.get("exchange"),
            "country": profile.get("country"),
            "currency": profile.get("currency"),
            "ipo": profile.get("ipo"),
            "marketCap": profile.get("marketCapitalization"),
            "sharesOutstanding": profile.get("shareOutstanding"),
            "weburl": profile.get("weburl"),
        }

        #clean props of empty values
        props = {k: v for k, v in props.items() if v not in (None, "", 0, [])}

        rows.append({"ticker": sym, "name": name, "sector": sector, "props": props})

    return rows


def _num(x):
    try:
        if x is None: 
            return None
        v = float(x)
        return v if math.isfinite(v) else None
    except Exception:
        return None

#from chatgpt - aswell same regarding the numeric cleaner above
def fetch_basic_financials(tickers: list[str]) -> dict[str, dict]:
    """
    Return { 'AAPL': {'pe':..., 'pb':..., 'ps':..., 'roe':..., ...}, ... }
    Pulls Finnhub 'company_basic_financials' (metric='all') and maps to our normalized keys.
    """
    out: dict[str, dict] = {}
    if not tickers:
        return out

    seen = set()
    for raw in tickers:
        sym = (raw or "").strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)

        try:
            payload = finnhub_client.company_basic_financials(symbol=sym, metric="all") or {}
        except Exception:
            continue

        metric = payload.get("metric") or {}
        # map: choose the first available key in each list
        def pick(keys: list[str]):
            for k in keys:
                if k in metric:
                    return _num(metric.get(k))
            return None

        m: dict[str, float] = {}
        # valuation
        v = pick(["peInclExtraTTM", "peTTM", "peBasicExclExtraTTM"])
        if v is not None: m["pe"] = v
        v = pick(["pbAnnual", "pbTTM"])
        if v is not None: m["pb"] = v
        v = pick(["psTTM"])
        if v is not None: m["ps"] = v
        # quality / margins
        v = pick(["roeTTM"])
        if v is not None: m["roe"] = v
        v = pick(["roaTTM"])
        if v is not None: m["roa"] = v
        v = pick(["grossMarginTTM"])
        if v is not None: m["grossMarginTTM"] = v
        v = pick(["operatingMarginTTM"])
        if v is not None: m["operatingMarginTTM"] = v
        v = pick(["netProfitMarginTTM", "netMarginTTM"])
        if v is not None: m["netMarginTTM"] = v
        # leverage & liquidity
        v = pick(["debtToEquity"])
        if v is not None: m["debtToEquity"] = v
        v = pick(["currentRatio"])
        if v is not None: m["currentRatio"] = v
        v = pick(["quickRatio"])
        if v is not None: m["quickRatio"] = v
        # risk & income
        v = pick(["beta"])
        if v is not None: m["beta"] = v
        dy = _num(metric.get("dividendYieldTTM"))
        if dy is not None:
            # normalize to fraction if API returns percent like 2.5 → 0.025
            if dy > 1.0:
                dy = dy / 100.0
            m["dividendYieldTTM"] = max(0.0, min(1.0, dy))
        # growth (optional)
        v = pick(["revenueGrowthTTM"])
        if v is not None: m["revenueGrowthTTM"] = v
        v = pick(["epsGrowthTTM"])
        if v is not None: m["epsGrowthTTM"] = v

        if m:
            out[sym] = m

    return out

