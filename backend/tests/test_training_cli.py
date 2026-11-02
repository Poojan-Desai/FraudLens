"""The legacy CLI must not bypass the supported leakage-safe study path."""
import json
import os
from pathlib import Path
import subprocess
import sys

from backend.app.ml.experiment import ExperimentConfig, FEATURES
from backend.app.ml.verify import verify_study


def test_legacy_cli_uses_four_windows_and_explicit_feature_allowlist(tmp_path):
    repository = Path(__file__).resolve().parents[2]
    config = ExperimentConfig(row_count=6000, seed=11, xgboost_estimators=3)
    config_path = tmp_path / "config.json"
    config_path.write_text(config.model_dump_json())
    # The obsolete CLI previously loaded this unconstrained CSV and selected
    # every non-excluded feature. It must no longer consume this source path.
    source = tmp_path / "data/synthetic/transactions.csv"
    source.parent.mkdir(parents=True)
    source.write_text("future_fraud_label\n1\n")
    output, snapshot = tmp_path / "runs", tmp_path / "snapshot.json"
    completed = subprocess.run(
        [sys.executable, str(repository / "scripts/train_models.py"),
         "--config", str(config_path), "--output", str(output), "--snapshot", str(snapshot)],
        cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(repository)},
        check=True, capture_output=True, text=True,
    )
    assert "Deprecated" in completed.stderr
    assert "transactions.csv is not loaded" in completed.stderr
    study_id = json.loads(completed.stdout)["study_id"]
    report = json.loads((output / study_id / "report.json").read_text())
    assert [report["windows"][name]["rows"] for name in ("train", "calibration", "selection", "test")] == [3600, 900, 600, 900]
    assert report["features"] == FEATURES
    assert "future_fraud_label" not in report["features"]
    assert json.loads(snapshot.read_text())["study_id"] == study_id
    assert verify_study(output / study_id)["status"] == "verified"
