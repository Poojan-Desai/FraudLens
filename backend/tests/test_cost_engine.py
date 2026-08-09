from backend.app.schemas import ScoredTransaction, StrategyAssumptions
from backend.app.services.cost_engine import evaluate_strategy


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
