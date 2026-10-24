# Interview engineering stories

## 1. Making an investigation decision and its evidence indivisible

**Problem/context.** The repository had SQLAlchemy transaction/score tables and a
static strategy dashboard, but no saved analyst workflow. Adding a status form
with a read-then-write handler would allow two analysts to overwrite one another,
and separately saving history could create an unexplained state change.

**Alternatives.** Last-write-wins is simple but silently loses decisions. A
process-local mutex cannot protect multiple workers. Database row locks are less
portable with SQLite. An event-sourced rewrite would add unnecessary complexity.

**Decision/implementation.** Keep an immutable scored snapshot and a current case
row, plus a per-case append-only journal. Require `expected_version` on every note
or transition; the SQL `UPDATE ... WHERE id AND version` is the concurrency
arbiter. Only after that update succeeds, append the next event and commit both
in one transaction. The event includes trusted actor identity, state, version,
time and snapshot checksum; its hash includes the prior hash. SQLite triggers
reject ordinary event edits/deletes. Explicit transitions require review before
resolution; administrators alone may reopen terminal resolutions.

**Validation/results.** Two simultaneous SQLite sessions contend for version 1:
one advances to version 2, the other receives 409, and exactly two events remain
(creation and successful action). Injecting journal insertion failure leaves
status/version unchanged. Trigger, snapshot tamper and chain corruption tests
fail closed. Two real Chrome pages show stale-write rejection and preserve the
unsaved note through reload. Role/export tests prevent viewer writes and strip
notes/actors from portable reports.

**Limits/lesson.** This protects application integrity, not a malicious database
owner: the unsigned journal can be rewritten by someone who disables triggers.
Redacted exports cannot recreate original event hashes. The useful interview
point is choosing a database invariant and testing real competing writers,
rather than describing a UI as concurrency-safe because it disables a button.

## 2. Auditing model claims without destroying the reproducible baseline

**Problem/context.** The previous unpublished study already isolated training,
calibration, selection and final test. Its generator used an artificial stationary
risk process, and its quality validator allowed partially missing categorical
features. Model metrics lacked a constant-probability comparator and a complete
dataset manifest. Replacing the generator would invalidate existing evidence and
risk obscuring whether changes improved engineering or just changed the task.

**Alternatives.** Regenerate a more elaborate entity simulator immediately;
introduce many models; select the best test threshold; or preserve data and first
make quality/provenance/comparison explicit. The first three options would expand
scope or compromise evaluation interpretation.

**Decision/implementation.** Preserve the generator and data bytes. Add strict
required-value/category/range/integer/timestamp/duplicate checks and a descriptive
versioned manifest with feature definitions, distributions, seed and checksums.
Add one constant model fitted from training-label prevalence and apply the same
selection-only cost policy. Verify compatible feature schema and manifest hashes
without loading model pickle. The demo imports scored test rows only after
regenerating the matching full dataset checksum; human judgments never become
training labels.

**Validation/results.** The full 75,000-row study reproduced existing model
outputs; repeated full runs yielded identical snapshot and prediction CSV bytes.
XGBoost average precision is 0.24078 versus the constant baseline's 0.01138, but
recall is only 0.13281 at the cost-selected policy. Logistic regression has the
better Brier score (0.00998 versus 0.01027). Fresh trusted bundle reload exactly
matches prediction doubles; schema/corruption, zero-positive, missing/category,
duplicate and test-label mutation regressions validate the relevant boundaries.

**Limits/lesson.** These models can learn hand-written synthetic rules; no result
establishes bank-fraud accuracy. Sampled account histories are not linked entity
histories. One seeded split lacks confidence intervals and external validation.
A baseline and honest model card made the experiment more defensible without
manufacturing a new headline accuracy number.

### Review follow-up: consistency is part of evidence integrity

A cached case row and a newly committed journal could each be valid but describe
different instants. Hash verification then falsely classified normal concurrent
work as corruption. A single joined read with ORM refresh makes row and journal
coherent before validation. A regression reproduces a stale reader, a second
session's commit and a subsequent reader action. A separate check binds duplicate
metadata to its hashed snapshot/genesis so accidental row damage cannot remain
marked verified. These changes improve corruption detection without weakening
optimistic write conflicts or granting a local database owner cryptographic trust.
