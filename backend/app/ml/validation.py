from __future__ import annotations

import pandas as pd


SYNTHETIC_REQUIRED = {
    "timestamp", "amount", "merchant_category", "country", "distance_from_home",
    "transactions_last_hour", "average_amount_30d", "new_device", "card_present",
    "account_age_days", "is_international", "previous_declines", "is_fraud",
}
REAL_REQUIRED = {"Time", "Amount", "Class", *(f"V{index}" for index in range(1, 29))}


def validate_schema(frame: pd.DataFrame, source: str) -> None:
    expected = SYNTHETIC_REQUIRED if source == "synthetic" else REAL_REQUIRED
    missing = expected - set(frame.columns)
    if missing:
        raise ValueError(f"{source} dataset is missing columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError(f"{source} dataset is empty")
    target = "is_fraud" if source == "synthetic" else "Class"
    observed = set(frame[target].dropna().astype(int).unique())
    if not observed.issubset({0, 1}) or not observed:
        raise ValueError(f"{source} target must be binary")
    if frame.isna().all(axis=0).any():
        raise ValueError(f"{source} dataset contains an entirely empty column")
