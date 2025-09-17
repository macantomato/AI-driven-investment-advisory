import os, httpx
import finnhub

API_BASE = "https://finnhub.io/api/v1"
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
if not FINNHUB_API_KEY:
    raise SystemExit("Set FINNHUB_API_KEY env variable first")

finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)


def fetch_profiles(tickers: list[str]) -> list[dict]:
    if not tickers:
        return []
    rows: list[dict] = []
    seen: set[str] = set()

    for t in tickers:
        sym = (t or "").strip().upper()
        if not t or t in seen:
            continue
        seen.add(sym)

        try:
            profile = finnhub_client.company_profile2(symbol=sym) or {}
        except Exception:
            continue

        # get basic props
        name = (profile.get("name") or sym).strip()
        sector = (profile.get("finnhubindustry") or "Uknown").strip()

        # extra props from profile
        props = {
            "exchange": (profile.get("exchange") or ""),
            "country": (profile.get("country") or ""),
            "currency": (profile.get("currency") or ""),
            "ipo": (profile.get("ipo") or ""),
            "marketCapitalization": (profile.get("marketCapitalization") or 0),
            "shareOutstanding": (profile.get("shareOutstanding") or 0),
            "ticker": (profile.get("ticker") or ""),
            "weburl": (profile.get("weburl") or ""),
        }

        #clean props of empty values
        props = {k: v for k, v in props.items() if v not in (None, "", 0, [])}

        rows.append({"ticker": sym, "name": name, "sector": sector, "props": props})

    return rows

