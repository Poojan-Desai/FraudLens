# FraudLens synthetic study model card

**Intended use:** local educational comparison of fraud scoring, calibration,
illustrative cost policies and investigator accountability. Not credit decisions,
real transaction blocking, or proof of bank-fraud detection performance.

**Study:** `7287a6f8b6ef04ba`; generator `synthetic_strategy_v1`; seed 42;
75,000 rows / 823 positives. Canonical dataset SHA-256 and generator/source hashes
are in `public/evaluation.json` and `dataset-manifest.json` in the saved run.
No existing raw dataset was replaced; the unchanged generator was reproduced.

**Inputs:** explicit twelve-feature allowlist in `experiment.FEATURES`; transaction
amount, merchant/category/country, sampled distance, history/velocity, device,
card presence, account age, international indicator, prior declines and derived
amount ratio. Label, timestamp and dataset-source metadata are excluded.
No real cardholders, PANs, account identities or private bank data are collected.

**Method:** fixed estimator hyperparameters; preprocessing and estimator fit only
on earliest 45,000 rows; frozen fitted pipeline sigmoid-calibrated on next 11,250;
cost threshold selected only on next 7,500; final metrics on locked last 11,250.
Test-label mutation leaves model scores and selected policy unchanged (regression
test). Test sensitivity curves are exploratory, not policy validation. No
out-of-time external dataset, hyperparameter search, bootstrap confidence interval
or deployment champion-selection procedure is implemented.

**Baseline:** training-label prevalence 0.01113333, applied as a constant score.
Its policy uses the same selection-only grid and tie break. Test average
precision 0.01137778; Brier 0.01124838; ROC-AUC 0.5; cost $6,728.51.

**Calibrated logistic regression:** threshold 0.32; precision 0.54545;
recall 0.09375; F1 0.16000; average precision 0.21135; ROC-AUC 0.85695;
Brier 0.00997565; cost $6,489.69.

**Calibrated XGBoost:** threshold 0.18; precision 0.62963;
recall 0.1328125; F1 0.21935; average precision 0.24078; ROC-AUC 0.83140;
Brier 0.01026769; cost $6,108.56. Most fraud remains missed at this operating point.

**Costs:** default false-positive cost $18, manual review $1.20,
recovery 35%, whole-test-window capacity 1,400, overflow $1.65. All are
illustrative assumptions. Policies flag versus approve, not a three-way
approve/review/block queue. Python and browser share a tested half-up cent rule;
formula duplication across runtimes remains a limitation.

**Reproducibility:** same machine two full seeded runs yielded byte-identical
snapshot and test prediction CSVs. Manifest creation timestamps, training timings
and model pickle hashes are outside the deterministic public snapshot. Saved
model reload reproduces fresh prediction doubles in a trusted-artifact test.
The verifier checks hashes, feature schema, reported held-out metrics and all
99 curve points without loading pickles; it does not rerun fitting/calibration
or independently attest the study author.

**Known failure modes:** synthetic hand-written labeling rules; stationary
features; no relational histories, delayed labels or concept drift; one seed/split;
limited recall; no fairness evaluation or real-world subgroup claims. Case
reason codes describe observed inputs, not calibrated individual feature
attributions or causal explanations. Investigator judgments remain untrusted
for training and never update the generator's ground-truth labels.
