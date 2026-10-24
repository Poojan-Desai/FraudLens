# FraudLens local verification — October 24, 2026

Environment: Apple M3 Pro, macOS, Python 3.13.1; Node 22.18.0; Chrome headless;
local synthetic data only. No remote push, CI run or deployment was performed.

## Baseline

The clean local baseline (Git `HEAD`, including prior unpublished changes) was
exported to ignored `work/baseline/` and tested independently after installing
requirements. Its 32 backend tests passed (24.39s including cold imports); the
existing seven frontend unit tests passed. No baseline tests were removed.

## Final checks

| Command | Verified outcome |
|---|---|
| `PYTHONPATH=. .venv/bin/python -m pytest -q backend/tests` | 60 passed (32 retained + 28 new), 3.93s; one upstream Starlette/AnyIO deprecation warning. |
| `npm run test:unit` | Seven passed. |
| `npm run lint` | Passed. |
| `npx tsc --noEmit` | Passed. |
| `npm run build` | Static production export passed; `/` and `/investigations/`. Next 16.4.3. |
| `PYTHONPATH=. python scripts/run_experiment.py --output artifacts/upgrade --snapshot public/evaluation.json` | Completed full 75,000-row four-window run `7287a6f8b6ef04ba`. |
| `PYTHONPATH=. python scripts/verify_experiment.py artifacts/upgrade/7287a6f8b6ef04ba` | Verified two model files, 11,250 held-out predictions, metrics/curves, feature schema and dataset manifest without deserializing bundles. |
| Same full experiment with `--output artifacts/upgrade-repeat --snapshot work/evaluation-repeat.json` | Completed; public snapshots and prediction CSVs byte-identical. |
| `PYTHONPATH=. python scripts/prepare_investigation_demo.py artifacts/upgrade/7287a6f8b6ef04ba` | Created 12 cases after complete dataset-regeneration checksum verification; no labels copied. Repeat created zero duplicate cases and preserved existing decisions. |
| `FRAUDLENS_BROWSER_URL=http://127.0.0.1:4187 npm run test:browser` | 83 checks passed at 320/390/768/1440px. |
| Demo environment sourced; same URL `npm run test:investigations` | 27 checks passed at 390/1440px, actual local API writes and two-page stale-write recovery. |
| `npm audit --json` | 13 remaining findings: nine high, four moderate, zero low/critical; all are development/build dependencies. Production-only audit reports zero findings. Audit exits nonzero because debt remains. |

Local port 4176 was already occupied, so browser evidence used isolated port 4187
and `FRAUDLENS_CASE_ORIGINS=http://127.0.0.1:4187`. The documented default ports
remain 4176 for static UI and 8000 for loopback API.

The first investigation browser run exposed an assertion race: Next's route
announcer also uses `role=alert`. It was corrected to wait for the visible case
error panel. The API correctly returned 409 throughout. A real UX gap discovered
in this process was fixed: reloading the same case now retains an unsaved note.

## New regression coverage

Fourteen investigation tests cover fail-closed credentials/config, role-derived
actors, export redaction, review/resolution/admin reopen, unchanged scored
snapshots, stale versions, forbidden/invalid actions, duplicates/labels/unflagged
input, literal search/pagination, actual competing SQLite writers, injected
journal-write rollback, SQLite append-only triggers, snapshot/event tamper and
CORS. Fourteen dataset tests cover missing/invalid values, impossible date/range,
duplicates/empty data, zero positives, manifest quality/input preservation,
prevalence comparator, trusted-artifact reload parity and schema/manifest damage.

The browser adds invalid-token behavior, actual saved-score/provenance rendering,
plain-text XSS payload, stale writer conflicts, note retention, resolution and
history, terminal-state role limits, real report download, no persistent token
storage, reload credential clearing and responsive overflow checks.

## Measured results and limits

See `MODEL_CARD.md` and the report JSON. XGBoost test AP 0.24078369 / Brier
0.01026769 / recall 0.1328125 / illustrative cost $6,108.56; logistic test AP
0.21134504 / Brier 0.00997565 / recall 0.09375 / cost $6,489.69; baseline AP
0.01137778 / Brier 0.01124838 / recall 0 / cost $6,728.51. Costs are assumptions;
there is no real-payment, live inference, financial-return or deployment claim.

Full model artifacts/runtime DB/generated credentials are deliberately excluded
from deliverables. Model reports, manifests, test logs, screenshots, source and
patches are safe local review artifacts. Security limitations and remaining
requirements are documented in the README and threat model.

## Independent review fixes and final verification

Two reproduced integrity defects were corrected before delivery. Case detail/list
serialization and actions now load the case row and ordered journal in one joined
SQL statement, refreshing cached ORM identities; normal competing commits no
longer produce a false corruption result. Verification also binds the case's
transaction ID to the hashed snapshot and its creation time to the genesis event.
A cached-reader/committed-writer regression and two independent metadata tamper
regressions pass. Each tamper is rejected on detail, list, action and export.

The final source was verified after these fixes and compatible dependency updates:
60 backend tests, seven frontend tests, lint, type checking, production build,
27 investigation browser checks and 83 analytics browser checks. The API was
restarted from this checkout before browser verification.

Vite was updated to 8.3.5 and compatible transitive fixes applied without forcing
a major migration of the inherited optional Cloudflare/vinext build tooling.
The remaining 13 findings are documented in the raw audit and
`Remaining_Dependency_Findings.json`. Zero production audit findings is a registry
audit result, not a guarantee that software contains no vulnerabilities.
