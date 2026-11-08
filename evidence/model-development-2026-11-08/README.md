# Development model screening — November 8, 2026

This directory preserves the development search that selected
`unit_d2_300_regularized`. It contains no final-holdout results or predictions.
The completed screen compared exactly 12 predeclared XGBoost configurations on
development seeds **11, 29 and 73**, using 75,000 generated rows per seed.
Only the first 63,750 rows were retained: 45,000 training, 11,250 separate sigmoid
calibration, and 7,500 selection. The remaining 11,250 rows were discarded before
inspection, prediction or evaluation. A separate final evaluation must follow a
frozen plan; selection outcomes are not final validation.

## Preserved evidence

- `candidate_screening.py` is the byte-identical executed original. Its SHA-256
  is `44b494147a1fe8154992e3f8d9a385f2c23aa33f56e8ca53f53a2e941de0215e`.
- `protocol-v1.json` records the grid, primary/secondary ranking, feature
  allowlist, seeds, windows, source hashes and versions before any fit.
- `candidate-screen-results.json` retains all 36 fits, resolved parameters,
  per-seed metrics and aggregate rankings. Whitespace alone was compacted for
  inclusion; its parsed JSON is identical to the original 99,095-byte report.
- `frozen-candidate.json` identifies the proposal before final evaluation.
- `candidate-screen-recommendation.md` explains the proposal and tradeoffs.
- `screen-consistency-checks.json` records internal artifact validation.
- `screening.log` preserves the chronological fit results and timing.
- `artifact-manifest.json` records raw checksums, canonical JSON equivalence and
  the one whitespace-only report transformation. A final freeze should hash the
  actual included report bytes, whose raw checksum differs from the original.
- `implementation-review.json` separately verifies the final-comparison
  estimator factory, preprocessing/calibration and freeze CLI against the
  original baseline and proposal on a permitted small development fixture.

The original script lives here unchanged so its recorded hash stays valid.
Do not execute it directly from this directory: its original workspace-relative
layout is reproduced by the wrapper below.

## Reproduce the development screen

From the repository root, with its pinned Python dependencies installed in
`.venv`, run:

```sh
.venv/bin/python evidence/model-development-2026-11-08/reproduce.py \
  --output work/model-development-reproduction/independent-repeat
```

The output directory must be new. The wrapper creates an isolated layout and a
repository symlink below that output, copies the unchanged original script, and
runs it with the current interpreter and single-thread limits. All generated
reports and selection-only arrays remain in the ignored workspace; nothing is
written into this evidence directory or committed automatically. The wrapper
was syntax-checked; this publication did not rerun another model search through
the wrapper.

Reproduction generates only the three listed development seeds. The generator
must receive the original 75,000 count before slicing because its RNG process is
not prefix-stable across different requested sizes. Preprocessing uses only
training rows; calibration uses only its separate window. Features are the
unchanged 12-column allowlist; target, timestamp and metadata are excluded, and
no generator-rule-derived features are added.

Primary ranking is the mean selection average precision across the three seeds;
mean selection recall at exactly 150 of 7,500 reviews is the secondary tie break.
Ties in top-k scores prefer earlier rows. The winner uses weight 1, depth 2,
300 trees, min_child_weight 5 and reg_lambda 5; learning rate 0.05, row/column
subsampling 0.85, binary logistic objective and separate sigmoid calibration
remain unchanged. All fits use `n_jobs=1`, with model random state equal to the
development seed. Versions and all resolved parameters are in the report.

Full report bytes will differ on rerun because timestamps, timing, repository
provenance and environment are recorded. Numerical reproducibility also depends
on the pinned libraries/platform. No cross-environment bitwise guarantee is
claimed. These same-generator development results do not establish real-payment
performance, significance, production capacity, or realized financial savings.
