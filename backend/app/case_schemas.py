"""Contracts deliberately exclude ground-truth labels and caller-selected actors."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Status = Literal["pending", "reviewed", "confirmed_fraud", "legitimate"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class CaseSnapshot(StrictModel):
    transaction_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    timestamp: datetime
    amount: float = Field(ge=0, le=1_000_000_000)
    merchant_category: str = Field(min_length=1, max_length=80)
    country: str = Field(min_length=1, max_length=80)
    fraud_probability: float = Field(ge=0, le=1)
    threshold: float = Field(gt=0, lt=1)
    model_version: str = Field(min_length=1, max_length=100)
    source: Literal["verified_synthetic_study", "caller_supplied_simulation"]
    features: dict[str, float | bool | str] = Field(default_factory=dict, max_length=30)
    reason_codes: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("timestamp")
    @classmethod
    def aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @field_validator("features")
    @classmethod
    def bounded_features(cls, value):
        if {key.lower() for key in value} & {"is_fraud", "label", "target", "ground_truth", "class"}:
            raise ValueError("ground-truth labels do not belong in investigation features")
        if any(len(key) > 80 or (isinstance(item, str) and len(item) > 200) for key, item in value.items()):
            raise ValueError("feature names/values exceed limits")
        return value

    @field_validator("reason_codes")
    @classmethod
    def bounded_reasons(cls, value):
        if any(not item.strip() or len(item) > 240 for item in value):
            raise ValueError("reason codes must contain 1–240 characters")
        return value


class CaseAction(StrictModel):
    expected_version: int = Field(ge=1)
    action: Literal["transition", "note"]
    status: Status | None = None
    note: str = Field(min_length=3, max_length=2000)

    @field_validator("note")
    @classmethod
    def readable_note(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3 or any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("note must have at least three readable characters and no control characters")
        return value
