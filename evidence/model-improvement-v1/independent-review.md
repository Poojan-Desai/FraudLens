# Independent final FraudLens result review

Reviewed November 8, 2026. Frozen plan: `d8cc5fece5e3319e`. Source checkpoint: `27d273278d98fd92252f2eca130d30df780c1c5b`. This is a read-only audit of the saved final predictions, plan, report, source hashes, development evidence and publication timeline. No model was loaded, fitted, modified, or selected; no dataset was generated or regenerated. Repository files were not edited.

## Finding

The saved evidence supports a **same-generator synthetic ranking improvement**. Independently recomputed average precision and exact-capacity metrics match the published/full report exactly. At the same 3,000-alert budget on the same 150,000 rows, the challenger identifies 650 of 1,545 labeled fraud cases, compared with 604 for the incumbent. That is 46 additional detections, with 46 fewer false positives because the alert count is fixed.

It does **not** support an improved selection-chosen cost policy. Under the preselected cost thresholds, the challenger detects only 163 versus 298 fraud labels and has a higher illustrative total cost. The incumbent should remain the cost-policy default. Label the successful gate as a ranking/fixed-capacity gate; a generic “model promoted” statement would obscure this material regression.

## Independent computations

The audit decompresses `test-predictions.csv.gz`, parses probabilities with pandas round-trip precision, checks canonical unique row IDs and valid targets/scores, uses sklearn's `average_precision_score`, and implements its own ranking with `numpy.lexsort((transaction_id, -score))`. No production model-comparison helper is used to calculate AP or choose the top-k rows. All four predeclared budgets were recomputed and matched. At the primary cutoff, each model has a one-row boundary group, so there is no ambiguity about which boundary tie was selected.

| Metric on the same independent synthetic replication | Incumbent | Challenger | Difference |
|---|---:|---:|---:|
| Average precision | 0.2487259915 | 0.2726320394 | +0.0239060479; +9.6114% relative |
| Alerts at 2% capacity | 3,000 | 3,000 | 0 |
| True positives | 604 | 650 | +46 |
| False positives | 2,396 | 2,350 | -46 |
| False negatives | 941 | 895 | -46 |
| Recall at 2% capacity | 39.0939% | 42.0712% | +2.9773 percentage points |
| Precision at 2% capacity | 20.1333% | 21.6667% | +1.5333 percentage points |
| Brier score, descriptive | 0.0092679956 | 0.0087894857 | Lower point estimate; no independent calibration-improvement CI claimed |
| ROC-AUC, descriptive | 0.8567680747 | 0.8694353742 | Higher point estimate; not the primary gate |

There are 150,000 rows and 1,545 fraud labels (1.03% prevalence). The challenger still misses 895 fraud labels at this capacity, and 2,350 of its 3,000 alerts are false positives. Same-capacity precision and recall share the same true-positive numerator; they should not be described as independent confirmations.

The reported paired 500-replicate percentile intervals are AP difference `[0.0149469432, 0.0331804608]` and primary-budget recall difference `[0.0160820224, 0.0395327890]`. Their implementation and tie treatment were reviewed before freeze; the primary agent is separately recomputing the full interval set. This independent audit recomputes point metrics rather than duplicating the 500-replicate calculation. The recorded AP lower bound is positive and the independently checked recall point difference is nonnegative, satisfying the predeclared gate if the primary agent's full interval verification passes.

The AP gain is **2.3906 AP percentage points**, or **9.6114% relative to incumbent AP**. It is not a 9.6-point gain in accuracy or a real-world fraud-detection rate. The confidence interval conditions on these fitted models and this sampling process; it does not include training/development-selection uncertainty.

## Material cost-policy regression

An independent integer-cent/Decimal calculation reproduces both total costs. The cost rule uses illustrative assumptions already present in the project: false positive cost $18, manual review $1.20, recovery fraction 0.35, capacity 1,400, and overflow $1.65. Final thresholds remain the ones chosen on the separate original selection window; no final-data threshold tuning was performed by this audit.

| Selection-chosen threshold policy on the fresh rows | Incumbent | Challenger |
|---|---:|---:|
| Frozen selection-chosen threshold | 0.18 | 0.66 |
| Alerts | 529 | 236 |
| True positives | 298 | 163 |
| Precision | 56.3327% | 69.0678% |
| Recall | 19.2880% | 10.5502% |
| Illustrative total cost | $81,248.93 | $84,405.00 |

The challenger's total is **$3,156.07 higher, or 3.8844% worse**, and detects 135 fewer fraud labels at these thresholds. Its higher precision comes with substantially fewer alerts and lower recall. These outcomes do not contradict the ranking improvement: ranking the whole population better does not guarantee that a threshold selected from a small development window transfers into a better operating policy.

Do not present the cost difference as realized financial loss or savings. Keep the incumbent cost policy, show the challenger only with the qualified ranking/fixed-budget evidence, and retain this regression in the technical guide, interview answer, and change report. Improving the cost policy would be subsequent development work requiring its own policy-selection protocol and a future untouched evaluation; optimizing it on this now-visible final set would contaminate the claim.

## Frozen provenance, features and candidate selection

The audit verified these byte-level bindings:

- Public `model-comparison.json` and the full run `report.json` parse identically.
- Run and committed `configs/model-improvement-frozen-v1.json` are byte-identical; SHA-256 is `46b27ec0230290f7b18318904e86957a2ac4018fee94a5c82e10f4420400b012`.
- Recomputed canonical plan identity is `d8cc5fece5e3319e`.
- All seven frozen source hashes match the working tree and the source checkpoint's committed bytes. The unchanged generator hash remains `69b8816f72592bfe4799a6c196cdfa6c4ddb0fcbfd792a0a615363730a92a068`.
- The report uses the unchanged original 12-feature allowlist. No generator-risk/oracle feature was added. The reviewed fit code retains the original full 75,000-row generation count before slicing off the exposed tail and fits training/calibration/selection at 45,000/11,250/7,500 rows.
- The candidate is `unit_d2_300_regularized`: unit class weight, depth 2, 300 trees, minimum child weight 5, L2 regularization 5. Incumbent weighting/depth and the shared family settings match the reviewed implementation.
- The included development report and evaluation protocol hashes match the freeze. All ten file entries in the development artifact manifest match their included hashes.
- Independently grouping the saved 36 development fits confirms 12 configurations, each evaluated on seeds 11/29/73. The frozen candidate is the unique highest mean-selection-AP configuration, 0.3473163793 versus runner-up 0.3313466942. Thus secondary tie-rule wording does not affect the actual winner.
- Prediction gzip SHA-256 is `c09d12b497d766e3a949a9ad3248f2fe79c7a2b29484b72395bc126cb38d0873`; both saved model byte hashes match the report. No executable model bundle was loaded.
- Audit Python/package versions match the frozen environment: Python 3.13.1, numpy 2.3.2, pandas 2.2.3, scipy 1.18.1, sklearn 1.7.1, XGBoost 3.0.3, joblib 1.5.1.

The full raw-feature dataset hash and training-window data hashes are not independently recomputed in this audit, because it intentionally does not regenerate data. The primary agent's full verifier handles that reproduction. Source hashes, plan settings and the saved prediction inputs were checked here. Hash consistency does not establish authenticity or independently prove that the saved probabilities were emitted by the hashed models.

## Timeline and published checkpoint

| Event | UTC | America/New_York |
|---|---|---|
| Plan frozen | November 8, 22:42:54.918002 | November 8, 17:42:54.918002 EST |
| Checkpoint commit timestamp | November 8, 22:42:55 | November 8, 17:42:55 EST |
| GitHub push-run server creation | November 8, 22:42:58 | November 8, 17:42:58 EST |
| Recorded evaluation start | November 8, 22:43:17.645874 | November 8, 17:43:17.645874 EST |
| Recorded evaluation completion | November 8, 22:43:58.477141 | November 8, 17:43:58.477141 EST |

The frozen plan and implementation are in [checkpoint 27d2732](https://github.com/Poojan-Desai/FraudLens/commit/27d273278d98fd92252f2eca130d30df780c1c5b). GitHub's [push workflow run 42531605233](https://github.com/Poojan-Desai/FraudLens/actions/runs/42531605233) was server-created before the locally recorded evaluation start and completed successfully. The start ledger binds the same frozen-plan hash. This corroborates publication of the frozen protocol before the recorded run. Unsigned local timestamps and a published checkpoint cannot prove that no earlier unseen generation or data access ever occurred; do not describe them as cryptographic proof of blinding.

The source generates final data after frozen model fitting in the recorded run. The final seed `20261108` differs from fitting seed 42 and development seeds 11/29/73. Timestamps restart in 2025 under the same stationary mechanism; this is an independent random replication, not a future-time, external-data, bank, or production validation.

## Responsible wording

Resume candidate, after publication/integration:

“Improved XGBoost average precision from 0.249 to 0.273 on 150,000 independent synthetic transactions; detected 46 additional fraud labels at the same 3,000-alert budget, with paired uncertainty and policy limitations documented.”

Interview explanation:

“The original 17-of-128 result used a different test and a much smaller alert budget. To test a real model change, I froze a candidate chosen using three development seeds, then compared it with the incumbent on the same independent synthetic rows at exactly the same capacity. AP increased about 9.6% relative, and the model detected 650 versus 604 fraud labels with 3,000 alerts. I also found a negative result: its separately selected cost threshold generalized worse, so I kept the incumbent cost policy. The ranking result is useful, but I would not call it real-payment accuracy or claim financial savings.”

Compact machine-readable audit evidence is saved in `work/reports/fraudlens-model-final-review.json`.
