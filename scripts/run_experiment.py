"""Run from repository root: PYTHONPATH=. python scripts/run_experiment.py."""
import argparse
import json
from pathlib import Path

from backend.app.ml.experiment import ExperimentConfig, run_experiment


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train, calibrate, select policy, then evaluate held-out synthetic transactions")
    parser.add_argument("--config", type=Path, default=Path("configs/synthetic-v2.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/runs"))
    parser.add_argument("--snapshot", type=Path, help="Explicitly refresh the committed browser evidence JSON")
    args = parser.parse_args()
    try:
        report = run_experiment(ExperimentConfig.model_validate_json(args.config.read_text()), args.output, args.snapshot)
    except FileExistsError as error:
        raise SystemExit(f"Immutable study directory already exists: {error.filename}. Use a new --output directory for a repeat run.") from error
    print(json.dumps({"study_id": report["study_id"], "predictions_sha256": report["predictions_sha256"], "models": {name: {key: model["metrics"][key] for key in ("threshold", "precision", "recall", "f1", "pr_auc", "roc_auc", "brier_score", "total_cost")} for name, model in report["models"].items()}}, indent=2))
