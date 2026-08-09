import pandas as pd
import pytest

from backend.app.ml.synthetic import generate_transactions
from backend.app.ml.validation import validate_schema


def test_synthetic_schema_validation_accepts_generated_data():
    validate_schema(generate_transactions(200), "synthetic")


def test_schema_validation_reports_missing_columns():
    with pytest.raises(ValueError, match="missing columns"):
        validate_schema(pd.DataFrame({"amount": [5], "is_fraud": [False]}), "synthetic")
