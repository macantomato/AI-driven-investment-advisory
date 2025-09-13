from typing import Dict, List
import os
from fastapi import FastAPI
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase, Driver

APP_NAME = "advisor-api"
DISCLAIMER = "Educational only — NOT financial advice."

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

@app.get("/health")
def health():
    return {"status": "ok", "service": APP_NAME, "disclaimer": DISCLAIMER}

@app.get("/db/ping")
def db_ping():
    drv = get_driver()
    with drv.session() as s:
        value = s.run("RETURN 1 AS value").single()["value"]
    return {"neo4j": "ok", "value": value}

@app.get("/")
def root():
    return {"ok": True, "hint": "Use /health, /db/ping, /docs"}

@app.post("/advice", response_model=AdviceResponse)
def advice(req: AdviceRequest):
    # Minimal stub: equal weight, no DB/LLM yet
    unique = [t.strip().upper() for t in req.universe if t.strip()]
    unique = list(dict.fromkeys(unique))
    n = len(unique)
    if n == 0:
        return {"allocation": {}, "rationale": "No assets provided.", "disclaimer": DISCLAIMER}
    weight = round(1.0 / n, 6)
    allocation = {t: weight for t in unique}
    rationale = (
        f"Stub equal-weight across {n} assets (risk={req.risk}). "
        f"LLM and graph logic will be added later. {DISCLAIMER}"
    )
    return AdviceResponse(allocation=allocation, rationale=rationale, disclaimer=DISCLAIMER)
