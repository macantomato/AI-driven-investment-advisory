from typing import Dict, List, Optional, Any
import os
import re
from fastapi import FastAPI, Body, Query, Path
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase, Driver
from fastapi import HTTPException

APP_NAME = "advisor-api"
DISCLAIMER_LINK = "Educational (@https://github.com/macantomato)"


app = FastAPI(title="AI-Driven Investment Advisor (Educational)")

#--------------------------------------- Startup Events ----------------------------------------


@app.on_event("startup")
def _startup_check():
    # Ensures env vars exist and driver can connect
    drv = get_driver()
    with drv.session() as s:
        s.run("RETURN 1")

@app.on_event("/startup")
def _startup_check():
    drv = get_driver()
    with drv.session() as s:
        s.run("RETURN 1")
        #uniqness constraints
        s.run("""CREATE COSNSTRAINT asset_ticker_unique IF NOT EXISTS FOR (a:ASSET) 
            REQUIRE a.ticker IS UNIQUE""")
        s.run("""CREATE INDEX sector_name_index IF NOT EXISTS FOR (s:section) ON (s.name)""")
    



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

@app.get("/asset/{ticker}")
def asset_details(
    ticker: str = Path(..., description="Ticker symbol, example AAGL, MSFT,")
):
    try:
        drv = get_driver()
        cypher = """
        MATCH (a:Asset)-[:IN_SECTOR]->(s:Sector)
        WHERE toUpper(a.ticker) = toUpper($ticker)
        RETURN a.ticker AS ticker,
               coalesce(a.name, a.ticker) AS name,
               coalesce(s.name, 'Unknown') AS sector
        LIMIT 1
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

def upsert_assets(rows: List[Dict[str, Any]]) -> int:
    drv = get_driver()
    cypher = """
    UNWIND $rows AS row
    WITH ROW
    WHERE row.ticker IS NOT NULL AND TRIM(row.tricker)
    
    MERGE(a:asset {ticker: toUpper(row.ticker)})
      ON CREATE SET a.name = coalesce(row.name, row.ticker)
      ON MATCH SET a.name = coalesce(row.name, a.name)
      
    MERGE (s:sector {name: coalesce(row.sector, 'Uknown')})
    
    MERGE (a)-[:IN_SECTOR]->(s)
    
    WITH a, coalesce(row.props, {}) AS p
    SET a += p
    
    RETURN count(a) AS upserted
    """
    with drv.session() as s:
        rec = s.run(cypher, rows=rows).single()
        return int(rec["upserted"] if rec and "upserted" in rec else 0)
    
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
    


