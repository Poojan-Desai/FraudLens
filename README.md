# FraudLens

A fraud investigation and model-evaluation portfolio project using **75,000
synthetic transactions**. Python/FastAPI and scikit-learn/XGBoost provide a
reproducible study and local case API; React/Next.js provides an analytical
dashboard and an analyst review workflow.

[Static dashboard](https://fraudlens-poojan-desai.netlify.app) ·
[Complete local guide](docs/LOCAL_GUIDE.md) · [Model card](docs/MODEL_CARD.md) ·
[Threat model](docs/THREAT_MODEL.md)

The hosted dashboard is a static snapshot. Investigation actions require the local
API and configured credentials; this repository does not provide a live inference
or production banking service.

## What it demonstrates

- Four disjoint chronological windows: 45,000 training, 11,250 calibration,
  7,500 policy selection and 11,250 locked test transactions. Preprocessing and
  model fitting use training data only; test data never selects the policy.
- Separate probability calibration and cost-policy selection, a train-prevalence
  comparator, dataset manifests and checksum verification of saved results.
- Threshold exploration based on measured test aggregates, with illustrative
  operating costs and explicitly labeled fictional transaction examples.
- Analyst case review with viewer/analyst/admin permissions, optimistic version
  checks, atomic decisions and an append-only hash-linked SQLite action journal.
- Verified import of saved flagged predictions without loading executable model
  bundles. Human decisions remain separate from model-training ground truth.

## Run locally

Requirements: Node.js 22.13+, Python 3.13 and Google Chrome for browser checks.

```sh
git clone https://github.com/Poojan-Desai/FraudLens.git
cd FraudLens
npm ci
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
PYTHONPATH=. python scripts/run_experiment.py --output artifacts/runs --snapshot public/evaluation.json
PYTHONPATH=. python scripts/verify_experiment.py artifacts/runs/<study-id>
npm run build
python3 -m http.server 4176 --bind 127.0.0.1 --directory out
```

Open [http://127.0.0.1:4176](http://127.0.0.1:4176). Replace `<study-id>` with the
identifier printed by the experiment. Run directories are immutable; use a fresh
output directory for another run. The configuration is in `configs/synthetic-v2.json`.

For investigations, open a second terminal in the checkout:

```sh
source .venv/bin/activate
PYTHONPATH=. python scripts/prepare_investigation_demo.py artifacts/runs/<study-id>
source work/investigation-demo/environment.sh
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

The setup creates ignored local credentials and up to 12 synthetic cases after
verifying the regenerated dataset. Follow the [case-review walkthrough](docs/LOCAL_GUIDE.md#complete-investigation-demonstration)
to connect at `/investigations/`, review a case and download a redacted report.
Do not publish the generated credentials or runtime database.

## Verified evidence

Fresh October 28, 2026 local checks passed **60 backend tests, seven frontend unit
tests, 83 dashboard browser checks and 27 investigation browser checks**, plus
lint, TypeScript and the production static build. A fresh full 75,000-row study
reproduced the committed snapshot byte for byte; its saved artifacts verified
11,250 held-out predictions and two model files without deserializing model bundles.

The study uses seed 42 and 128 positive labels in the test window. At the
selection-chosen threshold of 0.18, calibrated XGBoost has test precision 62.96%,
recall 13.28% and average precision 0.24078. These describe this synthetic process,
not real-payment performance. Assumed costs and comparisons are documented in the
[model card](docs/MODEL_CARD.md); the selected policy misses most labeled fraud.

```sh
PYTHONPATH=. python -m pytest -q backend/tests
npm run test:unit
npm run lint
npx tsc --noEmit
npm run build
# Static server running:
npm run test:browser
# Local API running and demo environment sourced:
npm run test:investigations
```

[CI](https://github.com/Poojan-Desai/FraudLens/actions) defines backend tests,
experiment reproduction/artifact verification and frontend checks/build.
See [October verification](docs/VERIFICATION-2026-10-28.md) for current results and
[prior verification](docs/VERIFICATION.md) for the original implementation audit.

## Limits and security

The generator uses hand-written stationary rules without persistent accounts;
its metrics cannot establish real-world fraud detection or business savings.
Three-way approve/review/block policy, live inference, real-payment benchmarking,
local model explanations and production identity remain incomplete.

Local case access fails closed without configured credentials. Static bearer
tokens lack expiration/MFA; bind the API to loopback. Hashes detect local tampering
but are unsigned and cannot protect against a database owner rewriting all history.
Exports remove notes/actors while retaining synthetic transaction evidence.
Only trusted locally generated joblib bundles should ever be loaded.

The repaired lockfile passes clean `npm ci`. The current npm audit reports
**15 development/build findings (nine high, six moderate), zero critical and zero
production-only findings**. These remain unresolved dependency debt, detailed in
[verification](docs/VERIFICATION-2026-10-28.md). No general security certification
or production deployment is claimed.
