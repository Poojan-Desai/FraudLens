"""Score a CSV with a trusted locally generated comparison model; no hosted API.

Never use a third-party joblib/pickle bundle. An unsigned checksum is an accident
check, not publisher authentication. Human case decisions do not enter training.
"""
import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from backend.app.ml.experiment import FEATURES
from backend.app.ml.model_comparison import load_plan


def score_batch(run: Path, frame: pd.DataFrame, capacity: int, *, trust_local_artifacts: bool = False) -> pd.DataFrame:
    if not trust_local_artifacts:
        raise ValueError("Explicit trust of your own locally generated model artifacts is required")
    if not isinstance(capacity, int) or isinstance(capacity, bool) or not 0 <= capacity <= len(frame):
        raise ValueError("capacity must be a whole number from zero to the batch size")
    if not 1 <= len(frame) <= 1000000 or set(FEATURES) - set(frame.columns):
        raise ValueError("provide 1–1,000,000 rows with all twelve required features")
    values = frame[FEATURES].copy()  # Ignore supplied labels, metadata and extra columns.
    if values.isna().any().any():
        raise ValueError("model features must be nonmissing")
    numeric = [name for name in FEATURES if name not in {"merchant_category", "country"}]
    if any(not pd.api.types.is_numeric_dtype(values[name]) for name in numeric):
        raise ValueError("numeric and indicator features must have numeric types")
    if not np.isfinite(values[numeric].to_numpy(dtype=float)).all() or (values[numeric] < 0).any().any():
        raise ValueError("numeric features must be finite and nonnegative")
    for name in ("new_device", "card_present", "is_international"):
        if not values[name].isin([0, 1]).all():
            raise ValueError("indicator features must be binary")
    if (values.average_amount_30d <= 0).any():
        raise ValueError("average_amount_30d must be positive")
    for name in ("merchant_category", "country"):
        if not values[name].map(lambda value: isinstance(value, str) and 0 < len(value.strip()) <= 80).all():
            raise ValueError("category/country must be nonempty bounded strings")
    plan_path = run / "frozen-plan.json"
    _, frozen = load_plan(plan_path, check_source=False)
    report = json.loads((run / "report.json").read_text())
    if not report["comparison"]["promotion_gate_passed"] or report["plan_id"] != frozen["plan_id"] or report["frozen_plan_sha256"] != hashlib.sha256(plan_path.read_bytes()).hexdigest():
        raise ValueError("use a successfully evaluated matching local run")
    artifact = run / "challenger.joblib"
    if hashlib.sha256(artifact.read_bytes()).hexdigest() != report["model_artifact_sha256"][artifact.name]:
        raise ValueError("model artifact checksum differs")
    bundle = joblib.load(artifact)  # Only after explicit trust; hashes are unsigned.
    if bundle["feature_columns"] != FEATURES or bundle["plan_id"] != frozen["plan_id"]:
        raise ValueError("incompatible model bundle")
    scores = bundle["calibrated_model"].predict_proba(values)[:, 1]
    if not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ValueError("model returned invalid probabilities")
    flagged = np.zeros(len(scores), dtype=bool)
    flagged[np.argsort(-scores, kind="stable")[:capacity]] = True
    return pd.DataFrame({"input_row": np.arange(len(scores)), "fraud_probability": scores,
                         "flagged_for_review": flagged, "model_plan_id": frozen["plan_id"]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--capacity", type=int, required=True)
    parser.add_argument("--trust-local-artifacts", action="store_true")
    args = parser.parse_args()
    frame = pd.read_csv(args.input, nrows=1000001, usecols=lambda name: name in FEATURES)
    result = score_batch(args.run, frame, args.capacity, trust_local_artifacts=args.trust_local_artifacts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    print(json.dumps({"rows_scored": len(result), "flagged": int(result.flagged_for_review.sum()),
                      "policy": "fixed batch capacity; descending model probability, input-row ties",
                      "limits": "synthetic-model local demonstration; scores are not real-payment assurance; no server or case write"}, indent=2))


if __name__ == "__main__":
    main()
