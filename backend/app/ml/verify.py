"""Verify saved evidence without deserializing executable model bundles.

Hashes detect accidental damage, not authenticity: reports are not signed.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment import FEATURES, ExperimentConfig, canonical_json, held_out_metrics, threshold_curve


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _compare(actual, expected, path="metrics") -> None:
    if isinstance(expected, dict):
        _require(isinstance(actual, dict) and actual.keys() == expected.keys(), f"{path}: keys differ")
        for key in expected:
            _compare(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        _require(isinstance(actual, list) and len(actual) == len(expected), f"{path}: length differs")
        for index, (left, right) in enumerate(zip(actual, expected)):
            _compare(left, right, f"{path}[{index}]")
    elif isinstance(expected, (int, float)):
        _require(isinstance(actual, (int, float)) and np.isfinite(actual) and np.isclose(actual, expected, rtol=1e-12, atol=1e-12), f"{path}: value differs")
    else:
        _require(actual == expected, f"{path}: value differs")


def verify_study(run_dir: Path) -> dict:
    report = json.loads((run_dir / "report.json").read_text())
    _require(report.get("schema_version") == 2, "unsupported report schema")
    _require(report.get("features") == FEATURES, "incompatible feature schema")
    config_bytes = (run_dir / "config.json").read_bytes()
    config = ExperimentConfig.model_validate_json(config_bytes)
    _require(hashlib.sha256(config_bytes).hexdigest() == report["config_sha256"], "configuration hash mismatch")
    _require(config.model_dump(mode="json") == report["config"], "configuration differs from report")
    if "dataset_manifest_sha256" in report:
        manifest_bytes = (run_dir / "dataset-manifest.json").read_bytes()
        _require(hashlib.sha256(manifest_bytes).hexdigest() == report["dataset_manifest_sha256"], "dataset manifest hash mismatch")
        manifest = json.loads(manifest_bytes)
        _require(manifest["dataset_sha256"] == report["dataset"]["sha256"] and manifest["row_count"] == config.row_count, "dataset manifest differs")
    identity = {"dataset": report["dataset"]["sha256"], "config": report["config_sha256"], "provenance": report["provenance"]}
    _require(hashlib.sha256(canonical_json(identity)).hexdigest()[:16] == report["study_id"] == run_dir.name, "study identity mismatch")
    _require(sum(window["rows"] for window in report["windows"].values()) == config.row_count == report["dataset"]["rows"], "window row counts differ")
    prediction_bytes = (run_dir / "test_predictions.csv").read_bytes()
    _require(hashlib.sha256(prediction_bytes).hexdigest() == report["predictions_sha256"], "prediction hash mismatch")
    # Round-trip parsing retains the original IEEE doubles for exact PR ties.
    frame = pd.read_csv(run_dir / "test_predictions.csv", float_precision="round_trip")
    _require(len(frame) == report["windows"]["test"]["rows"] and len(frame) > 0, "test row count mismatch")
    _require(frame.transaction_id.notna().all() and frame.transaction_id.is_unique, "test IDs must be unique and present")
    _require(frame.is_fraud.notna().all() and frame.is_fraud.isin([0, 1]).all() and frame.is_fraud.nunique() == 2, "test targets must contain both binary classes")
    _require(int(frame.is_fraud.sum()) == report["windows"]["test"]["fraud_rows"], "fraud row count mismatch")
    _require(np.isfinite(frame.amount).all() and (frame.amount >= 0).all(), "test amounts must be finite and nonnegative")
    timestamps = pd.to_datetime(frame.timestamp, utc=True, errors="raise")
    _require(timestamps.notna().all() and timestamps.is_unique and timestamps.is_monotonic_increasing, "test timestamps must be strictly ordered")
    for boundary, actual in (("start", timestamps.min()), ("end", timestamps.max())):
        _require(actual == pd.Timestamp(report["windows"]["test"][boundary]), f"test {boundary} differs")
    _require(set(report["models"]) == {"logistic_regression", "xgboost"}, "unexpected model set")
    if "baselines" in report:
        baseline = report["baselines"]["train_prevalence"]
        prevalence = report["windows"]["train"]["fraud_rows"] / report["windows"]["train"]["rows"]
        _compare(baseline["probability"], prevalence, "baseline.probability")
        _compare(baseline["metrics"], held_out_metrics(frame, np.full(len(frame), prevalence), baseline["selected_threshold"], config.assumptions), "baseline.metrics")
    for name, model in report["models"].items():
        _require(hashlib.sha256((run_dir / f"{name}.joblib").read_bytes()).hexdigest() == model["artifact_sha256"], f"{name}: model hash mismatch")
        probabilities = frame[f"{name}_probability"].to_numpy()
        _require(np.isfinite(probabilities).all() and ((probabilities >= 0) & (probabilities <= 1)).all(), f"{name}: invalid probabilities")
        _require(0.01 <= model["selected_threshold"] <= 0.99, f"{name}: invalid threshold")
        expected = held_out_metrics(frame, probabilities, model["selected_threshold"], config.assumptions)
        _compare(model["metrics"], expected, name)
        _compare(model["test_thresholds"], threshold_curve(frame, probabilities, config.assumptions), f"{name}.test_thresholds")
    return {"study_id": report["study_id"], "test_rows": len(frame), "models_verified": len(report["models"]), "status": "verified"}
