from backend.app.ml.synthetic import generate_transactions, time_split


def test_synthetic_schema_and_determinism():
    first = generate_transactions(500, seed=7)
    second = generate_transactions(500, seed=7)
    assert first.equals(second)
    assert {"amount", "new_device", "card_present", "is_fraud", "dataset_source"}.issubset(first.columns)
    assert first["is_fraud"].dtype == bool
    assert (first["amount"] > 0).all()


def test_time_split_preserves_chronology():
    train, validation, test = time_split(generate_transactions(1_000, seed=9))
    assert len(train) == 700
    assert len(validation) == 150
    assert len(test) == 150
    assert train["timestamp"].max() < validation["timestamp"].min() < test["timestamp"].min()
