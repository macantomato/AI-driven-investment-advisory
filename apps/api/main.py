from typing import Dict, List, Optional, Any
import os
import re
from fastapi import FastAPI, Body, Query, Path
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase, Driver
from fastapi import HTTPException
from providers.finnhub import fetch_profiles

APP_NAME = "advisor-api"
DISCLAIMER_LINK = "Educational (@https://github.com/macantomato)"


app = FastAPI(title="AI-Driven Investment Advisor (Educational)")

#--------------------------------------- Startup Events ----------------------------------------


@app.on_event("startup")
def _startup_check_and_constraints():
    drv = get_driver()
    with drv.session() as s:
        # connectivity check
        s.run("RETURN 1")
        s.run("""
        CREATE CONSTRAINT asset_ticker_unique IF NOT EXISTS
        FOR (a:Asset) REQUIRE a.ticker IS UNIQUE
        """)
        # index for sctors
        s.run("""
        CREATE INDEX sector_name_idx IF NOT EXISTS
        FOR (s:Sector) ON (s.name)
        """)
        # Unique constraint for sectors
        s.run("""
        CREATE CONSTRAINT sector_name_unique IF NOT EXISTS
        FOR (s:Sector) REQUIRE s.name IS UNIQUE
        """)
    



#--------------------------------------- LLM Client ----------------------------------------
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# --- CORS: allow local Vite and future Cloudflare Pages deployments ---
allowed_origins = ["http://localhost:5173"]            # Vite dev server
allowed_origin_regex = r"https://.*\.pages\.dev"        # Cloudflare Pages subdomains

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allowed_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Minimal Neo4j driver (lazy init) ---
_driver: Driver | None = None

def get_driver() -> Driver:
    global _driver
    if _driver is None:
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER")
        pw = os.getenv("NEO4J_PASS")
        if not all([uri, user, pw]):
            raise RuntimeError("Missing NEO4J_URI/NEO4J_USER/NEO4J_PASS env vars.")
        _driver = GraphDatabase.driver(uri, auth=(user, pw))
    return _driver

@app.on_event("shutdown")
def _close_driver():
    global _driver
    if _driver is not None:
        _driver.close()

class AdviceRequest(BaseModel):
    risk: int = Field(ge=1, le=5, description="Risk level 1–5 (low→high)")
    universe: List[str] = Field(min_length=1, description="List of tickers/assets")

class AdviceResponse(BaseModel):
    allocation: Dict[str, float]
    rationale: str
    disclaimer: str


#--------------------------------------- API Endpoints GET ----------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "service": APP_NAME, "disclaimer": DISCLAIMER_LINK}

@app.get("/db/ping")
def db_ping():
    drv = get_driver()
    with drv.session() as s:
        value = s.run("RETURN 1 AS value").single()["value"]
    return {"neo4j": "ok", "value": value}

@app.get("/")
def root():
    return {"ok": True, "hint": "Use /health, /db/ping, /docs"}

@app.get("/universe")
def universe(
    sector: Optional[str] = Query(default=None, description="Exact sector name (case-insensitive)"),
    limit: int = Query(default=100, ge=1, le=500, description="Max rows")
):
    try:
        rows = list_assets_with_sectors(sector=sector, limit=limit)
        return {"count": len(rows), "items": rows, "disclaimer": DISCLAIMER_LINK}
    except Exception as e:
        print("[/universe] ERROR:", type(e).__name__, str(e))
        raise HTTPException(status_code=500, detail="Database read failed")

@app.get("/search")
def search(
    q: str = Query(..., min_length=1, max_length=10,
                   description="Search ticker or name (case-insensitive prefix)"),
    limit: int = Query(default=20, ge=1, le=100, description="Max rows to return")
):
    try:
        drv = get_driver()
        with drv.session() as s:
            cypher = """
            MATCH (a:Asset)-[:IN_SECTOR]->(s:Sector)
            WHERE toUpper(a.ticker) STARTS WITH toUpper($q)
            OR toUpper(coalesce(a.name, '')) STARTS WITH toUpper($q)
            RETURN a.ticker AS ticker,
                   coalesce(a.name, a.ticker) AS name,
                   coalesce(s.name, 'Unknown') AS sector
            ORDER BY ticker
            LIMIT $limit
            """
            result = s.run(cypher, q=q, limit=int(limit))
            rows = [dict(r) for r in result]
        return {"count": len(rows), "items": rows, "disclaimer": DISCLAIMER_LINK}
    except Exception as e:
        print("[/search] ERROR:", type(e).__name__, str(e))
        raise HTTPException(status_code=500, detail="Database read failed")


@app.get("/asset/{ticker}")
def asset_details(
    ticker: str = Path(..., description="Ticker symbol, example AAGL, MSFT,")
):
    try:
        drv = get_driver()
        #Added to return all props from asset node
        cypher = """
        MATCH (a:Asset)
        WHERE toUpper(a.ticker) = toUpper($ticker)
        OPTIONAL MATCH (a)-[:IN_SECTOR]->(s:Sector)
        WITH a, collect(DISTINCT s.name) AS sectors
        RETURN a{ .*, sectors: sectors } AS item
        """
        with drv.session() as s:
            record = s.run(cypher, ticker=ticker).single()
        if not record:
            raise HTTPException(status_code=404, detail="Asset not found")
        return {"item": dict(record), "disclaimer": DISCLAIMER_LINK}
    except HTTPException:
        raise
    except Exception as e:
        print("[/asset/{ticker}] ERROR:", type(e).__name__, str(e))
        raise HTTPException(status_code=500, detail="Database read failed")

@app.get("/ingest/finnhub")
def ingest_finnhub(
    tickers: List[str] = Query(..., min_items=1, max_items=50, description="Repeat ?tickers=AAPL&tickers=MSFT"),
    include: Optional[str] = Query(None, description="comma list: metrics")
):
    if len(tickers) > 50:
        raise HTTPException(status_code=400, detail="Max 50 tickers allowed")
    try:
        from providers.finnhub import fetch_basic_financials
        rows = fetch_profiles(tickers)
        if not rows:
            return {"received": 0, "created_count": 0, "updated_count": 0,
                    "created_tickers": [], "updated_tickers": [], "disclaimer": DISCLAIMER_LINK}

        include_set = {s.strip().lower() for s in (include.split(",") if include else [])}

        if "metrics" in include_set:
            metrics = fetch_basic_financials([r["ticker"] for r in rows])
            for r in rows:
                r["props"].update(metrics.get(r["ticker"], {}))

        summary = upsert_assets(rows)
        return {"received": len(rows), **summary, "disclaimer": DISCLAIMER_LINK}
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        print("[/ingest/finnhub] ERROR:", type(e).__name__, str(e))
        raise HTTPException(status_code=500, detail="Ingest failed")


@app.get("/analyze/fundamentals")
def analyze_fundamentals(ticker: str = Query(..., min_length=1)):
    cypher = """
    MATCH (a:Asset)
    WHERE toUpper(a.ticker) = toUpper($ticker)
    OPTIONAL MATCH (a)-[:IN_SECTOR]->(s:Sector)
    WITH a, collect(DISTINCT s.name) AS sectors
    RETURN a{ .*, sectors: sectors } AS item
    """
    drv = get_driver()
    with drv.session() as s:
        record = s.run(cypher, ticker=ticker).single()
    if not record:
        raise HTTPException(status_code=404, detail="Asset not found")

    item = record["item"]

    pe = item.get("pe")
    mcap = item.get("marketCap") or item.get("marketcap")
    sector = (item.get("sectors") or ["Unknown"])[0]

    analysis = []
    if pe is not None:
        if pe < 10:
            analysis.append(f"The P/E ratio of {pe} suggests the stock may be undervalued.")
        elif pe > 25:
            analysis.append(f"The P/E ratio of {pe} indicates the stock may be overvalued.")
        else:
            analysis.append(f"The P/E ratio of {pe} is within a normal range.")
    else:
        analysis.append("P/E ratio data is not available.")

    if mcap is not None:
        if mcap < 300_000_000:
            analysis.append(f"The market cap of ${mcap:,.0f} classifies it as a small-cap stock, which may have higher growth potential but also higher risk.")
        elif mcap < 2_000_000_000:
            analysis.append(f"The market cap of ${mcap:,.0f} classifies it as a mid-cap stock, balancing growth potential and stability.")
        else:
            analysis.append(f"The market cap of ${mcap:,.0f} classifies it as a large-cap stock, which tends to be more stable but with potentially lower growth.")
    else:
        analysis.append("Market capitalization data is not available.")

    analysis.append(f"The stock operates in the {sector} sector.")

    return {
        "ticker": item.get("ticker"),
        "name": item.get("name"),
        "sector": sector,
        "pe": pe,
        "marketCap": mcap,
        "analysis": analysis,
        "disclaimer": DISCLAIMER_LINK,
    }

@app.get("/finnhub/recommendation/{ticker}")
def finnhub_recommendation(ticker: str = Path(..., min_length=1, description="Ticker symbol, AAPL")):
    from providers.finnhub import fetch_finnhub_recommendation
    symbol = ticker.strip().upper()
    try:
        record = fetch_finnhub_recommendation(symbol)
    except HTTPException:
        raise
    except Exception as e:
        print("[/finnhub/recommendation] ERROR:", type(e).__name__, str(e))
        raise HTTPException(status_code=500, detail="Fetch failed") from e
    if not record:
        raise HTTPException(status_code=404, detail="No recommendation, or invalid ticker")

    return {"ticker": symbol, "recommendations": record}
    
@app.get("/finnhub/news/{ticker}")
def finnhub_news(
    ticker: str = Path(..., min_length=1, description="Ticker (e.g., AAPL)"),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=200)
):
    try:
        from providers.finnhub import fetch_company_news
        items = fetch_company_news(ticker, days=days, limit=limit)
        return {"ticker": ticker.upper(), "count": len(items), "items": items}
    except Exception as e:
        print("[/finnhub/news] ERROR:", type(e).__name__, str(e))
        raise HTTPException(status_code=500, detail="Fetch failed")
    
# wrapper for single ticker ingest with finnhub
# @app.get("/ingest/ticker/{ticker}")
# def ingest_ticker(ticker: str):
#     return ingest_finnhub(tickers=[ticker], include="metrics")

#--------------------------------------- API Endpoints POST  ----------------------------------------
@app.api_route("/advice", methods=["GET", "POST"])
def advice(_: dict | None = Body(None)):
    items = list_assets_with_sectors()
    return {
        "query": "MATCH (a:Asset)-[:IN_SECTOR]->(s:Sector) RETURN a.ticker AS ticker, s.name AS sector ORDER BY ticker",
        "count": len(items),
        "items": items,
        "disclaimer": DISCLAIMER_LINK,
        "rationale": llm_explain([r["ticker"] for r in items][:8], 3) or "LLM not configured",
    }

@app.post("/explain")
def explain(payload: dict | None = Body(None)):
    risk = int(payload.get("risk", 3)) if payload else 3
    universe = payload.get("universe") if payload else None

    if not universe:
        rows = list_assets_with_sectors()
        tickers = [r["ticker"] for r in rows][:8]
    else:
        tickers = [t.strip().upper() for t in universe if t and t.strip()]
        tickers = list(dict.fromkeys(tickers))[:8]

    text = llm_explain(tickers, risk)
    rationale = text or (
        f"Stub rationale for risk={risk} and tickers={tickers}. "
        f"{DISCLAIMER_LINK}"
    )
    return {
        "risk": risk,
        "tickers_used": tickers,
        "rationale": rationale,
        "disclaimer": DISCLAIMER_LINK,
    }
#next to do is POST for upsert assets (endpoint)
class IngestAsset(BaseModel):
    ticker: str
    name: Optional[str] = None
    sector: Optional[str] = None
    props: Dict[str, Any] = Field(default_factory=dict)

# @app.post("/ingest/assets")
# def ingest_assets(payload: List[IngestAsset] = Body(...)):
#     try:
#         rows = [p.model_dump() if hasattr(p, "model_dump") else p.dict() for p in payload]
#         n = upsert_assets(rows)
#         return {"ingested": n, "disclaimer": DISCLAIMER_LINK}
#     except Exception as e:
#         print("[/ingest/assets] ERROR:", type(e).__name__, str(e))
#         raise HTTPException(status_code=500, detail="Ingest failed")

@app.post("/ingest/assets")
def ingest_assets(payload: List[IngestAsset] = Body(...)):
    try:
        rows = [p.model_dump() if hasattr(p, "model_dump") else p.dict() for p in payload]
        summary = upsert_assets(rows)
        return {"received": len(rows), **summary, "disclaimer": DISCLAIMER_LINK}
    except Exception as e:
        print("[/ingest/assets] ERROR:", type(e).__name__, str(e))
        raise HTTPException(status_code=500, detail="Ingest failed")


#--------------------------------------- Query/Cypher funcs ----------------------------------------

# def list_assets_with_sectors() -> list[dict]:
#     drv = get_driver()
#     cypher = """
#     MATCH (a:Asset)-[:IN_SECTOR]->(s:Sector)
#     RETURN a.ticker AS ticker, s.name AS sector
#     ORDER BY ticker
#     """
#     with drv.session() as s:
#         return [dict(r) for r in s.run(cypher)]

def list_assets_with_sectors(sector: Optional[str] = None, limit: int = 100) -> list[dict]:
    drv = get_driver()
    cypher = """
    MATCH (a:Asset)-[:IN_SECTOR]->(s:Sector)
    {where}
    RETURN a.ticker AS ticker, coalesce(s.name, 'Unknown') AS sector
    ORDER BY ticker
    LIMIT $limit
    """.replace("{where}", "WHERE toUpper(s.name) = toUpper($sector)" if sector else "")
    params = {"sector": sector, "limit": int(limit)}
    with drv.session() as s:
        return [dict(r) for r in s.run(cypher, **params)]

def upsert_assets(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    drv = get_driver()
    cypher = """
    UNWIND $rows AS row
    WITH row
    WHERE row.ticker IS NOT NULL AND trim(row.ticker) <> ''

    MERGE (a:Asset {ticker: toUpper(row.ticker)})
      ON CREATE SET a.name = coalesce(row.name, row.ticker), a._new = true
      ON MATCH  SET a.name = coalesce(row.name, a.name)

    MERGE (s:Sector {name: coalesce(row.sector, 'Unknown')})
    MERGE (a)-[:IN_SECTOR]->(s)

    WITH a, coalesce(row.props, {}) AS p, (a._new IS NOT NULL) AS isNew
    SET a += p
    SET a.updatedAt = datetime(), a.updatedAtMs = timestamp()
    REMOVE a._new

    RETURN
      count(a) AS total_touched,
      sum(CASE WHEN isNew THEN 1 ELSE 0 END) AS created_count,
      collect({ticker: a.ticker, created: isNew}) AS results
    """
    with drv.session() as s:
        rec = s.run(cypher, rows=rows).single()
        results = rec["results"] or []
        created = [r["ticker"] for r in results if r["created"]]
        updated = [r["ticker"] for r in results if not r["created"]]
        return {
            "total_touched": int(rec["total_touched"]),
            "created_count": int(rec["created_count"]),
            "updated_count": len(updated),
            "created_tickers": created,
            "updated_tickers": updated,
        }

    
#--------------------------------------- Groq LLM funcs ----------------------------------------
_llm_client = None

def get_llm():
    global _llm_client
    if _llm_client is not None:
        return _llm_client
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or OpenAI is None:
        return None
    _llm_client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
    return _llm_client

def llm_explain(tickers: list[str], risk: int) -> str | None:
    client = get_llm()
    if client is None:
        return None
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            temperature=0.2,
            max_tokens=220,
            messages=[
                {"role": "system", "content": "You are a professional investment advisor."
                 "Be brief (80-120 words). Use plain language. "},
                 {"role": "user", "content":
                 f"Risk level: {risk} (1–5). Universe tickers: {', '.join(tickers)}. "
                 "Explain a simple rationale for an equal-weight learning example and note any missing data briefly."},
            ], timeout=20,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or None
    except Exception:
        return None
    
   #--------------------------------------- Helpers for analyzers  ----------------------------------------
def _get_asset_item(ticker: str) -> dict | None:
    """Return a{ .*, sectors: [...] } from Neo4j or None."""
    drv = get_driver()
    cypher = """
    MATCH (a:Asset)
    WHERE toUpper(a.ticker) = toUpper($ticker)
    OPTIONAL MATCH (a)-[:IN_SECTOR]->(s:Sector)
    WITH a, collect(DISTINCT s.name) AS sectors
    RETURN a{ .*, sectors: sectors } AS item
    """
    with drv.session() as s:
        rec = s.run(cypher, ticker=ticker).single()
    return rec["item"] if rec else None


def _num(v, default=None):
    try:
        if v is None:
            return default
        f = float(v)
        return f
    except Exception:
        return default


def _fmt_money(x: float | None) -> str:
    if x is None:
        return "n/a"
    absx = abs(x)
    if absx >= 1e12: return f"${x/1e12:.2f}T"
    if absx >= 1e9:  return f"${x/1e9:.2f}B"
    if absx >= 1e6:  return f"${x/1e6:.2f}M"
    if absx >= 1e3:  return f"${x/1e3:.2f}K"
    return f"${x:,.0f}"
    
@app.get("/analyze/fundamentals_v1")
def analyze_fundamentals_v1(ticker: str = Query(..., min_length=1)):
    item = _get_asset_item(ticker)
    if not item:
        raise HTTPException(status_code=404, detail="Asset not found")

    pe   = _num(item.get("pe"))
    pb   = _num(item.get("pb"))
    ps   = _num(item.get("ps"))
    roe  = _num(item.get("roe"))
    roa  = _num(item.get("roa"))
    gm   = _num(item.get("grossMarginTTM"))
    om   = _num(item.get("operatingMarginTTM"))
    nm   = _num(item.get("netMarginTTM"))
    dte  = _num(item.get("debtToEquity"))
    cr   = _num(item.get("currentRatio"))
    qr   = _num(item.get("quickRatio"))
    beta = _num(item.get("beta"))
    dy   = _num(item.get("dividendYieldTTM"))  
    mcap = _num(item.get("marketCap"))

    score = 50
    notes = []

    if pe is not None:
        if pe < 12:  score += 6;  notes.append(f"P/E {pe:.1f} looks inexpensive.")
        elif pe > 30: score -= 6; notes.append(f"P/E {pe:.1f} looks rich.")
        else: notes.append(f"P/E {pe:.1f} is moderate.")

    if pb is not None and pb > 6: score -= 3
    if ps is not None and ps > 12: score -= 3

    if roe is not None:
        if roe >= 15: score += 6; notes.append(f"ROE {roe:.1f}% is strong.")
        elif roe < 5: score -= 4; notes.append(f"ROE {roe:.1f}% is low.")

    if gm is not None and gm >= 50: score += 3
    if om is not None and om >= 20: score += 2
    if nm is not None and nm >= 15: score += 2

    if dte is not None:
        if dte > 2.0: score -= 5; notes.append(f"Debt/Equity {dte:.2f} is high.")
        elif dte < 0.5: score += 3

    if cr is not None and cr < 1.0: score -= 3
    if qr is not None and qr < 0.8: score -= 2

    if beta is not None:
        if beta > 1.4: score -= 3
        elif beta < 0.8: score += 2

    if dy is not None and dy >= 0.02: score += 2  # ≥2% div yield

    score = max(0, min(100, score))

    return {
        "ticker": item.get("ticker"),
        "name": item.get("name"),
        "sector": (item.get("sectors") or ["Unknown"])[0],
        "metrics": {
            "pe": pe, "pb": pb, "ps": ps,
            "roe": roe, "roa": roa,
            "grossMarginTTM": gm, "operatingMarginTTM": om, "netMarginTTM": nm,
            "debtToEquity": dte, "currentRatio": cr, "quickRatio": qr,
            "beta": beta, "dividendYieldTTM": dy,
            "marketCap": mcap, "marketCapPretty": _fmt_money(mcap),
        },
        "score": score,
        "notes": notes,
        "disclaimer": DISCLAIMER_LINK,
    }

@app.get("/analyze/news")
def analyze_news(
    ticker: str = Query(..., min_length=1),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=3, le=30),
):
    from providers.finnhub import fetch_company_news
    items = fetch_company_news(ticker, days=days, limit=limit)
    headlines = [f"- {it.get('headline','')}" for it in items][:limit]

    client = get_llm()
    summary = ""
    sentiment = 0.0
    bullets = []
    risks = []
    if client and headlines:
        try:
            prompt = (
                "Summarize these recent headlines in 3-5 sentences, "
                "then provide 3 bullet positives and 3 bullet risks. "
                "Finally, return an overall sentiment from -1 (bearish) to +1 (bullish).\n\n"
                + "\n".join(headlines)
            )
            resp = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                temperature=0.2, max_tokens=350, timeout=20,
                messages=[
                    {"role":"system","content":"Be concise, neutral and factual."},
                    {"role":"user","content":prompt}
                ]
            )
            text = (resp.choices[0].message.content or "").strip()
            summary = text
        except Exception:
            pass

    return {
        "ticker": ticker.upper(),
        "count": len(items),
        "headlines": items,   
        "summary": summary or "No LLM summary available.",
        "sentiment": sentiment,
        "disclaimer": DISCLAIMER_LINK,
    }

@app.get("/analyze/street")
def analyze_street(ticker: str = Query(..., min_length=1)):
    from providers.finnhub import fetch_finnhub_recommendation
    rows = fetch_finnhub_recommendation(ticker) or []

    latest = rows[0] if rows else {}
    counts = {
        "strongBuy": int(latest.get("strongBuy", 0) or 0),
        "buy": int(latest.get("buy", 0) or 0),
        "hold": int(latest.get("hold", 0) or 0),
        "sell": int(latest.get("sell", 0) or 0),
        "strongSell": int(latest.get("strongSell", 0) or 0),
        "period": latest.get("period"),
    }
    total = sum(counts[k] for k in ("strongBuy","buy","hold","sell","strongSell"))
    bias = (counts["strongBuy"] + counts["buy"]) - (counts["sell"] + counts["strongSell"])

    stance = "mixed"
    if total > 0:
        if bias >= total * 0.2: stance = "bullish"
        elif bias <= -total * 0.2: stance = "bearish"

    return {
        "ticker": ticker.upper(),
        "latest": counts,
        "total_analysts": total,
        "stance": stance,
        "history": rows, 
        "disclaimer": DISCLAIMER_LINK,
    }

class AdviceV1Request(BaseModel):
    tickers: List[str] = Field(min_items=1, max_items=10)
    risk: int = Field(3, ge=1, le=5)

@app.post("/advice/v1")
def advice_v1(body: AdviceV1Request):
    tickers = [t.strip().upper() for t in body.tickers if t and t.strip()]
    tickers = list(dict.fromkeys(tickers))[:10]

    per = []
    for t in tickers:
        fundamentals = analyze_fundamentals_v1.__wrapped__(ticker=t)  # call handler logic
        street = analyze_street.__wrapped__(ticker=t)
        news = analyze_news.__wrapped__(ticker=t, days=14, limit=5)
        per.append({"ticker": t, "fundamentals": fundamentals, "street": street, "news": news})

    client = get_llm()
    rationale = "LLM not configured."
    allocation = {t: round(1/len(tickers), 4) for t in tickers} if tickers else {}

    if client:
        try:
            lines = []
            for p in per:
                f = p["fundamentals"]; s = p["street"]; n = p["news"]
                lines.append(
                    f"{p['ticker']}: score={f.get('score')}, "
                    f"pe={f['metrics'].get('pe')}, roe={f['metrics'].get('roe')}, "
                    f"dte={f['metrics'].get('debtToEquity')}, beta={f['metrics'].get('beta')}, "
                    f"street={s.get('stance')} ({s.get('total_analysts')} analysts), "
                    f"news_count={n.get('count')}"
                )
            prompt = (
                "You're an educational investment assistant. Given risk level "
                f"{body.risk} (1=conservative, 5=aggressive) and the following per-ticker summaries,\n"
                "1) suggest a simple diversified allocation (weights summing to 100%),\n"
                "2) give a brief rationale (120-180 words),\n"
                "3) include 2 risks to monitor.\n"
                "Do not give financial advice; be educational and generic.\n\n"
                + "\n".join(lines)
            )
            resp = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                temperature=0.2, max_tokens=400, timeout=25,
                messages=[{"role":"system","content":"Be concise, educational, balanced."},
                          {"role":"user","content":prompt}]
            )
            rationale = (resp.choices[0].message.content or "").strip()

        except Exception:
            pass

    return {
        "risk": body.risk,
        "tickers": tickers,
        "per_ticker": per,
        "allocation": allocation, 
        "rationale": rationale,
        "disclaimer": DISCLAIMER_LINK,
    }


