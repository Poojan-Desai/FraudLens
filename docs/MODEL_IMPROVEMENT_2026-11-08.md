# Actual model improvement — frozen synthetic replication

This release changes the trained model configuration. It is separate from the
previous cost/F1/F2 threshold controls. The original 75,000-row study and its
17/128 result remain unchanged as historical policy evidence.

## Result to lead with

On **150,000 freshly generated synthetic transactions**, containing **1,545 fraud
labels**, the development-selected challenger caught **650** fraud cases versus
**604** for the incumbent at **exactly 3,000 alerts for each model**. Recall was
42.07% versus 39.09%, precision 21.67% versus 20.13%, and false alerts 2,350 versus
2,396. The improvement is 46 additional detected cases with the same workload,
not an increase obtained by lowering a threshold and issuing more alerts.

Average precision (AP) improved from **0.248726 to 0.272632**, an absolute gain
of **0.023906** and a **9.61% relative gain**. AP is step-weighted precision over
recall, not accuracy and not trapezoidal PR-AUC. The paired ordinary row-bootstrap
95% interval for the AP difference was **[0.014947, 0.033180]**. The primary-budget
recall-difference interval was **[0.016082, 0.039533]**, or approximately **+1.61 to
+3.95 percentage points**. These are approximate percentile intervals from 500
fixed-seed replicates, conditional on the fitted models and this generator.

The predeclared gate passed: lower AP-difference interval bound above zero and
nonnegative primary-budget recall point difference. The secondary recall
interval is reported separately; precision and recall at fixed alert count share
the same true-positive numerator and are not independent corroborating studies.

## Every predeclared workload budget

| Batch review budget | Alerts per model | Incumbent fraud caught | Challenger fraud caught | Incumbent recall | Challenger recall |
|---|---:|---:|---:|---:|---:|
| 0.5% | 750 | 377 | 399 | 24.40% | 25.83% |
| 1% | 1,500 | 492 | 519 | 31.84% | 33.59% |
| **2% — primary** | **3,000** | **604** | **650** | **39.09%** | **42.07%** |
| 5% | 7,500 | 816 | 836 | 52.82% | 54.11% |

These are retrospective **batch top-k rankings** with fixed predeclared budgets,
not a daily investigator limit or a deployed real-time threshold. Ties use input
transaction-ID order, never labels, and exactly k alerts are selected. Original
transaction order is preserved for tied scores within bootstrap resamples.

## A result that did not improve

The challenger is not universally better. Its separately selection-chosen cost
threshold performed worse in this fresh replication:

| Cost-policy result under unchanged illustrative assumptions | Incumbent | Challenger |
|---|---:|---:|
| Selection-chosen threshold | 0.18 | 0.66 |
| Alerts | 529 | 236 |
| Fraud caught | 298 | 163 |
| Recall | 19.29% | 10.55% |
| Precision | 56.33% | 69.07% |
| Modeled whole-window cost | $81,248.93 | $84,405.00 |

Consequently, this release does **not** replace the original cost policy with the
challenger's 0.66 threshold or claim better cost effectiveness. The original
policy sandbox remains labeled and separate. Brier loss was 0.009268 for the
incumbent and 0.008789 for the challenger, a measured point result rather than a
newly validated general calibration or business-savings claim.

## What changed in the model

Both estimators use the unchanged twelve input features and the same numerical
imputation/scaling, categorical imputation/one-hot encoding, train-only fitting
and separate sigmoid calibration. No generator rules, labels, features, or
threshold curves in the original study were altered.

| Setting | Incumbent | Development-selected challenger |
|---|---|---|
| Trees / learning rate | 300 / 0.05 | 300 / 0.05 |
| Tree depth | 3 | 2 |
| Positive-class weight | Training negative/positive ratio, about 88.82 | 1.0 |
| Minimum child weight | 1 | 5 |
| L2 regularization (`reg_lambda`) | 1 | 5 |
| Subsample / column sample | 0.85 / 0.85 | 0.85 / 0.85 |
| Estimator seed / jobs | 42 / 1 | 42 / 1 |
| Probability calibration | Frozen estimator, separate sigmoid fit | Same method and separate data |

The combined configuration is simpler and more regularized. This comparison does
not isolate the causal contribution of each changed parameter; there was no
final-test ablation or second hyperparameter search after seeing the result.

## Selection and independent evaluation protocol

1. **Declare development search.** Twelve fixed configurations were screened on
   seeds 11, 29 and 73. For each 75,000-row generation, use only the first 45,000
   rows for training, the next 11,250 for calibration and the next 7,500 for
   selection. Discard the remaining 11,250 without prediction/evaluation.
2. **Choose on development only.** The highest mean selection AP won:
   `unit_d2_300_regularized`, mean AP 0.347316 versus incumbent 0.294973. AP improved
   on all three development seeds. These selected results are not final evidence.
   The AP maximum was unique, so alternative exact-tie rules had no effect.
3. **Freeze source and plan.** Plan `d8cc5fece5e3319e` fixes parameters, seeds,
   row counts, budgets, 500 paired replicates, seed 90210, linear percentile
   quantiles, evidence hashes, original feature allowlist and source hashes.
   It was frozen at 2026-11-08 22:42:54 UTC and published in GitHub checkpoint
   [`27d2732`](https://github.com/Poojan-Desai/FraudLens/commit/27d2732) before final
   generation. Local evaluation started at 22:43:17 UTC. Timestamps and unsigned
   hashes document the process; they are not cryptographic proof of unobservability.
4. **Fit two locked models fairly.** Generate the original 75,000 seed-42 rows,
   immediately retain only the original first 63,750, and fit both models on the
   same 45,000/11,250/7,500 train/calibration/policy-selection windows. The public
   original 11,250-row test does not select or evaluate the new model.
5. **Generate the reserved replication once.** Only after frozen fitting, create
   seed 20261108 with 150,000 rows. Score both models on these identical features.
   Model parameters, review capacity and outcome-selection rules are not changed.
6. **Evaluate and preserve all outcomes.** Save predictions, source/config hashes,
   both trusted local model bundles and the full report. Recompute point metrics,
   row-source checks and paired intervals without deserializing model bundles.
   Publish the favorable ranking result and the unfavorable cost-policy result.

The generator is not prefix-stable across different requested row counts, so
regenerating 63,750 rows would not reproduce the original training data. The new
helper generates 75,000 first and slices. It also avoids the original four-window
helper, which validates the old test labels even when they are not used for
training. New tests protect these boundaries and original-ID tie handling.

## Run or reproduce it

Install the pinned requirements in a virtual environment as in the README. The
already frozen plan must not be edited to obtain a more flattering test result.

```sh
# Reproduce the disclosed model fit/evaluation into a fresh immutable run root:
PYTHONPATH=. python scripts/compare_models.py evaluate \
  --plan configs/model-improvement-frozen-v1.json --output artifacts/reproduction

# Full local verification includes both saved model-file hashes, never joblib load:
PYTHONPATH=. python scripts/compare_models.py verify \
  artifacts/reproduction/d8cc5fece5e3319e

# Audit committed predictions/intervals/source rows without unprovided model files:
PYTHONPATH=. python scripts/compare_models.py verify \
  evidence/model-improvement-v1 --evidence-only
```

The evidence-only command explicitly reports `model_files_verified: false`.
Saved-data checks establish the numerical report and bind the recorded inputs;
they do not independently attest that the saved predictions came from the stated
model-fitting process. The full local run additionally hashed both model bundles.
Checksums are unsigned. Source and dependency versions are recorded; no general
cross-platform byte-identical training claim is made.

Development reproduction and complete per-candidate/per-seed results are in
`evidence/model-development-2026-11-08/`. Re-running the disclosed final evaluation
is reproduction, not a new independent test or an opportunity to tune against it.

## Use the improved model locally

The evaluation saves the actual calibrated challenger as `challenger.joblib` in
the ignored run directory. A bounded CSV scoring command uses that trusted local
bundle, ignores labels/extra columns, and selects exactly a caller-declared batch
capacity. It requires all twelve features and an explicit trust flag because
joblib is executable serialization; unsigned hashes are not publisher identity.
Use only bundles you generated yourself, not arbitrary downloaded models.

```sh
PYTHONPATH=. python scripts/score_improved_model.py \
  --run artifacts/reproduction/d8cc5fece5e3319e \
  --input data/synthetic/your-local-feature-batch.csv \
  --output work/scored-batch.csv --capacity 20 --trust-local-artifacts
```

Output preserves input row numbers, probabilities, review flags and plan ID. This
is a local scoring demonstration for the synthetic model, not a hosted banking
API, real-payment assurance or automatic case import. It does not change ground
truth or train from investigator decisions. Netlify hosts the report/dashboard;
model training, local scoring, case API, runtime databases and credentials remain
local and outside the static publish directory.

## Limits you must be able to explain

- The same known handcrafted stationary generator supplies development, fitting
  and final draws. Its code and feature set are unchanged, but an independent seed
  is not an external payment dataset. Timestamps restart January 1, 2025: this is
  not future-period validation, realistic account history or a drift experiment.
- Fraud labels are stochastic. Missing most fraud at a small review budget can
  coexist with a statistically supported ranking gain. Do not call 42.07% recall
  “42.07% accuracy” or present 650 as a new numerator over the old 128-case set.
- The paired percentile interval is approximate (500 replicates, relatively few
  draws in each tail). It conditions on fitted models and row resampling; it does
  not include retraining, generator uncertainty, clustered accounts or model
  selection uncertainty. No interval method/replicate count was changed after
  final evaluation to make the gate pass.
- Brier and selected-cost outcomes are secondary, not tuned promotion criteria.
  Better AP does not imply better cost policy, fair decisions, deployment
  reliability, customer benefit or real savings. The cost regression is visible.
- No fairness audit, representative payment benchmark, SSO, enterprise isolation,
  monitoring, regulatory assurance or production financial deployment is claimed.

## Responsible resume and interview wording

Candidate bullet: “Improved fraud-model average precision by 9.6% relative on a
frozen 150,000-transaction synthetic replication; detected 46 additional labeled
fraud cases at the same 3,000-alert budget, with paired-bootstrap uncertainty and
explicit cost-policy regressions.” Use only if you can explain the whole protocol
and your contribution. Retain “synthetic,” “relative” and the matched budget.

Q: **Did you just lower the threshold again?**
A: “No. I changed model weighting, depth and regularization after development-only
selection. Both final models were allowed exactly 3,000 alerts on the same fresh
150,000 rows. The challenger caught 650 versus 604, so the increase at that budget
comes from different rankings rather than additional alerts.”

Q: **Why isn't the final gain the 17.7% development gain?**
A: “Development outcomes selected the winner and can be optimistic. The frozen
candidate's independent replication gain was 9.6% relative AP. I report that final
number, not the more flattering selected development number.”

Q: **Why did the cost policy get worse if the model got better?**
A: “AP is a ranking measure. A single operating threshold, probability calibration,
transaction amounts and cost assumptions are different concerns. The challenger
cost threshold caught fewer cases and had worse modeled cost, so I retained the
old policy sandbox and exposed the regression. A client needs a policy validated
for their actual capacity and objective.”

Q: **Is this proof of real fraud-detection performance?**
A: “No. It is a controlled independent replication under one known synthetic
mechanism. Real transactions have delayed labels, correlated accounts, drift and
operational constraints that this generator does not model. The evaluation
method is stronger; the dataset's realism remains limited.”

Q: **What was frozen before the final test?**
A: “The chosen configuration, original features/generator, fitting/calibration
windows, final seed/count, primary AP metric, 2% budget, tie policy, promotion gate
and paired bootstrap settings. The source/plan checkpoint was pushed before the
reserved replication was generated.”

## Change and test report

Fresh local validation on November 8 used the pinned dependencies and original
macOS/Node/Python environment recorded in the frozen evidence.

| Check | Fresh result | Scope |
|---|---|---|
| Full backend suite | 94 passed; one Starlette/httpx deprecation warning | 72 existing checks plus 19 comparison-integrity and 3 local-scoring regressions |
| Frontend units | 17 passed | Original policies plus four comparison/gate/cost-regression presentation checks |
| ESLint, TypeScript, static build | Passed | Supported Next.js static export |
| Dashboard Chrome checks | 163 passed across 320/390/768/1440 px | Fresh counts/budgets/report, visible cost regression, original controls and study isolation, layout and runtime errors |
| Full local model evidence verification | Passed | 150,000 regenerated source rows, saved metrics, all 500 paired intervals and both model-file hashes; no model deserialization |
| Committed evidence-only verification | Passed | Same numerical/source-data checks with explicitly unprovided model bundles |
| Actual local scoring CLI | 1,000 feature rows scored, exactly 20 review flags | Own trusted challenger bundle; labels omitted; no live service or case write |
| Independent audit | Passed | Separately recomputed AP, four budgets and Decimal cost totals; checked feature/source/plan bindings and freeze-before-generation timeline |

The first new test run exposed retained-label object dtype inherited from an
intentionally corrupted excluded tail. Strict retained-schema validation followed
by binary-label normalization fixed it; the reserved evaluation was generated only
after these tests and fixes. Independent review also caught bootstrap score-tie
ordering and missing verification/budget bounds before the freeze. Those fixes
are included in the 19 new comparison checks. No final outcome was used to change
model parameters or the frozen evaluation method.

Publications and hosted source identities are recorded separately in the release
manifest and final publication report. Local passing checks are not a claim that
all native/API features are hosted or that production banking behavior was tested.
