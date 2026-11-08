# Frozen model comparison: independent synthetic replication

The candidate and protocol were frozen in `configs/model-improvement-frozen-v1.json`
and published in Git checkpoint `27d2732` before generation of the reserved
150,000-row replication. See `report.json` for every predeclared budget, both
models' outcomes and the original cost-policy regression. This is an actual
refitted model comparison, not a threshold-only gain or real-payment benchmark.

Verify the saved metrics, paired intervals and regenerated source rows without
loading model bundles:

```sh
PYTHONPATH=. python scripts/compare_models.py verify evidence/model-improvement-v1 --evidence-only
```

The evidence-only mode explicitly does not verify the model bundles, which are
kept in ignored local run directories. The original full local verification
additionally hashed both saved bundles without loading them. Checksums identify
bytes but are unsigned and do not prove who authored them or attest model fitting.
The saved predictions permit numerical audit of the reported metrics; they do not
independently establish that a model was trained as described.

To reproduce fitting and evaluation from the frozen source, use a fresh output
root. This is a reproduction of an already disclosed test, not a new untouched
validation or an opportunity to tune against these outcomes:

```sh
PYTHONPATH=. python scripts/compare_models.py evaluate \
  --plan configs/model-improvement-frozen-v1.json --output artifacts/reproduction
PYTHONPATH=. python scripts/compare_models.py verify artifacts/reproduction/d8cc5fece5e3319e
```

Source and dependency versions are recorded in the plan/report. Different model
runtime/platform versions can change predictions; no cross-environment bitwise
model claim is made. Do not load third-party pickle/joblib. Do not describe the
new ranking result as an improvement of the original cost policy: the challenger
cost-selected policy had worse modeled cost and recall in this replication.
