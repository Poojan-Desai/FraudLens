"""Frozen, paired model comparison on an independent synthetic replication.

Development selection is separate. This module cannot search model candidates
using the final evaluation, and it never uses the exposed original test tail.
"""
from __future__ import annotations

from datetime import datetime, timezone
import gzip
import hashlib
from importlib.metadata import version
import io
import json
from pathlib import Path
import platform
import subprocess
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from .experiment import FEATURES, canonical_json, select_policy, threshold_summary
from .synthetic import generate_transactions
from .train import _preprocessor
from .validation import validate_schema
from ..schemas import StrategyAssumptions

REPOSITORY = Path(__file__).resolve().parents[3]
SOURCE_FILES = [
    "backend/app/ml/model_comparison.py", "backend/app/ml/synthetic.py",
    "backend/app/ml/train.py", "backend/app/ml/experiment.py",
    "backend/app/ml/validation.py", "backend/app/schemas.py",
    "backend/app/services/money.py",
]


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[a-z0-9_-]{1,80}$")
    weight_rule: Literal["negative_positive_ratio", "sqrt_negative_positive_ratio", "one"]
    max_depth: int = Field(ge=1, le=8)
    n_estimators: int = Field(ge=1, le=1000)
    min_child_weight: float = Field(default=1, ge=0, le=100)
    reg_lambda: float = Field(default=1, ge=0, le=100)


INCUMBENT = Candidate(id="incumbent", weight_rule="negative_positive_ratio", max_depth=3, n_estimators=300)


class ComparisonPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    candidate: Candidate
    development_seeds: tuple[int, ...] = (11, 29, 73)
    fit_seed: int = Field(default=42, ge=0)
    fit_generated_rows: int = Field(default=75000, ge=6000, le=1000000)
    final_seed: int = Field(default=20261108, ge=0)
    final_rows: int = Field(default=150000, ge=1000, le=1000000)
    primary_budget: float = Field(default=0.02, gt=0, lt=1)
    reported_budgets: tuple[float, ...] = (0.005, 0.01, 0.02, 0.05)
    bootstrap_replicates: int = Field(default=500, ge=100, le=2000)
    bootstrap_seed: int = Field(default=90210, ge=0)

    @model_validator(mode="after")
    def independent_seeds(self):
        if not self.development_seeds or len(set(self.development_seeds)) != len(self.development_seeds) or any(seed < 0 for seed in self.development_seeds):
            raise ValueError("development seeds must be distinct nonnegative integers")
        if self.final_seed in {*self.development_seeds, self.fit_seed}:
            raise ValueError("final seed must differ from all development/fit seeds")
        if self.candidate.id == INCUMBENT.id:
            raise ValueError("challenger must have its own identity")
        if len(set(self.reported_budgets)) != len(self.reported_budgets) or any(not np.isfinite(x) or not 0 < x < 1 for x in self.reported_budgets):
            raise ValueError("reported budgets must be distinct finite fractions")
        if self.primary_budget not in self.reported_budgets:
            raise ValueError("primary budget must be reported")
        if any(int(np.floor(self.final_rows * fraction)) < 1 for fraction in self.reported_budgets):
            raise ValueError("every final budget must permit at least one alert")
        return self


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_hashes() -> dict[str, str]:
    return {name: digest((REPOSITORY / name).read_bytes()) for name in SOURCE_FILES}


def environment() -> dict:
    return {"python": platform.python_version(), "platform": platform.platform(),
            "packages": {name: version(name) for name in ("numpy", "pandas", "scipy", "scikit-learn", "xgboost", "joblib")}}


def freeze_plan(path: Path, plan: ComparisonPlan, development_report: Path, protocol: Path) -> dict:
    """Write once, before final generation. Hashes bind plan to source/evidence."""
    payload = {"plan": plan.model_dump(mode="json"), "source_sha256": source_hashes(),
               "development_report_sha256": digest(development_report.read_bytes()),
               "protocol_sha256": digest(protocol.read_bytes()), "environment": environment(),
               "frozen_at_utc": datetime.now(timezone.utc).isoformat()}
    payload["plan_id"] = digest(canonical_json(payload))[:16]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(payload, handle, indent=2, allow_nan=False)
        handle.write("\n")
    return payload


def load_plan(path: Path, check_source: bool = True) -> tuple[ComparisonPlan, dict]:
    payload = json.loads(path.read_text())
    identity = {key: value for key, value in payload.items() if key != "plan_id"}
    if digest(canonical_json(identity))[:16] != payload["plan_id"]:
        raise ValueError("frozen plan identity mismatch")
    if check_source and payload["source_sha256"] != source_hashes():
        raise ValueError("source differs from frozen plan; do not silently reuse its evaluation")
    return ComparisonPlan.model_validate(payload["plan"]), payload


def fit_windows(frame: pd.DataFrame, generated_rows: int) -> dict[str, pd.DataFrame]:
    """Capture only first 85%; don't inspect or validate the exposed test tail.

    The generator is not prefix-stable: generate the original count first, then
    slice. Timestamps must already be chronological so slicing has fixed meaning.
    """
    boundaries = (0, int(generated_rows * .6), int(generated_rows * .75), int(generated_rows * .85))
    if len(frame) < boundaries[-1]:
        raise ValueError("insufficient retained development rows")
    retained = frame.iloc[:boundaries[-1]].copy()
    validate_schema(retained, "synthetic")
    # Validation precedes normalization; an excluded object's dtype must not
    # affect how sklearn interprets otherwise valid retained binary labels.
    retained["is_fraud"] = retained.is_fraud.astype(bool)
    missing = set(FEATURES) - set(retained.columns)
    if missing:
        raise ValueError(f"missing model features: {sorted(missing)}")
    if not pd.to_datetime(retained.timestamp, utc=True).is_monotonic_increasing:
        raise ValueError("retained rows must be chronological")
    parts = {name: retained.iloc[start:end].copy() for name, start, end in zip(("train", "calibration", "selection"), boundaries, boundaries[1:])}
    if any(part.is_fraud.nunique() != 2 for part in parts.values()):
        raise ValueError("each fitting window must contain both target classes")
    return parts


def estimator(spec: Candidate, labels: pd.Series, seed: int) -> XGBClassifier:
    ratio = float((~labels.astype(bool)).sum() / labels.sum())
    weight = 1.0 if spec.weight_rule == "one" else np.sqrt(ratio) if spec.weight_rule.startswith("sqrt") else ratio
    return XGBClassifier(n_estimators=spec.n_estimators, max_depth=spec.max_depth,
                         min_child_weight=spec.min_child_weight, reg_lambda=spec.reg_lambda,
                         learning_rate=.05, subsample=.85, colsample_bytree=.85,
                         objective="binary:logistic", eval_metric="aucpr",
                         scale_pos_weight=weight, random_state=seed, n_jobs=1)


def fit_models(plan: ComparisonPlan, retained: pd.DataFrame) -> tuple[dict, dict, dict]:
    parts = fit_windows(retained, plan.fit_generated_rows)
    train, calibration, selection = (parts[name] for name in ("train", "calibration", "selection"))
    fitted, summaries = {}, {}
    for name, spec in (("incumbent", INCUMBENT), ("challenger", plan.candidate)):
        model = estimator(spec, train.is_fraud, plan.fit_seed)
        pipeline = Pipeline([("preprocess", _preprocessor(FEATURES)), ("model", model)])
        pipeline.fit(train[FEATURES], train.is_fraud)
        calibrated = CalibratedClassifierCV(FrozenEstimator(pipeline), method="sigmoid")
        calibrated.fit(calibration[FEATURES], calibration.is_fraud)
        scores = calibrated.predict_proba(selection[FEATURES])[:, 1]
        policy = select_policy(selection, scores, StrategyAssumptions())
        fitted[name] = calibrated
        summaries[name] = {"candidate": spec.model_dump(), "selection_average_precision": float(average_precision_score(selection.is_fraud, scores)),
                           "selection_cost_policy_threshold": policy["threshold"],
                           "resolved_scale_pos_weight": float(model.get_params()["scale_pos_weight"])}
    windows = {name: {"rows": len(part), "fraud_rows": int(part.is_fraud.sum()),
                      "sha256": digest(part.to_csv(index=False, lineterminator="\n").encode())} for name, part in parts.items()}
    return fitted, summaries, windows


def check_arrays(labels, scores) -> tuple[np.ndarray, np.ndarray]:
    labels, scores = np.asarray(labels), np.asarray(scores, dtype=float)
    if labels.ndim != 1 or scores.ndim != 1 or len(labels) != len(scores) or not len(labels):
        raise ValueError("labels and scores must be aligned nonempty vectors")
    if not np.isin(labels, [0, 1]).all() or np.unique(labels).size != 2:
        raise ValueError("both binary target classes required")
    if not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ValueError("finite probabilities from zero to one required")
    return labels.astype(bool), scores


def budget_indices(scores: np.ndarray, fraction: float) -> np.ndarray:
    """Exactly floor(N*fraction), stable input/transaction-ID ties; no labels."""
    scores = np.asarray(scores, dtype=float)
    if scores.ndim != 1 or not len(scores) or not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ValueError("finite probability vector required")
    if not np.isfinite(fraction) or not 0 < fraction < 1:
        raise ValueError("budget fraction must lie strictly between zero and one")
    count = int(np.floor(len(scores) * fraction))
    if count < 1:
        raise ValueError("budget must permit at least one alert")
    return np.argsort(-scores, kind="stable")[:count]


def budget_metrics(labels, scores, fraction: float) -> dict:
    labels, scores = check_arrays(labels, scores)
    chosen = budget_indices(scores, fraction)
    tp, alerts, positives = int(labels[chosen].sum()), len(chosen), int(labels.sum())
    return {"budget_fraction": fraction, "alerts": alerts, "true_positives": tp,
            "false_positives": alerts - tp, "false_negatives": positives - tp,
            "true_negatives": len(labels) - positives - (alerts - tp),
            "precision": tp / alerts, "recall": tp / positives,
            "minimum_selected_score": float(scores[chosen[-1]])}


def measured_metrics(labels, scores, amounts, plan: ComparisonPlan, selected_threshold: float) -> dict:
    labels, scores = check_arrays(labels, scores)
    return {"average_precision": float(average_precision_score(labels, scores)),
            "roc_auc": float(roc_auc_score(labels, scores)), "brier_score": float(brier_score_loss(labels, scores)),
            "budgets": {str(f): budget_metrics(labels, scores, f) for f in plan.reported_budgets},
            "selection_cost_policy": threshold_summary(labels, scores, np.asarray(amounts), selected_threshold, StrategyAssumptions())}


def paired_intervals(labels, incumbent_scores, challenger_scores, fraction: float, replicates: int, seed: int) -> dict:
    labels, incumbent_scores = check_arrays(labels, incumbent_scores)
    _, challenger_scores = check_arrays(labels, challenger_scores)
    if not isinstance(replicates, int) or replicates < 2:
        raise ValueError("at least two bootstrap replicates required")
    rng, ap, recall = np.random.default_rng(seed), [], []
    for _ in range(replicates):
        # Keep original transaction-ID order within equal-score groups. Sorting
        # does not change bootstrap multiplicities, only label-blind tie order.
        sample = np.sort(rng.integers(0, len(labels), len(labels)))
        target = labels[sample]
        if np.unique(target).size != 2:
            # Sparse tiny test fixtures can draw one class; real final N is large.
            continue
        old, new = incumbent_scores[sample], challenger_scores[sample]
        ap.append(float(average_precision_score(target, new) - average_precision_score(target, old)))
        recall.append(budget_metrics(target, new, fraction)["recall"] - budget_metrics(target, old, fraction)["recall"])
    if len(ap) < max(2, int(replicates * .9)):
        raise ValueError("too few valid paired bootstrap replicates")
    def interval(values):
        lower, upper = np.quantile(values, [.025, .975], method="linear")
        return {"lower": float(lower), "upper": float(upper)}
    return {"method": "paired ordinary row bootstrap; percentile 95%, numpy linear quantiles; original-ID score ties; sklearn grouped-tie AP",
            "requested_replicates": replicates, "valid_replicates": len(ap), "seed": seed,
            "average_precision_delta_95": interval(ap), "primary_budget_recall_delta_95": interval(recall)}


def comparison_summary(metrics: dict, intervals: dict, primary_budget: float) -> dict:
    old, new = metrics["incumbent"], metrics["challenger"]
    delta = new["average_precision"] - old["average_precision"]
    recall_delta = new["budgets"][str(primary_budget)]["recall"] - old["budgets"][str(primary_budget)]["recall"]
    passed = intervals["average_precision_delta_95"]["lower"] > 0 and recall_delta >= 0
    return {"average_precision_delta": delta, "average_precision_relative_change": delta / old["average_precision"],
            "primary_budget_recall_delta": recall_delta, "intervals": intervals,
            "promotion_gate": "positive lower 95% AP-delta bound and nonnegative primary-budget recall point delta",
            "promotion_gate_passed": bool(passed),
            "claim_scope": "independent same-generator synthetic ranking comparison; not real-payment or future-time validation"}


def run_comparison(plan_path: Path, output: Path) -> dict:
    plan, frozen = load_plan(plan_path)
    run = output / frozen["plan_id"]
    run.mkdir(parents=True, exist_ok=False)
    (run / "frozen-plan.json").write_bytes(plan_path.read_bytes())
    (run / "evaluation-started.json").write_text(json.dumps({"started_at_utc": datetime.now(timezone.utc).isoformat(), "frozen_plan_sha256": digest(plan_path.read_bytes())}, indent=2))
    # Generate the original count, then discard the exposed tail before fitting.
    original = generate_transactions(plan.fit_generated_rows, plan.fit_seed)
    retained = original.iloc[:int(plan.fit_generated_rows * .85)].copy()
    del original
    models, summaries, windows = fit_models(plan, retained)
    artifact_hashes = {}
    for name, model in models.items():
        path = run / (name + ".joblib")
        joblib.dump({"calibrated_model": model, "feature_columns": FEATURES, "plan_id": frozen["plan_id"]}, path)
        artifact_hashes[path.name] = digest(path.read_bytes())
    # First generation of the reserved final replication occurs after frozen fit.
    final = generate_transactions(plan.final_rows, plan.final_seed)
    validate_schema(final, "synthetic")
    frame = final[["amount", "is_fraud"]].copy()
    frame.insert(0, "transaction_id", [f"FRESH-{i:06d}" for i in range(len(final))])
    metrics = {}
    for name, model in models.items():
        scores = model.predict_proba(final[FEATURES])[:, 1]
        frame[name + "_probability"] = scores
        metrics[name] = measured_metrics(final.is_fraud, scores, final.amount, plan, summaries[name]["selection_cost_policy_threshold"])
    intervals = paired_intervals(final.is_fraud, frame.incumbent_probability, frame.challenger_probability,
                                 plan.primary_budget, plan.bootstrap_replicates, plan.bootstrap_seed)
    compressed = gzip.compress(frame.to_csv(index=False, lineterminator="\n").encode(), mtime=0)
    (run / "test-predictions.csv.gz").write_bytes(compressed)
    report = {"schema_version": 1, "plan_id": frozen["plan_id"], "frozen_plan_sha256": digest(plan_path.read_bytes()),
              "frozen_at_utc": frozen["frozen_at_utc"], "completed_at_utc": datetime.now(timezone.utc).isoformat(),
              "features": FEATURES, "training_windows": windows, "model_specs": summaries,
              "fresh_evaluation": {"seed": plan.final_seed, "rows": len(final), "fraud_rows": int(final.is_fraud.sum()),
                                   "dataset_sha256": digest(final.to_csv(index=False, lineterminator="\n").encode()),
                                   "description": "independent draw of unchanged known stationary synthetic mechanism; timestamps restart, not future-time holdout"},
              "primary_budget": plan.primary_budget, "models": metrics,
              "comparison": comparison_summary(metrics, intervals, plan.primary_budget),
              "predictions_sha256": digest(compressed), "model_artifact_sha256": artifact_hashes,
              "provenance": {"source_sha256": frozen["source_sha256"], "environment": environment(),
                             "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPOSITORY, text=True).strip(),
                             "development_report_sha256": frozen["development_report_sha256"], "protocol_sha256": frozen["protocol_sha256"]},
              "limitations": ["Synthetic mechanism was known; real-payment performance is not established.",
                              "One final fitting seed and one independent final draw; bootstrap conditions on fitted models, not training uncertainty.",
                              "Primary top-2% budget fixed before final evaluation; precision and recall at the same alert count share one TP numerator.",
                              "Batch top-k is not a threshold-based live arrival policy. No hosted inference service is created.",
                              "Cost results use illustrative assumptions; ranking improvement does not imply improved calibration or realized savings.",
                              "Signed provenance, fairness assessment, external data, temporal drift and bank deployment remain unverified."]}
    (run / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def verify_comparison(run: Path, recompute_intervals: bool = True, require_models: bool = True) -> dict:
    """Recompute public numbers from saved predictions, never loading joblib."""
    from .verify import _compare
    report = json.loads((run / "report.json").read_text())
    plan_path = run / "frozen-plan.json"
    plan, frozen = load_plan(plan_path, check_source=False)
    if report["schema_version"] != 1 or report["features"] != FEATURES or report["plan_id"] != frozen["plan_id"] or report["frozen_plan_sha256"] != digest(plan_path.read_bytes()):
        raise ValueError("incompatible report or frozen plan")
    if report["provenance"]["source_sha256"] != frozen["source_sha256"] or report["provenance"]["development_report_sha256"] != frozen["development_report_sha256"] or report["provenance"]["protocol_sha256"] != frozen["protocol_sha256"]:
        raise ValueError("report provenance differs from frozen plan")
    if report["primary_budget"] != plan.primary_budget or report["frozen_at_utc"] != frozen["frozen_at_utc"]:
        raise ValueError("report budget or freeze time differs from plan")
    retained = generate_transactions(plan.fit_generated_rows, plan.fit_seed).iloc[:int(plan.fit_generated_rows * .85)].copy()
    parts = fit_windows(retained, plan.fit_generated_rows)
    expected_windows = {name: {"rows": len(part), "fraud_rows": int(part.is_fraud.sum()),
                              "sha256": digest(part.to_csv(index=False, lineterminator="\n").encode())} for name, part in parts.items()}
    if report["training_windows"] != expected_windows:
        raise ValueError("training-window provenance differs from regenerated source")
    data = (run / "test-predictions.csv.gz").read_bytes()
    if digest(data) != report["predictions_sha256"]:
        raise ValueError("prediction checksum mismatch")
    frame = pd.read_csv(io.BytesIO(gzip.decompress(data)), float_precision="round_trip")
    if len(frame) != plan.final_rows or report["fresh_evaluation"]["rows"] != plan.final_rows or frame.transaction_id.isna().any() or not frame.transaction_id.is_unique:
        raise ValueError("invalid evaluation rows or identities")
    if not np.isfinite(frame.amount).all() or (frame.amount < 0).any():
        raise ValueError("invalid evaluation amounts")
    if int(frame.is_fraud.sum()) != report["fresh_evaluation"]["fraud_rows"] or report["fresh_evaluation"]["seed"] != plan.final_seed:
        raise ValueError("evaluation target count/seed differs")
    expected_final = generate_transactions(plan.final_rows, plan.final_seed)
    if report["fresh_evaluation"]["dataset_sha256"] != digest(expected_final.to_csv(index=False, lineterminator="\n").encode()):
        raise ValueError("fresh dataset checksum differs from regenerated source")
    if frame.transaction_id.tolist() != [f"FRESH-{i:06d}" for i in range(len(frame))] or not np.array_equal(frame.is_fraud, expected_final.is_fraud) or not np.array_equal(frame.amount, expected_final.amount):
        raise ValueError("saved evidence rows differ from regenerated source")
    if set(report["model_artifact_sha256"]) != {"incumbent.joblib", "challenger.joblib"}:
        raise ValueError("model artifact identities differ")
    if require_models:
        for filename, expected in report["model_artifact_sha256"].items():
            if not (run / filename).is_file() or digest((run / filename).read_bytes()) != expected:
                raise ValueError("model artifact missing or checksum differs")
    metrics = {}
    for name, spec in (("incumbent", INCUMBENT), ("challenger", plan.candidate)):
        if report["model_specs"][name]["candidate"] != spec.model_dump():
            raise ValueError("reported model spec differs from frozen plan")
        expected_weight = estimator(spec, parts["train"].is_fraud, plan.fit_seed).get_params()["scale_pos_weight"]
        if report["model_specs"][name]["resolved_scale_pos_weight"] != expected_weight:
            raise ValueError("resolved training weight differs from plan")
        threshold = report["model_specs"][name]["selection_cost_policy_threshold"]
        if not np.isfinite(threshold) or not .01 <= threshold <= .99:
            raise ValueError("invalid selection threshold")
        metrics[name] = measured_metrics(frame.is_fraud, frame[name + "_probability"], frame.amount, plan, report["model_specs"][name]["selection_cost_policy_threshold"])
    _compare(report["models"], metrics)
    intervals = paired_intervals(frame.is_fraud, frame.incumbent_probability, frame.challenger_probability, plan.primary_budget, plan.bootstrap_replicates, plan.bootstrap_seed) if recompute_intervals else report["comparison"]["intervals"]
    _compare(report["comparison"], comparison_summary(metrics, intervals, plan.primary_budget))
    return {"status": "verified" if require_models else "prediction_metrics_verified", "plan_id": frozen["plan_id"], "rows": len(frame), "intervals_recomputed": recompute_intervals,
            "model_files_verified": require_models, "source_data_regenerated": True,
            "promotion_gate_passed": report["comparison"]["promotion_gate_passed"]}
