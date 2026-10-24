import json

import numpy as np
import pytest
from pydantic import ValidationError

from backend.app.ml.experiment import ExperimentConfig, run_experiment, threshold_summary
from backend.app.ml.verify import verify_study
from backend.app.schemas import ScoredTransaction, StrategyAssumptions
from backend.app.services.cost_engine import evaluate_strategy


def test_half_cent_cost_has_same_policy_in_api_and_study():
    assumptions = StrategyAssumptions(fraud_recovery_rate=0, manual_review_cost=0)
    rows = [ScoredTransaction(transaction_id=1, amount=0.125, fraud_probability=0.1, is_fraud=True)]
    api = evaluate_strategy(rows, 0.5, assumptions)
    study = threshold_summary(np.array([1, 0]), np.array([0.1, 0.1]), np.array([0.125, 0]), 0.5, assumptions)
    assert api.total_strategy_cost == study["total_cost"] == 0.13


def test_finite_large_cost_does_not_overflow_when_scaled_to_cents():
    rows = [ScoredTransaction(transaction_id=1, amount=1e308, fraud_probability=0.1, is_fraud=True)]
    result = evaluate_strategy(rows, 0.5, StrategyAssumptions())
    assert result.total_strategy_cost == 6.5e307


@pytest.mark.parametrize("amount", [float("inf"), float("nan"), -float("inf")])
def test_api_rejects_nonfinite_amounts(amount):
    with pytest.raises(ValidationError):
        ScoredTransaction(transaction_id=1, amount=amount, fraud_probability=0.1, is_fraud=True)


@pytest.fixture()
def study(tmp_path):
    report = run_experiment(ExperimentConfig(row_count=6000, seed=11, xgboost_estimators=12), tmp_path)
    return tmp_path / report["study_id"]


def test_saved_study_verifies_without_loading_pickles(study, monkeypatch):
    import joblib
    monkeypatch.setattr(joblib, "load", lambda *args, **kwargs: pytest.fail("must not deserialize executable model artifacts"))
    assert verify_study(study)["test_rows"] == 900


@pytest.mark.parametrize("filename,error", [("test_predictions.csv", "prediction hash"), ("xgboost.joblib", "model hash"), ("config.json", "configuration hash")])
def test_saved_study_detects_corrupted_files(study, filename, error):
    path = study / filename
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match=error):
        verify_study(study)


def test_saved_study_recomputes_metrics_instead_of_trusting_report(study):
    path = study / "report.json"
    report = json.loads(path.read_text())
    report["models"]["xgboost"]["metrics"]["true_positives"] += 1
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="true_positives"):
        verify_study(study)


def test_saved_study_recomputes_all_displayed_test_thresholds(study):
    path = study / "report.json"
    report = json.loads(path.read_text())
    report["models"]["xgboost"]["test_thresholds"][0]["total_cost"] = -999999
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="test_thresholds.*total_cost"):
        verify_study(study)
