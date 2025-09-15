from typing import Dict, List, Optional
import os
from fastapi import FastAPI
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase, Driver

APP_NAME = "advisor-api"
DISCLAIMER_LINK = "Educational (@https://github.com/macantomato)"

app = FastAPI(title="AI-Driven Investment Advisor (Educational)")

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


#--------------------------------------- API Endpoints ----------------------------------------
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

@app.post("/advice")
def advice(_: Optional[dict] = None):
    items = list_assets_with_sectors()
    return {
        "query": "MATCH (a:Asset)-[:IN_SECTOR]->(s:Sector) RETURN a.ticker AS ticker, s.name AS sector ORDER BY ticker",
        "count": len(items),
        "items": items,  # [{ "ticker": "AAPL", "sector": "Technology" }, ...]
        "disclaimer": DISCLAIMER_LINK,
    }
    

#--------------------------------------- Query funcs ----------------------------------------

def list_assets_with_sectors() -> list[dict]:
    drv = get_driver()
    cypher = """
    MATCH (a:Asset)-[:IN_SECTOR]->(s:Sector)
    RETURN a.ticker AS ticker, s.name AS sector
    ORDER BY ticker
    """
    with drv.session() as s:
        return [dict(r) for r in s.run(cypher)]

