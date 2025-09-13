from typing import Dict, List
from fastapi import FastAPI
from pydantic import BaseModel, Field

APP_NAME = "advisor-api"

app = FastAPI(title="AI-Driven Investment Advisor")

class AdviceRequest(BaseModel):
    risk: int = Field(ge=1, le=5, description="Risk level 1–5 (low→high)")
    universe: List[str] = Field(min_length=1, description="List of tickers/assets")

class AdviceResponse(BaseModel):
    allocation: Dict[str, float]
    rationale: str

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": APP_NAME,
    }

@app.post("/advice", response_model=AdviceResponse)
def advice(req: AdviceRequest):
    unique = [t.strip().upper() for t in req.universe if t.strip()]
    unique = list(dict.fromkeys(unique))
    n = len(unique)
    if n == 0:
        return {
            "allocation": {},
            "rationale": "No assets provided.",
        }
    weight = round(1.0 / n, 6)
    allocation = {t: weight for t in unique}

    rationale = (
        f"This is a stub allocation with equal weights across {n} assets. "
        f"Risk={req.risk}. No market data used yet—just shaping the API. "
    )

    return AdviceResponse(
        allocation=allocation,
        rationale=rationale,
    )