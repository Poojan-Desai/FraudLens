"""Reproducible synthetic study with four disjoint chronological windows.

Hyperparameters are fixed in configuration. Calibration, policy selection and
final evaluation use distinct data; the test window never chooses a policy.
"""
from __future__ import annotations

import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import time
from typing import Any

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, precision_recall_curve, roc_auc_score
from sklearn.pipeline import Pipeline

from ..schemas import StrategyAssumptions
from ..services.money import round_cost
from .synthetic import generate_transactions
from .train import _preprocessor
from .validation import validate_schema

FEATURES = [
    "amount", "merchant_category", "country", "distance_from_home",
    "transactions_last_hour", "average_amount_30d", "amount_to_customer_average",
    "new_device", "card_present", "account_age_days", "is_international", "previous_declines",
]
WINDOWS = ("train", "calibration", "selection", "test")


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: int = Field(default=2, ge=2, le=2)
    dataset_version: str = "synthetic_strategy_v1"
    row_count: int = Field(default=75_000, ge=1_000, le=1_000_000)
    seed: int = Field(default=42, ge=0)
    split_fractions: tuple[float, float, float, float] = (0.6, 0.15, 0.1, 0.15)
    xgboost_estimators: int = Field(default=300, ge=1, le=1_000)
    assumptions: StrategyAssumptions = Field(default_factory=StrategyAssumptions)

    @model_validator(mode="after")
    def validate_partitions(self):
        if any(not np.isfinite(f) or f <= 0 for f in self.split_fractions) or not np.isclose(sum(self.split_fractions), 1):
            raise ValueError("four positive split fractions must sum to one")
        if self.dataset_version != "synthetic_strategy_v1":
            raise ValueError("unsupported dataset generator version")
        return self


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def chronological_windows(frame: pd.DataFrame, fractions: tuple[float, ...]) -> dict[str, pd.DataFrame]:
    """Fail closed when window boundaries cannot be genuinely disjoint."""
    validate_schema(frame, "synthetic")
    missing = set(FEATURES) - set(frame.columns)
    if missing:
        raise ValueError(f"missing model features: {sorted(missing)}")
    if len(fractions) != 4 or any(not np.isfinite(f) or f <= 0 for f in fractions) or not np.isclose(sum(fractions), 1):
        raise ValueError("four positive split fractions must sum to one")
    ordered = frame.copy()
    ordered["timestamp"] = pd.to_datetime(ordered["timestamp"], errors="raise", utc=True)
    if ordered["timestamp"].isna().any() or ordered["timestamp"].duplicated().any():
        raise ValueError("timestamps must be present and unique for strict chronological windows")
    ordered = ordered.sort_values("timestamp", kind="stable").reset_index(drop=True)
    boundaries = [0, *[int(len(ordered) * f) for f in np.cumsum(fractions)[:-1]], len(ordered)]
    result = {name: ordered.iloc[start:end].copy() for name, start, end in zip(WINDOWS, boundaries, boundaries[1:])}
    for name, part in result.items():
        if part.empty or part.is_fraud.nunique() != 2:
            raise ValueError(f"{name} window must contain both target classes; increase dataset size")
    return result


def threshold_summary(labels: np.ndarray, probabilities: np.ndarray, amounts: np.ndarray, threshold: float, assumptions: StrategyAssumptions) -> dict[str, Any]:
    flagged = probabilities >= threshold
    fraud = labels.astype(bool)
    tp, fp = int((flagged & fraud).sum()), int((flagged & ~fraud).sum())
    fn, tn = int((~flagged & fraud).sum()), int((~flagged & ~fraud).sum())
    missed = float(amounts[~flagged & fraud].sum())
    detected = float(amounts[flagged & fraud].sum())
    loss = missed * (1 - assumptions.fraud_recovery_rate)
    friction = fp * (assumptions.false_positive_cost + assumptions.customer_friction_cost)
    review = min(tp + fp, assumptions.maximum_review_capacity) * assumptions.manual_review_cost
    overflow = max(0, tp + fp - assumptions.maximum_review_capacity) * 1.65
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "threshold": threshold, "true_positives": tp, "false_positives": fp,
        "true_negatives": tn, "false_negatives": fn, "flagged": tp + fp,
        "precision": precision, "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "false_positive_rate": fp / (fp + tn), "review_workload": (tp + fp) / len(labels),
        "fraud_detected": round(detected, 2), "fraud_missed": round(missed, 2),
        "missed_loss": round(loss, 2), "friction_cost": round(friction, 2),
        "review_cost": round(review, 2), "capacity_overflow_cost": round(overflow, 2),
        # Shared browser convention: nearest cent, half-cent upward, then a
        # higher-threshold tie break. Tiny tolerance absorbs summation noise.
        "total_cost": round_cost(loss + friction + review + overflow),
    }


def threshold_curve(frame: pd.DataFrame, probabilities: np.ndarray, assumptions: StrategyAssumptions) -> list[dict[str, Any]]:
    return [threshold_summary(frame.is_fraud.to_numpy(), probabilities, frame.amount.to_numpy(), step / 100, assumptions) for step in range(1, 100)]


def select_policy(frame: pd.DataFrame, probabilities: np.ndarray, assumptions: StrategyAssumptions) -> dict[str, Any]:
    # Ties prefer the higher threshold (less review); no test observations enter.
    return min(threshold_curve(frame, probabilities, assumptions), key=lambda row: (row["total_cost"], -row["threshold"]))


def held_out_metrics(frame: pd.DataFrame, probabilities: np.ndarray, threshold: float, assumptions: StrategyAssumptions) -> dict[str, Any]:
    labels = frame.is_fraud.to_numpy()
    result = threshold_summary(labels, probabilities, frame.amount.to_numpy(), threshold, assumptions)
    precision, recall, _ = precision_recall_curve(labels, probabilities)
    # Keep actual curve points only; downsampling is for artifact/browser size.
    chosen = np.unique(np.linspace(0, len(recall) - 1, min(150, len(recall)), dtype=int))
    bins = []
    indices = np.minimum((probabilities * 10).astype(int), 9)
    for index in range(10):
        mask = indices == index
        if mask.any():
            bins.append({"lower": index / 10, "upper": (index + 1) / 10, "count": int(mask.sum()), "mean_probability": float(probabilities[mask].mean()), "observed_fraction": float(labels[mask].mean())})
    result.update({
        "pr_auc": float(average_precision_score(labels, probabilities)),
        "pr_auc_definition": "average_precision_score (step-weighted precision)",
        "roc_auc": float(roc_auc_score(labels, probabilities)),
        "brier_score": float(brier_score_loss(labels, probabilities)),
        "calibration_curve": bins,
        "pr_curve": [{"recall": float(recall[i]), "precision": float(precision[i])} for i in chosen[::-1]],
    })
    return result


def run_experiment(config: ExperimentConfig, output_dir: Path, snapshot_path: Path | None = None, frame: pd.DataFrame | None = None) -> dict[str, Any]:
    frame = generate_transactions(config.row_count, config.seed) if frame is None else frame
    if len(frame) != config.row_count:
        raise ValueError("dataset row count does not match configuration")
    # Canonical CSV uses every source column, including ignored metadata, for provenance.
    dataset_bytes = frame.to_csv(index=False, lineterminator="\n").encode()
    dataset_hash = hashlib.sha256(dataset_bytes).hexdigest()
    config_hash = hashlib.sha256(canonical_json(config.model_dump(mode="json"))).hexdigest()
    repository = Path(__file__).resolve().parents[3]
    source_files = ["backend/app/ml/experiment.py", "backend/app/ml/train.py", "backend/app/ml/synthetic.py", "backend/app/ml/validation.py", "backend/app/schemas.py", "backend/app/services/money.py"]
    provenance = {
        "python": platform.python_version(),
        "platform": platform.platform(), "machine": platform.machine(),
        "packages": {package: version(package) for package in ("numpy", "pandas", "scipy", "scikit-learn", "xgboost", "joblib")},
        "source_sha256": {path: hashlib.sha256((repository / path).read_bytes()).hexdigest() for path in source_files},
    }
    study_id = hashlib.sha256(canonical_json({"dataset": dataset_hash, "config": config_hash, "provenance": provenance})).hexdigest()[:16]
    parts = chronological_windows(frame, config.split_fractions)
    train, calibration, selection, test = (parts[name] for name in WINDOWS)
    run_dir = output_dir / study_id
    # Runs are immutable. A deliberate repeat uses a different --output directory.
    run_dir.mkdir(parents=True, exist_ok=False)
    predictions = test[["timestamp", "amount", "is_fraud"]].copy()
    predictions.insert(0, "transaction_id", [f"EVAL-{index:06d}" for index in test.index])
    from xgboost import XGBClassifier

    models = {
        "logistic_regression": LogisticRegression(max_iter=800, class_weight="balanced", random_state=config.seed),
        "xgboost": XGBClassifier(n_estimators=config.xgboost_estimators, max_depth=3, learning_rate=0.05, subsample=0.85, colsample_bytree=0.85, objective="binary:logistic", eval_metric="aucpr", scale_pos_weight=float((~train.is_fraud.astype(bool)).sum() / train.is_fraud.sum()), random_state=config.seed, n_jobs=1),
    }
    report: dict[str, Any] = {
        "schema_version": 2, "study_id": study_id,
        "dataset": {"version": config.dataset_version, "sha256": dataset_hash, "rows": len(frame), "fraud_rows": int(frame.is_fraud.sum()), "source": "original synthetic generator; not real payment data"},
        "config_sha256": config_hash, "config": config.model_dump(mode="json"),
        "provenance": provenance,
        "features": FEATURES,
        "windows": {name: {"rows": len(part), "fraud_rows": int(part.is_fraud.sum()), "start": part.timestamp.min().isoformat(), "end": part.timestamp.max().isoformat()} for name, part in parts.items()},
        "methodology": "Fixed hyperparameters; fit preprocessing/model on train, sigmoid calibration on calibration, minimum business cost on selection, one final test evaluation. Grid 0.01–0.99; costs rounded to cents (half upward, 1e-7 cent summation tolerance); ties choose higher threshold. No test-based model champion or threshold selection.",
        "environment": {"platform": platform.platform(), "machine": platform.machine()},
        "models": {},
        "limitations": ["Synthetic stationary risk process; chronological order does not establish real-world temporal generalization.", "No real-data benchmark, causal explanation, deployment monitoring or hiring/financial outcome guarantee.", "Calibration is measured on test; no calibration or policy tuning uses test labels.", "Test threshold curves are exploratory sensitivity analysis; deployable policy was fixed on selection.", "Review capacity applies to the entire displayed evaluation window, not a daily arrival rate.", "Single seeded split; no uncertainty intervals or cross-environment bitwise reproducibility claim."],
    }
    for name, estimator in models.items():
        pipeline = Pipeline([("preprocess", _preprocessor(FEATURES)), ("model", estimator)])
        started = time.perf_counter()
        pipeline.fit(train[FEATURES], train.is_fraud)
        calibrated = CalibratedClassifierCV(FrozenEstimator(pipeline), method="sigmoid")
        calibrated.fit(calibration[FEATURES], calibration.is_fraud)
        training_seconds = time.perf_counter() - started
        selected = select_policy(selection, calibrated.predict_proba(selection[FEATURES])[:, 1], config.assumptions)
        probability = calibrated.predict_proba(test[FEATURES])[:, 1]
        predictions[f"{name}_probability"] = probability
        artifact_path = run_dir / f"{name}.joblib"
        joblib.dump({"calibrated_model": calibrated, "raw_pipeline": pipeline, "feature_columns": FEATURES, "study_id": study_id}, artifact_path)
        report["models"][name] = {
            "name": "Calibrated XGBoost" if name == "xgboost" else "Calibrated Logistic Regression",
            "parameters": {key: "nan" if isinstance(value, float) and not np.isfinite(value) else value for key, value in estimator.get_params().items()},
            "selected_threshold": selected["threshold"], "selection_cost": selected["total_cost"],
            "selection_thresholds": threshold_curve(selection, calibrated.predict_proba(selection[FEATURES])[:, 1], config.assumptions),
            "metrics": held_out_metrics(test, probability, selected["threshold"], config.assumptions),
            "test_thresholds": threshold_curve(test, probability, config.assumptions),
            "training_and_calibration_seconds": training_seconds,
            "artifact_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
        }
    prediction_bytes = predictions.to_csv(index=False, lineterminator="\n").encode()
    (run_dir / "test_predictions.csv").write_bytes(prediction_bytes)
    report["predictions_sha256"] = hashlib.sha256(prediction_bytes).hexdigest()
    (run_dir / "config.json").write_bytes(canonical_json(config.model_dump(mode="json")))
    (run_dir / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    if snapshot_path:
        # Public snapshot is deterministic: exclude machine timing and pickle hashes.
        snapshot = {key: value for key, value in report.items() if key != "environment"}
        snapshot["models"] = {name: {key: value for key, value in model.items() if key not in {"training_and_calibration_seconds", "artifact_sha256"}} for name, model in report["models"].items()}
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(snapshot, indent=2, allow_nan=False) + "\n")
    return report
