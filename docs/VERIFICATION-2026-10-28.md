# Verification — October 28, 2026

Fresh verification from the recovered October source, on macOS / Apple Silicon,
Node 22.18.0, Python 3.13.1 and headless Google Chrome. Results below describe this
local checkout; GitHub Actions reports remote execution separately.

| Check | Result |
|---|---|
| Clean JavaScript install | Initial `npm ci` rejected an incomplete lockfile; regenerated the lockfile with `npm install --package-lock-only`, then clean `npm ci` passed. No direct dependency was changed. |
| Backend | `PYTHONPATH=. .venv/bin/python -m pytest -q backend/tests`: 60 passed; one upstream Starlette/AnyIO deprecation warning. |
| Frontend | `npm run test:unit`: seven passed. |
| Source checks | ESLint and `npx tsc --noEmit` passed. |
| Production build | `npm run build` passed; static `/` and `/investigations/` exported. |
| Full experiment | Fresh 75,000-row study `7287a6f8b6ef04ba` reproduced `public/evaluation.json` byte for byte. |
| Artifact verification | Two model files and 11,250 held-out prediction rows verified without deserializing model bundles. Prediction SHA256: `4092f56b2c37af9055633bc1d4c8e608c2b4bc4d39b67fc8f54524bdbc91b9a0`. |
| Analytics browser | 83 checks passed at 320 / 390 / 768 / 1440 px. |
| Investigation browser | 27 checks passed at 390 / 1440 px against a fresh local case store and actual API writes. |
| npm dependency audit | 15 findings: nine high and six moderate in development/build tooling; no critical findings; production-only audit zero. Debt remains. |
| Secret review | Gitleaks 8.30.1 scanned all six recovered commits with zero findings. Reviewed tracked assets: synthetic snapshot, synthetic investigation screenshot, source/configuration and fonts; no generated credentials, runtime database, model bundles or raw transaction data are committed. |

The repaired lockfile resolves the missing Webpack peer subtree that would have
prevented clean CI installation. The case browser verified credential rejection,
server-side roles, persisted decisions, stale-version rejection, note retention,
export redaction and responsive layout. Study and application tests cover separate
data windows, cost/evidence consistency, dataset validation, real competing SQLite
writers, atomic rollback and tamper rejection.

For reproduction use the README commands. This run used static port 4197 and
`FRAUDLENS_CASE_ORIGINS=http://127.0.0.1:4197` because previews can coexist on this
machine. The API remained on loopback port 8000. Model/runtime artifacts and
mode-0600 local demo credentials remain ignored.

No real-payment benchmark, production deployment, banking loss reduction,
causal explanation or security certification is claimed. The synthetic process
and illustrative cost assumptions limit interpretation; see `MODEL_CARD.md` and
`THREAT_MODEL.md`.
