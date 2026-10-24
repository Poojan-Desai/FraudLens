# FraudLens implementation status

Updated October 24, 2026. This is a local development branch; public Netlify behavior has not been changed.

## Implemented and locally verified

- Four-window synthetic experiment with fixed parameters, training-only preprocessing, separate sigmoid calibration and cost-policy selection, and final held-out metrics.
- Immutable, fingerprinted study evidence and model bundles, prediction CSV, actual test threshold aggregates and downloadable browser snapshot.
- Saved-evidence verification recomputes held-out metrics, validates identities/bounds, checks file hashes and avoids model-pickle loading. Regression tests detect corrupted artifacts and altered reported metrics.
- Unified API/study/browser total-cost half-up cent rounding and rejected nonfinite transaction amounts at the API schema boundary.
- Static UI computes threshold costs from actual held-out score aggregates and chooses its policy from selection aggregates only; real PR points and calibration evidence replace illustrative model-evaluation graphics.
- Fictional transaction/attack examples stay labeled as authored. Example comparisons are immediate, without fake processing delays.
- Fractional/null target-label rejection, finite numeric schema checks, unknown-source rejection, and corrected Docker dashboard hostname/port.
- Upgraded Next to 16.3.8 and restored install-time audit notices; critical advisory count is zero, but 31 affected packages (22 high) remain.
- Added repeatable isolated browser verification and a CI definition. Local tests/build status is recorded in the phase report; remote CI and deployment remain unexecuted.

## Local evidence

Current `public/evaluation.json` includes run identity, hashes, versions, parameters, window bounds, all metrics and limitations. Local model/prediction artifacts are intentionally ignored by Git. README contains exact setup/training/repeat commands and current measured results.

On October 24, 32 backend tests, seven frontend tests, lint and the static build
passed locally. Two complete 75,000-row study runs reproduced the same prediction
CSV and browser snapshot bytes. This remains simulated-data evidence, not a
validated real-payment benchmark or profitability claim.

## Incomplete

Real-model transaction investigation/SHAP UI, persisted analyst decisions, model-serving API, monitoring, public benchmark evaluation, confidence intervals, broader accessibility/typography work and a complete Docker execution check. No PyTorch model or production/cloud integration is claimed.
