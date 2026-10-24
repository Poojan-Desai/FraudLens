from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass

from ..schemas import ScoredTransaction, StrategyAssumptions
from .money import round_cost


@dataclass(frozen=True)
class StrategyResult:
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

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


def evaluate_strategy(
    transactions: Iterable[ScoredTransaction],
    threshold: float,
    assumptions: StrategyAssumptions,
) -> StrategyResult:
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")

    rows = list(transactions)
    if not rows:
        raise ValueError("at least one scored transaction is required")

    tp = fp = tn = fn = 0
    prevented_fraud_amount = 0.0
    raw_missed_fraud = 0.0

    for row in rows:
        predicted_fraud = row.fraud_probability >= threshold
        if predicted_fraud and row.is_fraud:
            tp += 1
            prevented_fraud_amount += row.amount
        elif predicted_fraud and not row.is_fraud:
            fp += 1
        elif not predicted_fraud and row.is_fraud:
            fn += 1
            raw_missed_fraud += row.amount
        else:
            tn += 1

    flagged = tp + fp
    precision = tp / flagged if flagged else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    missed_loss = raw_missed_fraud * (1 - assumptions.fraud_recovery_rate)
    fp_cost = fp * (assumptions.false_positive_cost + assumptions.customer_friction_cost)
    reviewed = min(flagged, assumptions.maximum_review_capacity)
    review_cost = reviewed * assumptions.manual_review_cost
    overflow = max(0, flagged - assumptions.maximum_review_capacity) * 1.65

    return StrategyResult(
        threshold=threshold,
        precision=precision,
        recall=recall,
        f1=f1,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        flagged_transactions=flagged,
        legitimate_transactions_declined=fp,
        prevented_fraud_amount=round(prevented_fraud_amount, 2),
        missed_fraud_loss=round(missed_loss, 2),
        false_positive_cost=round(fp_cost, 2),
        manual_review_cost=round(review_cost, 2),
        capacity_overflow_cost=round(overflow, 2),
        total_strategy_cost=round_cost(missed_loss + fp_cost + review_cost + overflow),
    )
