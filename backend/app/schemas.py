from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrategyAssumptions(BaseModel):
    false_positive_cost: float = Field(default=18.0, ge=0)
    manual_review_cost: float = Field(default=1.2, ge=0)
    fraud_recovery_rate: float = Field(default=0.35, ge=0, le=1)
    customer_friction_cost: float = Field(default=0.0, ge=0)
    maximum_review_capacity: int = Field(default=1_400, ge=0)


class ScoredTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: int
    amount: float = Field(ge=0)
    fraud_probability: float = Field(ge=0, le=1)
    is_fraud: bool


class SimulationRequest(BaseModel):
    threshold: float = Field(default=0.42, ge=0.01, le=0.99)
    assumptions: StrategyAssumptions = Field(default_factory=StrategyAssumptions)
    transactions: list[ScoredTransaction] = Field(min_length=1)


class SimulationResponse(BaseModel):
    threshold: float
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    flagged_transactions: int
    legitimate_transactions_declined: int
    prevented_fraud_amount: float
    missed_fraud_loss: float
    false_positive_cost: float
    manual_review_cost: float
    capacity_overflow_cost: float
    total_strategy_cost: float


class AttackResponse(BaseModel):
    attack_id: str
    name: str
    fraud_probability: float
    threshold: float
    detected: bool
    strongest_signal: str
