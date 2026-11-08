# FraudLens development-only candidate recommendation

Frozen proposal: **unit_d2_300_regularized**.

Mean selection AP: baseline 0.294973; candidate 0.347316.
Mean selection recall at 150 / 7500 reviews: baseline 0.447668; candidate 0.463382.

| Candidate | Mean selection AP | AP sample SD | Mean recall @ top 2% |
| --- | ---: | ---: | ---: |
| unit_d2_300_regularized | 0.347316 | 0.073166 | 0.463382 |
| unit_d2_600_regularized | 0.331347 | 0.080529 | 0.459551 |
| unit_d3_300_regularized | 0.330092 | 0.081761 | 0.455616 |
| unit_d3_300_default | 0.327175 | 0.069598 | 0.439515 |
| sqrt_d2_600_regularized | 0.323500 | 0.077286 | 0.439229 |
| unit_d4_300_regularized | 0.316073 | 0.089606 | 0.439515 |
| sqrt_d3_300_default | 0.312997 | 0.079770 | 0.447565 |
| unit_d3_600_regularized | 0.312047 | 0.087922 | 0.435683 |
| baseline_existing | 0.294973 | 0.080198 | 0.447668 |
| unit_d4_600_regularized | 0.290925 | 0.086744 | 0.430791 |
| sqrt_d3_600_regularized | 0.277189 | 0.077455 | 0.435968 |
| sqrt_d4_600_regularized | 0.259707 | 0.064969 | 0.440758 |

## Exact candidate

```json
{
  "id": "unit_d2_300_regularized",
  "weight_rule": "one",
  "parameters": {
    "learning_rate": 0.05,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "objective": "binary:logistic",
    "eval_metric": "aucpr",
    "n_jobs": 1,
    "max_depth": 2,
    "n_estimators": 300,
    "min_child_weight": 5,
    "reg_lambda": 5
  }
}
```

This is development model selection, not a final result. The candidate was chosen by mean selection AP across development seeds 11, 29 and 73, with mean selection recall at a fixed top-2% budget as the secondary tie break. Sigmoid calibration uses a separate 11,250-row calibration window. Original feature allowlist and preprocessing are unchanged. Only training/calibration/selection data were retained. Remaining test rows were discarded without inspection. No final holdout was generated or inspected.

The full JSON retains per-seed results, resolved parameters, timing, source hashes and versions. A controlled fresh holdout must compare the frozen baseline and proposal under a frozen protocol before any stronger model-improvement claim. No real-world fraud-detection or bank-savings claim follows from this screen.

## Baseline and proposal by development seed

| Seed | Selection fraud labels | Baseline AP | Proposal AP | Baseline TP / alerts | Proposal TP / alerts | Baseline recall | Proposal recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 11 | 87 | 0.353751 | 0.399209 | 42 / 150 | 45 / 150 | 48.2759% | 51.7241% |
| 29 | 79 | 0.327556 | 0.379108 | 37 / 150 | 38 / 150 | 46.8354% | 48.1013% |
| 73 | 74 | 0.203611 | 0.263632 | 29 / 150 | 29 / 150 | 39.1892% | 39.1892% |

The AP gain appeared on all three development seeds; fixed-budget recall improved on two seeds and was unchanged on the third. These selection data chose the proposal, so the apparent gain is optimistic development evidence. Sample standard deviations describe variation across these three synthetic seeds; they are not confidence intervals or a significance test.

## Exact differences from the baseline

The estimator family, 300 trees, learning rate 0.05, subsampling 0.85, column subsampling 0.85, binary logistic objective, aucpr training metric, seed convention, original features and preprocessor, and separate sigmoid calibration are preserved. The proposal lowers max_depth from 3 to 2, replaces the training negative/positive class weight with 1, sets min_child_weight to 5 and reg_lambda to 5, replacing the baseline’s unspecified library defaults. The full resolved wrapper parameters for every fitted estimator are retained in JSON.

## Provenance and validation

Protocol canonical SHA-256: `db9b8829222064e0c8a196694cb2d4e1becd593501eef16671216e21c6754204`. Python 3.13.1; numpy 2.3.2, pandas 2.2.3, scipy 1.18.1, scikit-learn 1.7.1, xgboost 3.0.3, joblib 1.5.1, threadpoolctl 3.8.0. Repository head at screening: `8664e8ccba912017ab539cf466b28d9d9d0eb44a`. All 36 fits completed in 32.72 seconds on the recorded Mac environment; no general runtime improvement is claimed. The artifact consistency checks passed and are recorded in `screen-consistency-checks.json`. The script and all exploration artifacts reside outside the repository.
