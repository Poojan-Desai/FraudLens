# FraudLens Project Status

Last updated: 2026-08-09

## Current state

FraudLens is a working, deployed portfolio MVP with a reproducible Python analytics backend. The dashboard is complete enough for the planned 60-second internship demo.

## Implementation stages

| Stage | Status | Evidence |
| --- | --- | --- |
| 1. Repository and structure | Complete | React app, FastAPI backend, data/artifact/script folders |
| 2. Real dataset download and validation | Implemented | OpenML data ID 1597 downloader and strict schema validation; raw CSV intentionally not committed |
| 3. Synthetic generator | Complete | Deterministic 75,000-row generator, seed 42, readable features, clearly labeled source |
| 4. SQLite schema and import foundation | Complete | SQLAlchemy tables for transactions, model scores, explanations, and simulation runs |
| 5. Logistic Regression | Complete | Chronological split, preprocessing pipeline, class weighting, artifact and metrics output |
| 6. XGBoost and comparison | Complete | Calibrated XGBoost, untouched test metrics, joblib artifact bundle |
| 7. Financial-cost engine | Complete | Missed loss, friction, review cost, capacity overflow, cost-optimal threshold |
| 8. FastAPI endpoints | Complete | Health, strategy simulation, and attack-pattern endpoints with Pydantic validation |
| 9. React dashboard | Complete | Simulator, explorer, explanations, model comparison, PR curve, and attack lab |
| 10. Tests and documentation | Complete | Frontend/backend tests, README, architecture diagram, and demo script |

## Verified metrics

- Synthetic rows: 75,000
- Fraud cases: 823 (1.10%)
- Split: 52,500 train / 11,250 validation / 11,250 test
- Calibrated XGBoost: PR-AUC 0.249, precision 51.7%, recall 24.2%, F1 33.0%
- Logistic Regression: PR-AUC 0.231, precision 50.0%, recall 14.8%, F1 22.9%
- Backend tests: 10 passing
- Frontend strategy tests: 5 passing

## Resume/demo readiness

- The dashboard avoids misleading accuracy claims.
- Real and synthetic datasets have clearly separated purposes.
- Metrics shown in the model table match a reproducible local run.
- Explanation copy includes the causation caveat.
- The attack lab reacts to the currently selected strategy threshold.

## Sensible next improvements

These are not blockers for the MVP:

1. Download and run the European benchmark locally, then add its actual comparison metrics to a second model-results tab.
2. Add Platt-scaling calibration plots and Brier score to the model page.
3. Persist simulation runs through the API so analysts can compare saved strategies.
4. Record the 60-second demo and add it to the repository README.
