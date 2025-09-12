from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Advisor API")

class AdviceRequest(BaseModel):
    risk: str
    universe: list[str]
    constraints: dict | None = None

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/advice")
def advice(req: AdviceRequest):
    return {
        "notice": "Educational only—NOT financial advice",
        "allocation": [{"symbol": "XACT-OMXS30", "weight": 1.0}],
        "rationale": "Stub until Neo4j + tools are connected."
    }