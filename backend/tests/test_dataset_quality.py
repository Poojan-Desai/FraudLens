import hashlib

import pandas as pd
import pytest

from backend.app.ml.experiment import ExperimentConfig, chronological_windows, run_experiment
from backend.app.ml.manifest import dataset_manifest
from backend.app.ml.synthetic import generate_transactions
from backend.app.ml.validation import validate_schema
from backend.app.ml.verify import verify_study


@pytest.mark.parametrize("column,value,match", [
    ("country", None, "nonmissing"), ("new_device", None, "nonmissing"),
    ("country", "unknown", "unexpected country"), ("merchant_category", "other", "unexpected merchant_category"),
    ("transactions_last_hour", -1, "nonnegative integers"), ("previous_declines", 1.5, "nonnegative integers"),
    ("account_age_days", -1, "nonnegative integers"), ("distance_from_home", -1, "nonnegative"),
    ("average_amount_30d", 0, "positive"), ("timestamp", pd.Timestamp("1900-01-01"), "supported synthetic range"),
])
def test_quality_assertions_reject_inconsistent_data(column, value, match):
    frame = generate_transactions(100)
    frame[column] = frame[column].astype(object) if value is None else frame[column]
    if isinstance(value, float):
        frame[column] = frame[column].astype(float)
    frame.loc[0, column] = value
    with pytest.raises(ValueError, match=match):
        validate_schema(frame, "synthetic")


def test_duplicate_and_empty_datasets_are_rejected():
    frame = generate_transactions(100)
    with pytest.raises(ValueError, match="duplicate"):
        validate_schema(pd.concat([frame, frame.iloc[:1]]), "synthetic")
    with pytest.raises(ValueError, match="empty"):
        validate_schema(frame.iloc[:0], "synthetic")


def test_no_positive_labels_fail_closed_before_training():
    frame = generate_transactions(1000)
    frame["is_fraud"] = False
    with pytest.raises(ValueError, match="both target classes"):
        chronological_windows(frame, (.6, .15, .1, .15))


def test_manifest_describes_quality_and_preserves_input():
    frame = generate_transactions(1000)
    before = frame.copy(deep=True)
    checksum = hashlib.sha256(frame.to_csv(index=False, lineterminator="\n").encode()).hexdigest()
    manifest = dataset_manifest(frame, 42, checksum, "2026-10-24T00:00:00+00:00")
    assert manifest["dataset_sha256"] == checksum and manifest["row_count"] == 1000
    assert manifest["quality"]["duplicate_rows"] == 0
    assert sum(manifest["quality"]["missing_by_column"].values()) == 0
    assert manifest["fraud_prevalence"] == frame.is_fraud.mean()
    assert "sampled" in manifest["known_realism_limitations"][1]
    pd.testing.assert_frame_equal(frame, before)


def test_prevalence_baseline_and_manifest_integrity(tmp_path):
    import json
    config = ExperimentConfig(row_count=6000, seed=11, xgboost_estimators=3)
    report = run_experiment(config, tmp_path)
    baseline = report["baselines"]["train_prevalence"]
    assert baseline["probability"] == report["windows"]["train"]["fraud_rows"] / 3600
    assert baseline["metrics"]["roc_auc"] == .5
    assert baseline["metrics"]["pr_auc"] == report["windows"]["test"]["fraud_rows"] / 900
    path = tmp_path / report["study_id"]
    assert verify_study(path)["status"] == "verified"
    # Only trusted freshly trained bundles are loaded, after checksum verification.
    # Public report verification itself never deserializes executable pickle.
    import joblib
    import numpy as np
    from backend.app.ml.experiment import FEATURES
    frame = generate_transactions(config.row_count, config.seed)
    test = chronological_windows(frame, config.split_fractions)["test"]
    saved = pd.read_csv(path / "test_predictions.csv", float_precision="round_trip")
    for name in report["models"]:
        bundle = joblib.load(path / f"{name}.joblib")
        assert bundle["feature_columns"] == FEATURES
        np.testing.assert_array_equal(bundle["calibrated_model"].predict_proba(test[FEATURES])[:, 1], saved[f"{name}_probability"])
    original = (path / "report.json").read_text()
    invalid_report = json.loads(original)
    invalid_report["features"] = ["future_label"]
    (path / "report.json").write_text(json.dumps(invalid_report))
    with pytest.raises(ValueError, match="incompatible feature schema"):
        verify_study(path)
    (path / "report.json").write_text(original)
    manifest = json.loads((path / "dataset-manifest.json").read_text())
    manifest["row_count"] += 1
    (path / "dataset-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest hash"):
        verify_study(path)
