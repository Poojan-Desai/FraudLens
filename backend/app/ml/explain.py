from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


FEATURE_LABELS = {
    "new_device": "New device",
    "transactions_last_hour": "Transaction velocity",
    "is_international": "International purchase",
    "amount_to_customer_average": "Amount vs. customer average",
    "card_present": "Card physically present",
    "distance_from_home": "Distance from home",
    "previous_declines": "Previous declines",
    "account_age_days": "Account age",
    "merchant_category": "Merchant category",
}


@dataclass(frozen=True)
class ExplanationFactor:
    feature_name: str
    business_label: str
    feature_value: str
    contribution: float
    direction: str
    explanation_rank: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def format_top_factors(
    feature_names: list[str],
    feature_values: list[Any],
    contributions: list[float] | np.ndarray,
    limit: int = 5,
) -> list[ExplanationFactor]:
    if not (len(feature_names) == len(feature_values) == len(contributions)):
        raise ValueError("feature names, values, and contributions must align")
    ranked = sorted(range(len(feature_names)), key=lambda index: abs(float(contributions[index])), reverse=True)[:limit]
    return [
        ExplanationFactor(
            feature_name=feature_names[index],
            business_label=FEATURE_LABELS.get(feature_names[index], feature_names[index].replace("_", " ").title()),
            feature_value=str(feature_values[index]),
            contribution=round(float(contributions[index]), 6),
            direction="increases_risk" if float(contributions[index]) >= 0 else "reduces_risk",
            explanation_rank=rank + 1,
        )
        for rank, index in enumerate(ranked)
    ]


def explain_xgboost(raw_model: Any, transformed_rows: Any, feature_names: list[str]) -> list[list[ExplanationFactor]]:
    """Return the five strongest SHAP factors for every transformed row."""
    import shap

    explainer = shap.TreeExplainer(raw_model)
    values = np.asarray(explainer.shap_values(transformed_rows))
    dense = transformed_rows.toarray() if hasattr(transformed_rows, "toarray") else np.asarray(transformed_rows)
    return [format_top_factors(feature_names, dense[index].tolist(), values[index].tolist()) for index in range(len(dense))]
