# FraudLens audit — 2026-10-24

Inspected the local unpublished baseline before implementation: API/database/schema,
synthetic generation/validation, four-window experiment, evidence verifier, dashboard,
backend tests, browser checks, lockfiles and CI. Working tree was clean. Current
GitHub source plus earlier unpublished upgrades were preserved in the baseline.

| Category | Observations before editing |
|---|---|
| Existing strengths | Explicit train/calibration/selection/test windows, fixed hyperparameters, test-label mutation regression, train-only preprocessing, deterministic snapshots, checksum verifier that never deserializes pickle, measured dashboard aggregates and careful synthetic disclosures. |
| Critical defects | Synthetic schema accepts partially missing categorical/boolean fields and invalid ranges/categories; required derived model feature is checked separately. SQLite case-related tables are unused; no analyst workflow exists. |
| Missing capabilities | Persisted investigation state, concurrency conflict handling, actor authentication/authorization, notes/history/export. Dataset identity has checksum but lacks a standalone descriptive manifest and quality report. No prevalence-only comparator. |
| Engineering quality | Useful 39-test previously reported suite (to recheck), local browser script, static build and least-privilege CI. Main dashboard mixes authored examples with separately labeled actual study. |
| Security | Unauthenticated simulation endpoints accept unbounded lists. No existing sensitive case API; any new one must fail closed without configured credentials. joblib bundles are executable and must remain trusted-local only. Hashes are integrity checks, not publisher authenticity. Dependency audit debt is documented, not remediated wholesale. |
| Data/ML validity | Existing split/calibration policy isolation is strong. Synthetic labels derive from a hand-written stationary risk process; there are no persistent account identities and velocity/history features are sampled, not computed from linked events. No actual bank validity claim is supportable. |
| Product quality | Responsive static analytics UI and honest authored examples, but no complete score-to-investigation workflow. |
| Employer relevance | A coherent workflow can demonstrate transactional correctness, authorization, explicit state machines, auditability and trustworthy model evidence alongside existing ML methodology. |

## Ranked changes

1. Persisted case investigation vertical slice — high value; medium complexity/risk;
   validate real database/API concurrency, transitions, roles, event integrity and UI.
2. Dataset quality validation and descriptive versioned manifest — high value;
   low complexity; preserve generator and existing dataset, add negative tests.
3. Train-only prevalence baseline and refreshed reproducible model evidence — high
   value; low/medium complexity; compare AP/Brier/cost with current models.
4. Bounded API requests, local-only CORS, safe errors/exports, threat model — high
   value; low complexity; regression tests and configuration checks.
5. Full monitoring, three-way policy and trusted model serving — valuable but larger
   architectural scope; defer rather than misrepresent static scores as live inference.

## Baseline execution

See `docs/VERIFICATION.md` for commands and actual results. Dependencies were absent
in this fresh workspace and are installed in ignored local directories. No remote
writes, deployment or publication are authorized.
