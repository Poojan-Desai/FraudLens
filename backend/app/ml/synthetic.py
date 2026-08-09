from __future__ import annotations

import numpy as np
import pandas as pd


MERCHANT_CATEGORIES = np.array(["grocery", "dining", "fuel", "travel", "electronics", "digital_services", "healthcare", "luxury_goods"])
COUNTRIES = np.array(["United States", "Canada", "United Kingdom", "Spain", "Romania", "Singapore", "Brazil", "India"])


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(values, -30, 30)))


def generate_transactions(count: int = 75_000, seed: int = 42) -> pd.DataFrame:
    """Generate a deterministic, readable strategy dataset.

    The label is sampled from a nonlinear risk process and is intentionally kept
    separate from input features so downstream pipelines can enforce no leakage.
    """
    if count < 100:
        raise ValueError("count must be at least 100")

    rng = np.random.default_rng(seed)
    timestamps = pd.date_range("2025-01-01", periods=count, freq="3min")
    average_amount_30d = np.maximum(8, rng.lognormal(mean=3.75, sigma=0.72, size=count))
    amount_multiplier = rng.lognormal(mean=-0.04, sigma=0.79, size=count)
    amount = np.maximum(1, average_amount_30d * amount_multiplier)
    new_device = rng.binomial(1, 0.075, count)
    card_present = rng.binomial(1, 0.61, count)
    is_international = rng.binomial(1, 0.085, count)
    transactions_last_hour = np.minimum(rng.poisson(1.1, count), 16)
    previous_declines = np.minimum(rng.poisson(0.18, count), 8)
    distance_from_home = np.where(is_international, rng.gamma(3.0, 650, count), rng.gamma(1.5, 12, count))
    account_age_days = rng.integers(14, 4_500, count)
    merchant_category = rng.choice(MERCHANT_CATEGORIES, count, p=[.22, .2, .12, .09, .1, .12, .1, .05])
    country = np.where(is_international == 1, rng.choice(COUNTRIES[1:], count), "United States")
    amount_ratio = amount / average_amount_30d

    logit = (
        -7.0
        + 2.10 * new_device
        + 1.60 * is_international
        + 0.38 * transactions_last_hour
        + 0.70 * previous_declines
        + 1.20 * (amount_ratio > 3)
        + 0.65 * (card_present == 0)
        + 1.10 * (distance_from_home > 1_500)
        + 0.90 * np.isin(merchant_category, ["electronics", "luxury_goods"])
        + 1.40 * ((new_device == 1) & (is_international == 1))
    )
    probability = _sigmoid(logit)
    is_fraud = rng.binomial(1, probability)

    return pd.DataFrame({
        "timestamp": timestamps,
        "amount": amount.round(2),
        "merchant_category": merchant_category,
        "country": country,
        "distance_from_home": distance_from_home.round(2),
        "transactions_last_hour": transactions_last_hour,
        "average_amount_30d": average_amount_30d.round(2),
        "amount_to_customer_average": amount_ratio.round(3),
        "new_device": new_device.astype(bool),
        "card_present": card_present.astype(bool),
        "account_age_days": account_age_days,
        "is_international": is_international.astype(bool),
        "previous_declines": previous_declines,
        "is_fraud": is_fraud.astype(bool),
        "dataset_source": "synthetic_strategy_v1",
    })


def time_split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ordered = frame.sort_values("timestamp").reset_index(drop=True)
    train_end = int(len(ordered) * 0.70)
    validation_end = int(len(ordered) * 0.85)
    return ordered.iloc[:train_end].copy(), ordered.iloc[train_end:validation_end].copy(), ordered.iloc[validation_end:].copy()
