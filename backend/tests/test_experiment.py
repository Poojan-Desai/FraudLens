import json

import numpy as np
import pandas as pd
import pytest

from backend.app.ml.experiment import (
    ExperimentConfig, chronological_windows, run_experiment, select_policy, threshold_summary,
)
from backend.app.ml.synthetic import generate_transactions
from backend.app.ml.validation import validate_schema
from backend.app.schemas import ScoredTransaction, StrategyAssumptions
from backend.app.services.cost_engine import evaluate_strategy


@pytest.mark.parametrize("invalid", [0.5, 1.5, np.nan, "1"])
def test_invalid_labels_are_rejected_without_coercion(invalid):
    frame = generate_transactions(100)
    frame["is_fraud"] = frame.is_fraud.astype(object)
    frame.loc[0, "is_fraud"] = invalid
    with pytest.raises(ValueError, match="binary"):
        validate_schema(frame, "synthetic")


def test_windows_are_disjoint_even_when_input_is_shuffled():
    frame = generate_transactions(6000, seed=11).sample(frac=1, random_state=5)
    windows = chronological_windows(frame, (0.6, 0.15, 0.1, 0.15))
    assert [len(part) for part in windows.values()] == [3600, 900, 600, 900]
    parts = list(windows.values())
    for earlier, later in zip(parts, parts[1:]):
        assert earlier.timestamp.max() < later.timestamp.min()
    assert sum(part.is_fraud.sum() for part in parts) == frame.is_fraud.sum()


def test_timestamp_ties_at_a_split_boundary_fail_closed():
    frame = generate_transactions(6000, seed=11)
    frame.loc[3600, "timestamp"] = frame.loc[3599, "timestamp"]
    with pytest.raises(ValueError, match="unique"):
        chronological_windows(frame, (0.6, 0.15, 0.1, 0.15))


@pytest.mark.parametrize("fractions", [(0.7, 0.15, 0, 0.15), (0.6, 0.1, 0.1, 0.1)])
def test_invalid_experiment_partitions_are_rejected(fractions):
    with pytest.raises(ValueError, match="sum to one"):
        ExperimentConfig(split_fractions=fractions)


def test_aggregate_cost_agrees_with_existing_transaction_engine():
    labels = np.array([True, False, True, False])
    scores = np.array([0.92, 0.61, 0.34, 0.10])
    amounts = np.array([500, 70, 300, 25])
    assumptions = StrategyAssumptions(maximum_review_capacity=1)
    summary = threshold_summary(labels, scores, amounts, 0.5, assumptions)
    rows = [ScoredTransaction(transaction_id=i, amount=float(amount), fraud_probability=float(score), is_fraud=bool(label)) for i, (label, score, amount) in enumerate(zip(labels, scores, amounts))]
    expected = evaluate_strategy(rows, 0.5, assumptions)
    assert summary["total_cost"] == expected.total_strategy_cost
    assert summary["false_positives"] == expected.false_positives
    assert summary["false_negatives"] == expected.false_negatives
    assert summary["fraud_missed"] == 300


def test_policy_minimizes_declared_selection_cost_with_stable_tie_break():
    frame = pd.DataFrame({"is_fraud": [True, False, True, False], "amount": [500, 70, 300, 25]})
    scores = np.array([0.92, 0.61, 0.34, 0.10])
    selected = select_policy(frame, scores, StrategyAssumptions())
    assert selected["threshold"] == 0.34


def test_training_is_repeatable_and_test_labels_cannot_select_policy(tmp_path):
    config = ExperimentConfig(row_count=6000, seed=11, xgboost_estimators=12)
    frame = generate_transactions(config.row_count, config.seed)
    first = run_experiment(config, tmp_path / "first", tmp_path / "first.json", frame)
    second = run_experiment(config, tmp_path / "second", tmp_path / "second.json", frame)
    assert first["predictions_sha256"] == second["predictions_sha256"]
    assert (tmp_path / "first.json").read_bytes() == (tmp_path / "second.json").read_bytes()
    mutated = frame.copy()
    mutated.loc[5100:, "is_fraud"] = ~mutated.loc[5100:, "is_fraud"]
    # An obvious target-leakage column must never enter the explicit feature list.
    mutated["future_fraud_label"] = mutated.is_fraud
    changed = run_experiment(config, tmp_path / "changed", frame=mutated)
    first_scores = pd.read_csv(tmp_path / "first" / first["study_id"] / "test_predictions.csv")
    changed_scores = pd.read_csv(tmp_path / "changed" / changed["study_id"] / "test_predictions.csv")
    for name in first["models"]:
        assert first["models"][name]["selected_threshold"] == changed["models"][name]["selected_threshold"]
        np.testing.assert_array_equal(first_scores[f"{name}_probability"], changed_scores[f"{name}_probability"])
    assert "future_fraud_label" not in changed["features"]
    snapshot = json.loads((tmp_path / "first.json").read_text())
    assert sum(bin_["count"] for bin_ in snapshot["models"]["xgboost"]["metrics"]["calibration_curve"]) == 900
