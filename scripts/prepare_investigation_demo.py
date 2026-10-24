"""Import verified saved predictions without deserializing model artifacts.

Creates an isolated local SQLite demo and ignored mode-0600 credentials. No
network activity, labels copied into cases, or Git-tracked secrets.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shlex

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.auth import Principal
from backend.app.case_schemas import CaseSnapshot
from backend.app.database import Base
from backend.app.ml.experiment import FEATURES
from backend.app.ml.synthetic import generate_transactions
from backend.app.ml.verify import verify_study
from backend.app.models import InvestigationCase
from backend.app.services.cases import create_case
import pandas as pd


def prepare(study: Path, output: Path):
    verification = verify_study(study)
    report = json.loads((study / "report.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    database = output.resolve() / "investigations.db"
    engine = create_engine(f"sqlite:///{database}")
    Base.metadata.create_all(engine)
    rows = pd.read_csv(study / "test_predictions.csv", float_precision="round_trip")
    model = report["models"]["xgboost"]
    flagged = rows[rows.xgboost_probability >= model["selected_threshold"]].sort_values("xgboost_probability", ascending=False).head(12)
    source = generate_transactions(report["config"]["row_count"], report["config"]["seed"])
    # Evidence verifier hashes predictions; regeneration binds readable features
    # to the same complete dataset checksum before importing any transaction.
    import hashlib
    if hashlib.sha256(source.to_csv(index=False, lineterminator="\n").encode()).hexdigest() != report["dataset"]["sha256"]:
        raise ValueError("Regenerated dataset checksum does not match study")
    created = 0
    with Session(engine) as db:
        for _, row in flagged.iterrows():
            if db.scalar(select(InvestigationCase.id).where(InvestigationCase.transaction_id == row.transaction_id)):
                continue
            feature_row = source.iloc[int(row.transaction_id.removeprefix("EVAL-"))]
            timestamp = pd.Timestamp(feature_row.timestamp).tz_localize("UTC")
            if timestamp != pd.Timestamp(row.timestamp) or float(feature_row.amount) != float(row.amount):
                raise ValueError("Prediction and feature row differ")
            features = {key: feature_row[key].item() if hasattr(feature_row[key], "item") else feature_row[key] for key in FEATURES if key not in {"amount", "country", "merchant_category"}}
            reasons = ["Observed features, not SHAP or causal explanations"]
            if bool(feature_row.new_device):
                reasons.append("New device indicator")
            if bool(feature_row.is_international):
                reasons.append("International transaction indicator")
            if feature_row.transactions_last_hour >= 3:
                reasons.append(f"Sampled velocity: {feature_row.transactions_last_hour} transactions/hour")
            create_case(db, CaseSnapshot(transaction_id=row.transaction_id, timestamp=timestamp.to_pydatetime(), amount=row.amount,
                merchant_category=feature_row.merchant_category, country=feature_row.country,
                fraud_probability=row.xgboost_probability, threshold=model["selected_threshold"],
                model_version=f'{report["study_id"]}:xgboost', source="verified_synthetic_study", features=features, reason_codes=reasons), Principal("study-import", "admin"))
            created += 1
    env_path = output / "environment.sh"
    if not env_path.exists():
        tokens = {role: secrets.token_urlsafe(32) for role in ("analyst", "admin", "viewer")}
        identities = {token: {"actor": f"demo-{role}", "role": role} for role, token in tokens.items()}
        env = {"FRAUDLENS_DATABASE_URL": f"sqlite:///{database}", "FRAUDLENS_CASE_TOKENS": json.dumps(identities)}
        env.update({f"FRAUDLENS_DEMO_{role.upper()}_TOKEN": token for role, token in tokens.items()})
        fd = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write("# Local synthetic demo credentials. Never publish this file.\n")
            handle.writelines(f"export {key}={shlex.quote(value)}\n" for key, value in env.items())
    engine.dispose()
    print(json.dumps({**verification, "cases_created": created, "flagged_candidates": len(flagged), "database": str(database), "environment_file": str(env_path), "ground_truth_copied": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("study", type=Path)
    parser.add_argument("--output", type=Path, default=Path("work/investigation-demo"))
    args = parser.parse_args()
    prepare(args.study, args.output)
