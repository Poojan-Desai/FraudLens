import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from backend.app.ml.experiment import FEATURES
from backend.app.ml.model_comparison import Candidate, ComparisonPlan, freeze_plan, run_comparison
from backend.app.ml.synthetic import generate_transactions

spec = importlib.util.spec_from_file_location("score_improved_model", Path(__file__).resolve().parents[2] / "scripts/score_improved_model.py")
scoring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scoring)


@pytest.fixture(scope="module")
def scored_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("trusted-scoring-fixture")
    (root / "dev.json").write_text('{}')
    (root / "protocol.json").write_text('{}')
    plan = ComparisonPlan(candidate=Candidate(id="test_score", weight_rule="one", max_depth=2, n_estimators=8), fit_generated_rows=6000, fit_seed=11, final_rows=1000, final_seed=123, bootstrap_replicates=100)
    freeze_plan(root / "plan.json", plan, root / "dev.json", root / "protocol.json")
    report = run_comparison(root / "plan.json", root / "runs")
    # Fixture gates are not claims of improved quality; enable only the scoring contract.
    run = root / "runs" / report["plan_id"]
    report["comparison"]["promotion_gate_passed"] = True
    (run / "report.json").write_text(json.dumps(report))
    return run


def test_untrusted_bundle_is_never_loaded(scored_run, monkeypatch):
    monkeypatch.setattr(scoring.joblib, "load", lambda *a, **k: pytest.fail("must not load without explicit trust"))
    with pytest.raises(ValueError, match="trust"):
        scoring.score_batch(scored_run, generate_transactions(100, 17), 2)


def test_actual_trusted_model_scores_without_labels_and_keeps_fixed_capacity(scored_run):
    frame = generate_transactions(100, 17)
    first = scoring.score_batch(scored_run, frame[FEATURES], 2, trust_local_artifacts=True)
    changed = frame.copy()
    changed.is_fraud = ~changed.is_fraud
    changed["future_fraud_label"] = changed.is_fraud
    second = scoring.score_batch(scored_run, changed, 2, trust_local_artifacts=True)
    np.testing.assert_array_equal(first.fraud_probability, second.fraud_probability)
    assert first.flagged_for_review.sum() == second.flagged_for_review.sum() == 2
    assert len(first) == 100


def test_bad_inputs_and_artifact_damage_fail_before_deserialization(scored_run, monkeypatch):
    frame = generate_transactions(100, 17)
    monkeypatch.setattr(scoring.joblib, "load", lambda *a, **k: pytest.fail("invalid input/artifact must fail before load"))
    with pytest.raises(ValueError, match="capacity"):
        scoring.score_batch(scored_run, frame, 101, trust_local_artifacts=True)
    bad = frame.copy()
    bad.loc[0, "amount"] = float("inf")
    with pytest.raises(ValueError, match="finite"):
        scoring.score_batch(scored_run, bad, 2, trust_local_artifacts=True)
    artifact = scored_run / "challenger.joblib"
    original = artifact.read_bytes()
    artifact.write_bytes(original + b"bad")
    try:
        with pytest.raises(ValueError, match="checksum"):
            scoring.score_batch(scored_run, frame, 2, trust_local_artifacts=True)
    finally:
        artifact.write_bytes(original)
