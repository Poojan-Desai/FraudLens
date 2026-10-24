# Local investigation threat model

## Scope and trust boundaries

The browser static export talks to a loopback FastAPI process. The process trusts
its local environment credentials and local SQLite file. Study import verifies
saved evidence, regenerates the complete synthetic dataset and joins model
predictions to features; it never loads a model pickle. Only synthetic data is
supported for the demonstration. No real payment authorization/cloud service is
connected. Existing simulation/health endpoints remain public and contain no case
records; case endpoints independently require credentials.

| Threat | Implemented control and evidence | Boundary / remaining risk |
|---|---|---|
| Unauthenticated case reading/writing | All case routes require configured bearer identity; absent/invalid config fails 503; invalid token 401. Tested. | Static high-entropy tokens have no expiry, SSO, MFA or user management. Bind only to loopback. |
| Role escalation or forged actor | Server-derived actor/role; viewer reads only, analyst notes/transitions/export, admin imports/reopens. Extra actor field rejected. Tested. | Anyone with environment/admin access controls identity mapping. No per-tenant isolation. |
| Lost concurrent decisions | Every write conditionally updates ID and expected version; audit append shares commit. Two real threads permit exactly one v1 write; two browser pages demonstrate conflict recovery. | SQLite is a local store; high-load/multi-process service operation is unbenchmarked. |
| Audit edit/delete or snapshot damage | SQLite event triggers prohibit UPDATE/DELETE; SHA-256 links include actor/action/state/version/snapshot hash. Reads, actions and exports fail closed on detected tamper. Tested. | Unsigned chain: DB owner can disable triggers/recompute hashes. No external anchoring. |
| Partial state/event write | Injected event insertion failure rolls back state/version. Tested. | OS/hardware durability/power-loss testing has not been performed. |
| SQL injection / wildcard search | SQLAlchemy parameter binding; `.contains(..., autoescape=True)` treats wildcard input literally. Tested with SQL and `%` strings. | No raw caller-provided SQL supported. |
| XSS in notes | React text rendering; no HTML interpretation, JSON attachment type and `nosniff`; actual browser `<img onerror>` note remains text. | CSP/security hardening of the static host remains hosting-specific and unverified. |
| CSRF / browser credential leakage | Authorization header required, no cookies, explicit local CORS allowlist, no wildcard credentials. Tokens stay only in component memory; reload/disconnect clears them. Browser test inspects local/session storage. | A compromised allowed origin or malicious browser extension could steal a memory-resident token. |
| Sensitive report/log exposure | Export strips investigator note text and actors; responses `no-store`, `no-referrer`; no token logging. Tested. | Export retains synthetic transaction IDs/features; arbitrary simulated import text is not a complete PII deidentifier. Standard access logs retain route IDs, not request body/headers. |
| Model artifact code execution | Verification/demo import never deserialize joblib. Fresh locally generated trusted artifacts are loaded only in regression test for prediction parity. Corrupt hash/schema tests fail closed. | Unsigned hashes do not authenticate an artifact publisher. Do not load third-party pickle. |
| Invalid/abusive inputs | Bounded notes, features, search, paging and transaction arrays; finite probability/amount validation, timezone requirement, duplicate rejection. Tested. | No application rate limiter or ingress body-size limit; deployment requires both. |
| Compromised dependencies | Exact Next/ESLint update to 16.4.3 clears current critical npm advisories; lockfile and audit evidence retained. | 13 npm audit findings remain (9 high/4 moderate), all in development/build tooling; production-only audit reports zero findings. Python supply-chain audit and full SBOM remain incomplete. |

These are implemented design controls, not a claim of compliance with any
financial, privacy or cybersecurity certification. Remote CI/deployment and a
public-facing security review have not been run.
