import math

import pytest

from backend.app.schemas import ScoredTransaction, StrategyAssumptions
from backend.app.services.cost_engine import StrategyRangeError, evaluate_strategy


ROWS = [
    ScoredTransaction(transaction_id=1, amount=500, fraud_probability=0.92, is_fraud=True),
    ScoredTransaction(transaction_id=2, amount=70, fraud_probability=0.61, is_fraud=False),
    ScoredTransaction(transaction_id=3, amount=300, fraud_probability=0.34, is_fraud=True),
    ScoredTransaction(transaction_id=4, amount=25, fraud_probability=0.10, is_fraud=False),
]


def test_cost_engine_confusion_matrix_and_costs():
    result = evaluate_strategy(ROWS, 0.50, StrategyAssumptions(maximum_review_capacity=10))
    assert (result.true_positives, result.false_positives, result.true_negatives, result.false_negatives) == (1, 1, 1, 1)
    assert result.prevented_fraud_amount == 500
    assert result.legitimate_transactions_declined == 1
    assert result.total_strategy_cost > result.missed_fraud_loss


def test_higher_threshold_never_flags_more_transactions():
    assumptions = StrategyAssumptions()
    counts = [evaluate_strategy(ROWS, threshold, assumptions).flagged_transactions for threshold in (0.1, 0.3, 0.5, 0.8)]
    assert counts == sorted(counts, reverse=True)


def test_probabilities_produce_bounded_metrics():
    result = evaluate_strategy(ROWS, 0.42, StrategyAssumptions())
    assert 0 <= result.precision <= 1
    assert 0 <= result.recall <= 1
    assert 0 <= result.f1 <= 1


@pytest.mark.parametrize("probability,is_fraud,assumptions", [
    (0.1, True, {}),  # Raw missed amounts overflow before applying recovery.
    (0.9, True, {}),  # Prevented amount overflows even if total cost stays small.
    (0.9, False, {"false_positive_cost": 1e308}),
    (0.9, True, {"manual_review_cost": 1e308}),
])
def test_finite_inputs_with_unrepresentable_aggregates_are_rejected(probability, is_fraud, assumptions):
    rows = [ScoredTransaction(transaction_id=i, amount=1e308,
                              fraud_probability=probability, is_fraud=is_fraud) for i in (1, 2)]
    with pytest.raises(StrategyRangeError, match="finite numeric range"):
        evaluate_strategy(rows, 0.5, StrategyAssumptions(**assumptions))


def test_finite_components_cannot_overflow_combined_total():
    rows = [ScoredTransaction(transaction_id=1, amount=1e308, fraud_probability=0.1, is_fraud=True),
            ScoredTransaction(transaction_id=2, amount=1, fraud_probability=0.9, is_fraud=False)]
    assumptions = StrategyAssumptions(fraud_recovery_rate=0, false_positive_cost=1e308, manual_review_cost=0)
    with pytest.raises(StrategyRangeError, match="finite numeric range"):
        evaluate_strategy(rows, 0.5, assumptions)


def test_large_unused_cost_assumptions_do_not_create_nan():
    rows = [ScoredTransaction(transaction_id=1, amount=100, fraud_probability=0.1, is_fraud=False)]
    result = evaluate_strategy(rows, 0.5, StrategyAssumptions(false_positive_cost=1e308, customer_friction_cost=1e308))
    assert result.total_strategy_cost == 0
    assert all(math.isfinite(value) for value in result.to_dict().values())
