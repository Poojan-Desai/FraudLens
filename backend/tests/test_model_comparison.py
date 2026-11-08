"""Comparison integrity checks use tiny fixtures, never the reserved final seed."""
import gzip
import json

import numpy as np
import pytest
from pydantic import ValidationError
from sklearn.metrics import average_precision_score

from backend.app.ml.model_comparison import (
    Candidate, ComparisonPlan, INCUMBENT, budget_indices, budget_metrics,
    comparison_summary, estimator, fit_models, fit_windows, freeze_plan,
    load_plan, paired_intervals, run_comparison, verify_comparison,
)
from backend.app.ml.synthetic import generate_transactions


@pytest.fixture()
def tiny_plan():
    return ComparisonPlan(candidate=Candidate(id="tiny_challenger", weight_rule="one", max_depth=2, n_estimators=6, min_child_weight=5, reg_lambda=5),
                          fit_seed=11, fit_generated_rows=6000, final_seed=123, final_rows=2000,
                          primary_budget=.02, bootstrap_replicates=100)


def test_budget_is_exact_and_ties_are_label_blind():
    scores = np.array([.9, .8, .8, .8, .1])
    np.testing.assert_array_equal(budget_indices(scores, .4), [0, 1])
    a = budget_metrics([1, 0, 1, 0, 0], scores, .4)
    b = budget_metrics([0, 1, 0, 1, 0], scores, .4)
    assert a["alerts"] == b["alerts"] == 2
    assert a["true_positives"] == b["true_positives"] == 1
    assert a["recall"] == .5


@pytest.mark.parametrize("fraction", [0, 1, -1, float("nan")])
def test_invalid_budget_rejected(fraction):
    with pytest.raises(ValueError):
        budget_indices(np.array([.1, .2]), fraction)


def test_plan_keeps_final_seed_independent(tiny_plan):
    with pytest.raises(ValidationError, match="final seed"):
        ComparisonPlan(**{**tiny_plan.model_dump(), "final_seed": 11})
    with pytest.raises(ValidationError, match="primary budget"):
        ComparisonPlan(**{**tiny_plan.model_dump(), "reported_budgets": [.01]})


def test_fit_does_not_validate_or_use_original_test_tail(tiny_plan):
    original = generate_transactions(6000, 11)
    parts = fit_windows(original, 6000)
    assert [len(p) for p in parts.values()] == [3600, 900, 600]
    changed = original.copy()
    changed["is_fraud"] = changed.is_fraud.astype(object)
    changed.loc[5100:, "is_fraud"] = "not a valid label"
    changed.loc[5100:, "amount"] = -100
    first, summaries, windows = fit_models(tiny_plan, original)
    second, changed_summaries, changed_windows = fit_models(tiny_plan, changed)
    assert summaries == changed_summaries and windows == changed_windows
    sample = original.iloc[:100]
    for name in first:
        np.testing.assert_array_equal(first[name].predict_proba(sample), second[name].predict_proba(sample))
        assert first[name].feature_names_in_.tolist() == second[name].feature_names_in_.tolist()


def test_incumbent_matches_existing_settings_and_candidate_is_unweighted(tiny_plan):
    labels = generate_transactions(6000, 11).iloc[:3600].is_fraud
    old = estimator(INCUMBENT, labels, 42).get_params()
    new = estimator(tiny_plan.candidate, labels, 42).get_params()
    assert old["scale_pos_weight"] == (~labels).sum() / labels.sum()
    assert old["n_estimators"] == 300 and old["max_depth"] == 3
    assert new["scale_pos_weight"] == 1 and new["max_depth"] == 2
    assert new["min_child_weight"] == new["reg_lambda"] == 5
    for key, value in {"learning_rate": .05, "subsample": .85, "colsample_bytree": .85, "n_jobs": 1, "random_state": 42}.items():
        assert old[key] == new[key] == value


def test_paired_intervals_are_identical_for_identical_models_and_repeatable():
    target = np.array([0, 1, 0, 1] * 25)
    scores = np.array([.1, .7, .1, .7] * 25)
    first = paired_intervals(target, scores, scores, .2, 100, 77)
    assert first == paired_intervals(target, scores, scores, .2, 100, 77)
    assert first["average_precision_delta_95"] == {"lower": 0, "upper": 0}
    assert first["primary_budget_recall_delta_95"] == {"lower": 0, "upper": 0}
    # Duplicate score groups must follow sklearn's grouped-tie AP convention.
    assert average_precision_score(target, np.full(100, .5)) == .5


def test_promotion_gate_does_not_hide_recall_regression():
    m = {"incumbent": {"average_precision": .2, "budgets": {"0.02": {"recall": .5}}},
         "challenger": {"average_precision": .3, "budgets": {"0.02": {"recall": .49}}}}
    intervals = {"average_precision_delta_95": {"lower": .01, "upper": .2}}
    assert not comparison_summary(m, intervals, .02)["promotion_gate_passed"]
    m["challenger"]["budgets"]["0.02"]["recall"] = .5
    assert comparison_summary(m, intervals, .02)["promotion_gate_passed"]
    intervals["average_precision_delta_95"]["lower"] = -.01
    assert not comparison_summary(m, intervals, .02)["promotion_gate_passed"]


@pytest.fixture()
def frozen(tmp_path, tiny_plan):
    development, protocol = tmp_path / "development.json", tmp_path / "protocol.json"
    development.write_text('{"fixture": true}')
    protocol.write_text('{"fixture": true}')
    path = tmp_path / "plan.json"
    freeze_plan(path, tiny_plan, development, protocol)
    return path


def test_freeze_is_immutable_and_detects_tampered_plan(frozen, tiny_plan, tmp_path):
    assert load_plan(frozen)[0] == tiny_plan
    with pytest.raises(FileExistsError):
        freeze_plan(frozen, tiny_plan, tmp_path / "development.json", tmp_path / "protocol.json")
    payload = json.loads(frozen.read_text())
    payload["plan"]["candidate"]["max_depth"] = 4
    frozen.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="identity"):
        load_plan(frozen)


def test_saved_metrics_and_ci_verify_without_deserializing_models(frozen, tmp_path, monkeypatch):
    report = run_comparison(frozen, tmp_path / "runs")
    run = tmp_path / "runs" / report["plan_id"]
    import joblib
    monkeypatch.setattr(joblib, "load", lambda *a, **kw: pytest.fail("executable model loading forbidden"))
    assert verify_comparison(run)["rows"] == 2000
    with pytest.raises(FileExistsError):
        run_comparison(frozen, tmp_path / "runs")
    path = run / "report.json"
    changed = json.loads(path.read_text())
    changed["models"]["challenger"]["average_precision"] += .1
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="average_precision"):
        verify_comparison(run, recompute_intervals=False)


def test_saved_prediction_checksum_rejects_tamper(frozen, tmp_path):
    report = run_comparison(frozen, tmp_path / "runs")
    run = tmp_path / "runs" / report["plan_id"]
    p = run / "test-predictions.csv.gz"
    p.write_bytes(gzip.compress(b'forged'))
    with pytest.raises(ValueError, match="checksum"):
        verify_comparison(run)
