from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, DDL, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    amount: Mapped[float] = mapped_column(Float)
    merchant_category: Mapped[str] = mapped_column(String(80), index=True)
    country: Mapped[str] = mapped_column(String(80), index=True)
    distance_from_home: Mapped[float] = mapped_column(Float)
    transactions_last_hour: Mapped[int] = mapped_column(Integer)
    average_amount_30d: Mapped[float] = mapped_column(Float)
    new_device: Mapped[bool] = mapped_column(Boolean)
    card_present: Mapped[bool] = mapped_column(Boolean)
    account_age_days: Mapped[int] = mapped_column(Integer)
    is_international: Mapped[bool] = mapped_column(Boolean)
    previous_declines: Mapped[int] = mapped_column(Integer)
    is_fraud: Mapped[bool] = mapped_column(Boolean, index=True)
    dataset_source: Mapped[str] = mapped_column(String(40), index=True)

    scores: Mapped[list[ModelScore]] = relationship(back_populates="transaction", cascade="all, delete-orphan")
    explanations: Mapped[list[Explanation]] = relationship(back_populates="transaction", cascade="all, delete-orphan")


class ModelScore(Base):
    __tablename__ = "model_scores"
    __table_args__ = (Index("ix_model_score_version", "model_name", "model_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    model_name: Mapped[str] = mapped_column(String(80))
    model_version: Mapped[str] = mapped_column(String(40))
    fraud_probability: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    predicted_fraud: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    transaction: Mapped[Transaction] = relationship(back_populates="scores")


class Explanation(Base):
    __tablename__ = "explanations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    feature_name: Mapped[str] = mapped_column(String(120))
    feature_value: Mapped[str] = mapped_column(String(255))
    contribution: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(16))
    explanation_rank: Mapped[int] = mapped_column(Integer)

    transaction: Mapped[Transaction] = relationship(back_populates="explanations")


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    threshold: Mapped[float] = mapped_column(Float)
    false_positives: Mapped[int] = mapped_column(Integer)
    false_negatives: Mapped[int] = mapped_column(Integer)
    fraud_detected: Mapped[int] = mapped_column(Integer)
    fraud_missed: Mapped[int] = mapped_column(Integer)
    legitimate_transactions_declined: Mapped[int] = mapped_column(Integer)
    prevented_fraud_amount: Mapped[float] = mapped_column(Float)
    missed_fraud_loss: Mapped[float] = mapped_column(Float)
    operational_cost: Mapped[float] = mapped_column(Float)
    total_strategy_cost: Mapped[float] = mapped_column(Float)


class InvestigationCase(Base):
    __tablename__ = "investigation_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    snapshot_json: Mapped[str] = mapped_column(Text)
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40), index=True)


class CaseEvent(Base):
    __tablename__ = "case_events"
    __table_args__ = (UniqueConstraint("case_id", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("investigation_cases.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[str] = mapped_column(Text)
    previous_hash: Mapped[str] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64))


# Application users have no mutation/delete event routes. SQLite additionally
# rejects accidental SQL updates/deletes; a DB owner can still disable triggers.
for operation in ("UPDATE", "DELETE"):
    event.listen(CaseEvent.__table__, "after_create", DDL(
        f"CREATE TRIGGER case_events_no_{operation.lower()} BEFORE {operation} ON case_events "
        "BEGIN SELECT RAISE(ABORT, 'case events are append-only'); END"
    ).execute_if(dialect="sqlite"))
