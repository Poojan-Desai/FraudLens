# Selection-based policy presets

The dashboard now compares three explicit objectives for the existing calibrated
XGBoost model. No model, dataset, probability, or original selected threshold was
changed. All policies choose a threshold on the 7,500-row **selection** window;
ties choose the higher threshold. The table reports outcomes on the existing
11,250-row **test** window containing 128 labeled synthetic fraud cases.

| Objective | Threshold | Fraud caught | Precision | Alerts | False alerts | Modeled cost |
|---|---:|---:|---:|---:|---:|---:|
| Minimum cost | 0.18 | 17/128 (13.28%) | 62.96% | 27 | 10 | $6,108.56 |
| Maximum F1 | 0.11 | 44/128 (34.38%) | 26.35% | 167 | 123 | $6,514.92 |
| Maximum F2 | 0.06 | 61/128 (47.66%) | 12.55% | 486 | 425 | $11,920.68 |

These use the original defaults: $18 false-positive friction, $1.20 review,
35% recovery, 1,400 reviews over the whole test window and $1.65 overflow.
Costs are assumptions, not measured bank savings. F1/F2 do not enforce capacity
or minimize cost. F2 weights recall four times as much as precision. Changing
assumptions reselects the cost threshold on selection data, while F1/F2 stay
score-based. Every preset displays overflow when it exceeds capacity.

The original cost policy remains the default. Each Apply control updates the
same threshold slider, KPIs and confusion matrix; manual slider changes remain
exploratory test sensitivity analysis. The pure functions in `lib/strategy.ts`
support both stored models, while this comparison UI uses calibrated XGBoost.

## Validation and limits

- The full seeded study was rerun locally on November 7, 2026 and reproduced
  `public/evaluation.json` byte for byte. The artifact verifier checked 11,250
  predictions and both model-file hashes without loading model bundles.
- The existing seven frontend tests passed, then the expanded suite passed 13
  tests. Six new tests verify the frozen counts, both-model selection objectives,
  selection/test separation, capacity caveat, zero scores and invalid inputs.
- Lint, TypeScript and static build passed. Expanded browser checks passed 103
  assertions across 320, 390, 768 and 1440 px, including all Apply controls.
- The unchanged backend suite passed 72 tests with one dependency deprecation
  warning. No new backend functionality or model-quality improvement is claimed.
- These objectives were added after the original test results were available.
  The table is a retrospective comparison of precomputed outcomes, not independent
  confirmation that the new policy improves future performance. Select a business
  objective before a new untouched evaluation to make that claim.
- Earlier conversation examples used different alternative thresholds. The
  implemented F1/F2 definitions above are explicit and independently testable;
  they should not be relabeled as the earlier proposed policies.

Responsible wording: “Added selection-based cost/F1/F2 policy comparisons with
explicit precision, recall, false-alert and workload tradeoffs on a reproduced
75,000-transaction synthetic study.” Do not claim better fraud-model accuracy,
real-payment detection, causal explanations, or realized financial savings.
