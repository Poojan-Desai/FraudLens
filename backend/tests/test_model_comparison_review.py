"""Independent pre-freeze review regressions; reserved final seed is never used."""
import json
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import average_precision_score

from backend.app.ml import model_comparison as comparison


@pytest.fixture(scope="module")
def review_run(tmp_path_factory):
    folder = tmp_path_factory.mktemp("comparison-independent-review")
    development = folder / "development.json"
    development.write_text('{"fixture": "independent review, not screening evidence"}\n')
    protocol = folder / "protocol.md"
    protocol.write_text("Tiny alternate-seed fixture. No production final evaluation.\n")
    plan = comparison.ComparisonPlan(
        candidate=comparison.Candidate(id="review_fixture", weight_rule="one", max_depth=2, n_estimators=4),
        development_seeds=(1, 2, 3), fit_seed=31, fit_generated_rows=6000,
        final_seed=32, final_rows=1000, reported_budgets=(0.02,),
        bootstrap_replicates=100, bootstrap_seed=812,
    )
    plan_path = folder / "frozen.json"
    comparison.freeze_plan(plan_path, plan, development, protocol)
    report = comparison.run_comparison(plan_path, folder / "runs")
    return folder / "runs" / report["plan_id"]


def test_review_fixture_verifies_without_loading_models(review_run, monkeypatch):
    monkeypatch.setattr(comparison.joblib, "load", lambda *_a, **_kw: pytest.fail("verifier must not load executable model bundles"))
    assert comparison.verify_comparison(review_run)["status"] == "verified"


def test_plan_rejects_budget_that_rounds_to_zero_before_any_data_generation():
    with pytest.raises(ValueError, match="budget|alert|capacity"):
        comparison.ComparisonPlan(
            candidate=comparison.Candidate(id="review", weight_rule="one", max_depth=2, n_estimators=4),
            final_rows=1000, reported_budgets=(0.00001, 0.02),
        )


def test_verifier_rejects_changed_primary_budget(review_run):
    path = review_run / "report.json"
    original = path.read_bytes()
    changed = json.loads(original)
    changed["primary_budget"] = 0.05
    path.write_text(json.dumps(changed))
    try:
        with pytest.raises(ValueError, match="budget|frozen|plan"):
            comparison.verify_comparison(review_run, recompute_intervals=False)
    finally:
        path.write_bytes(original)


def test_verifier_rejects_missing_model_artifact(review_run):
    path = review_run / "challenger.joblib"
    original = path.read_bytes()
    path.unlink()
    try:
        with pytest.raises((ValueError, FileNotFoundError), match="model|artifact|challenger|No such file"):
            comparison.verify_comparison(review_run, recompute_intervals=False)
    finally:
        path.write_bytes(original)


def test_verifier_rejects_altered_model_bytes(review_run):
    path = review_run / "incumbent.joblib"
    original = path.read_bytes()
    path.write_bytes(original + b"accidental damage")
    try:
        with pytest.raises(ValueError, match="model|artifact|hash|checksum"):
            comparison.verify_comparison(review_run, recompute_intervals=False)
    finally:
        path.write_bytes(original)


def test_paired_bootstrap_uses_original_id_ties_not_random_draw_order():
    labels = np.tile([True, False, False, True, False, True, False, False], 8)
    old = np.tile([0.5, 0.5, 0.5, 0.2, 0.2, 0.2, 0.1, 0.1], 8)
    new = np.tile([0.5, 0.5, 0.2, 0.5, 0.2, 0.2, 0.1, 0.1], 8)
    count, seed, fraction = 200, 63, 0.25
    rng = np.random.default_rng(seed)
    ap, recalls = [], []
    for _ in range(count):
        # Sorting preserves bootstrap row multiplicity and restores original IDs.
        ids = np.sort(rng.integers(0, len(labels), len(labels)), kind="stable")
        target, incumbent, challenger = labels[ids], old[ids], new[ids]
        ap.append(average_precision_score(target, challenger) - average_precision_score(target, incumbent))
        recalls.append(comparison.budget_metrics(target, challenger, fraction)["recall"] - comparison.budget_metrics(target, incumbent, fraction)["recall"])
    actual = comparison.paired_intervals(labels, old, new, fraction, count, seed)
    np.testing.assert_allclose(
        [actual["average_precision_delta_95"]["lower"], actual["average_precision_delta_95"]["upper"]],
        np.quantile(ap, [.025, .975]), rtol=0, atol=1e-15,
    )
    np.testing.assert_allclose(
        [actual["primary_budget_recall_delta_95"]["lower"], actual["primary_budget_recall_delta_95"]["upper"]],
        np.quantile(recalls, [.025, .975]), rtol=0, atol=1e-15,
    )
