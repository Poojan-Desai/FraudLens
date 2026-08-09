from backend.app.ml.explain import format_top_factors


def test_explanations_are_ranked_and_business_readable():
    factors = format_top_factors(
        ["new_device", "card_present", "amount_to_customer_average"],
        [True, True, 4.2],
        [0.18, -0.07, 0.11],
    )
    assert [factor.explanation_rank for factor in factors] == [1, 2, 3]
    assert factors[0].business_label == "New device"
    assert factors[0].direction == "increases_risk"
    assert factors[-1].direction == "reduces_risk"
