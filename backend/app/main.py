from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .database import Base, engine
from .schemas import AttackResponse, SimulationRequest, SimulationResponse
from .services.cost_engine import evaluate_strategy


ATTACKS = {
    "card-testing": ("Card testing", 0.88, "Eight small attempts in eleven minutes"),
    "velocity": ("Velocity burst", 0.79, "Twelve transactions in the previous hour"),
    "takeover": ("Account takeover", 0.94, "New device, country, and unusual amount"),
    "travel": ("Impossible travel", 0.76, "4,012 miles in thirty-eight minutes"),
    "dormant": ("Dormant-card attack", 0.84, "First transaction after 143 inactive days"),
    "merchant": ("Merchant anomaly", 0.57, "First purchase in a high-risk category"),
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="FraudLens API",
    version="1.0.0",
    description="Explainable fraud-strategy simulation API.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "fraudlens-api"}


@app.post("/api/v1/strategy/simulate", response_model=SimulationResponse)
def simulate_strategy(request: SimulationRequest) -> SimulationResponse:
    result = evaluate_strategy(request.transactions, request.threshold, request.assumptions)
    return SimulationResponse(**result.to_dict())


@app.get("/api/v1/attacks/{attack_id}", response_model=AttackResponse)
def simulate_attack(attack_id: str, threshold: float = 0.42) -> AttackResponse:
    if not 0.01 <= threshold <= 0.99:
        raise HTTPException(status_code=422, detail="threshold must be between 0.01 and 0.99")
    attack = ATTACKS.get(attack_id)
    if not attack:
        raise HTTPException(status_code=404, detail="unknown attack pattern")
    name, probability, signal = attack
    return AttackResponse(
        attack_id=attack_id,
        name=name,
        fraud_probability=probability,
        threshold=threshold,
        detected=probability >= threshold,
        strongest_signal=signal,
    )
