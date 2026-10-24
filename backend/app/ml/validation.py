from __future__ import annotations

import pandas as pd
import numpy as np


SYNTHETIC_REQUIRED = {
    "timestamp", "amount", "merchant_category", "country", "distance_from_home",
    "transactions_last_hour", "average_amount_30d", "new_device", "card_present",
    "account_age_days", "is_international", "previous_declines", "is_fraud",
}
REAL_REQUIRED = {"Time", "Amount", "Class", *(f"V{index}" for index in range(1, 29))}


def validate_schema(frame: pd.DataFrame, source: str) -> None:
    if source not in {"synthetic", "real"}:
        raise ValueError("source must be synthetic or real")
    expected = SYNTHETIC_REQUIRED if source == "synthetic" else REAL_REQUIRED
    missing = expected - set(frame.columns)
    if missing:
        raise ValueError(f"{source} dataset is missing columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError(f"{source} dataset is empty")
    target = "is_fraud" if source == "synthetic" else "Class"
    if frame[target].isna().any() or not frame[target].isin([0, 1]).all():
        raise ValueError(f"{source} target must be binary")
    if frame.isna().all(axis=0).any():
        raise ValueError(f"{source} dataset contains an entirely empty column")
    if frame[list(expected)].isna().any().any():
        raise ValueError(f"{source} required values must be nonmissing")
    numeric_required = ({"amount", "distance_from_home", "transactions_last_hour", "average_amount_30d", "account_age_days", "previous_declines"}
                        if source == "synthetic" else REAL_REQUIRED)
    if any(not pd.api.types.is_numeric_dtype(frame[column]) for column in numeric_required):
        raise ValueError(f"{source} numeric features must have numeric types")
    numeric = frame.select_dtypes(include="number")
    if not np.isfinite(numeric.to_numpy()).all():
        raise ValueError(f"{source} numeric values must be finite and nonmissing")
    amount = "amount" if source == "synthetic" else "Amount"
    if (frame[amount] < 0).any():
        raise ValueError(f"{source} amounts must be nonnegative")
    if frame.duplicated().any():
        raise ValueError(f"{source} duplicate records are not permitted")
    if source == "synthetic":
        from .synthetic import COUNTRIES, MERCHANT_CATEGORIES

        for column in ("new_device", "card_present", "is_international"):
            if not frame[column].isin([0, 1]).all():
                raise ValueError(f"{column} must be binary")
        for column in ("transactions_last_hour", "account_age_days", "previous_declines"):
            values = frame[column]
            if not pd.api.types.is_numeric_dtype(values) or (values < 0).any() or (values % 1 != 0).any():
                raise ValueError(f"{column} must contain nonnegative integers")
        for column in ("distance_from_home", "average_amount_30d"):
            if not pd.api.types.is_numeric_dtype(frame[column]) or (frame[column] < 0).any():
                raise ValueError(f"{column} must be nonnegative")
        if (frame.average_amount_30d <= 0).any():
            raise ValueError("average_amount_30d must be positive")
        for column, allowed in (("country", COUNTRIES), ("merchant_category", MERCHANT_CATEGORIES)):
            if not frame[column].isin(allowed).all():
                raise ValueError(f"unexpected {column}")
        timestamps = pd.to_datetime(frame.timestamp, errors="raise", utc=True)
        if timestamps.isna().any() or timestamps.duplicated().any():
            raise ValueError("timestamps must be present and unique")
        if not timestamps.between(pd.Timestamp("2000-01-01", tz="UTC"), pd.Timestamp("2100-01-01", tz="UTC")).all():
            raise ValueError("timestamps outside supported synthetic range 2000–2100")
