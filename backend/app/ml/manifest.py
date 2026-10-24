"""Descriptive provenance and quality evidence; does not change generated data."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path

import pandas as pd

from .validation import validate_schema


def dataset_manifest(frame: pd.DataFrame, seed: int, dataset_hash: str, generation_timestamp: str | None = None) -> dict:
    validate_schema(frame, "synthetic")
    numeric = frame.select_dtypes(include="number")
    return {
        "manifest_schema_version": 1, "dataset_id": f"synthetic_strategy_v1-{dataset_hash[:16]}",
        "generator_version": "synthetic_strategy_v1", "schema_version": 1, "random_seed": seed,
        "generation_timestamp": generation_timestamp,
        "manifest_created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": dataset_hash,
        "generator_sha256": hashlib.sha256(Path(__file__).with_name("synthetic.py").read_bytes()).hexdigest(),
        "row_count": len(frame), "fraud_rows": int(frame.is_fraud.sum()), "fraud_prevalence": float(frame.is_fraud.mean()),
        "features": {
            "timestamp": "Synthetic transaction time at fixed three-minute intervals; not an account event history.",
            "amount": "Simulated transaction dollars, rounded to cents.",
            "merchant_category": "Sampled merchant category.", "country": "Sampled country conditional on international status.",
            "distance_from_home": "Sampled distance in miles, conditional on international status.",
            "transactions_last_hour": "Sampled Poisson count, not computed from linked entities.",
            "average_amount_30d": "Sampled customer average, not computed from prior events.",
            "amount_to_customer_average": "Amount divided by sampled average before independent rounding.",
            "new_device": "Sampled device novelty indicator.", "card_present": "Simulated physical-card indicator.",
            "account_age_days": "Sampled account age; no persistent account identifier.",
            "is_international": "Sampled international indicator.", "previous_declines": "Sampled prior-decline count.",
            "is_fraud": "Bernoulli-sampled outcome from hand-written nonlinear risk process; excluded from model features.",
            "dataset_source": "Generator version metadata; excluded from model features.",
        },
        "label_methodology": "Bernoulli draws from sigmoid(-7 + device, international, velocity, decline, amount-ratio, card-presence, distance, merchant and device/international interaction terms); no realized label enters features.",
        "quality": {"missing_by_column": {key: int(value) for key, value in frame.isna().sum().items()},
                    "duplicate_rows": int(frame.duplicated().sum()), "duplicate_timestamps": int(frame.timestamp.duplicated().sum()),
                    "numeric_distribution": numeric.describe(percentiles=[.01, .5, .99]).to_dict(),
                    "category_counts": {name: {str(key): int(value) for key, value in frame[name].value_counts().items()} for name in ("merchant_category", "country")}},
        "known_realism_limitations": ["Hand-written stationary risk process; models can learn these synthetic rules, not validated bank behavior.",
            "No linked customer/device/merchant entities; sampled velocity and account history are not relationally reconstructed.",
            "Fixed timestamp cadence; no seasonality, delayed outcomes or temporal concept drift.",
            "Synthetic labels are available immediately for evaluation; analyst decisions must remain separate."]}
