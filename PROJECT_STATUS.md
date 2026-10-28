# FraudLens implementation status

Updated October 28, 2026.

Implemented and locally verified: four disjoint chronological study windows,
train-only preprocessing/fitting, separate calibration and cost-policy selection,
locked test evaluation, a prevalence comparator, checksummed dataset/results,
actual threshold aggregates, and synthetic-data disclosures.

The local investigation API supports configured viewer/analyst/admin roles,
immutable scored snapshots, optimistic version checks, atomic case actions and
an append-only hash-linked journal. Human resolutions are not training labels.
The static investigation UI connects explicitly to the local API.

Fresh verification: 60 backend tests, seven frontend tests, 83 analytics browser
checks, 27 investigation browser checks, lint, TypeScript and static production
build passed. The full 75,000-row study reproduced the committed public snapshot.
A repaired package lock now permits clean `npm ci`. See
[verification](docs/VERIFICATION-2026-10-28.md) for exact scope and dependency debt.

Remaining: real-payment benchmarking, live inference/model serving, a three-way
decision policy, local model explanations, production identity, monitoring and
broader load testing. The hosted Netlify dashboard is a static snapshot; local
verification does not establish production deployment or banking performance.
