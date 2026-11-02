# Release review — November 2, 2026

Reviewed from `5db16ab` in the primary FraudLens checkout. No changes from the
separate history checkout were used. Public data remains synthetic.

## Corrections

- The supported study already used four strict chronological windows: 45,000
  training, 11,250 calibration, 7,500 policy selection and 11,250 final test rows.
  Preprocessing fits training only; calibration uses the next window; policy
  selection cannot see test labels. The explicit 12-feature allowlist excludes
  ground truth, timestamps and metadata. A fresh 75,000-row run reproduced public
  study `7287a6f8b6ef04ba` byte for byte and verified two model files and 11,250
  saved predictions without loading executable bundles.
- The obsolete training CLI used three windows and implicit feature discovery.
  It now warns visibly and delegates to the supported four-window runner. Its
  regression invokes the actual CLI with poisoned legacy input and verifies the
  current allowlist and saved artifacts. Historical direct helper imports remain
  unsupported for current evaluation; the active API does not import them.
- Finite inputs could overflow aggregate amounts or costs and return HTTP 500.
  Strategy calculations now reject unrepresentable aggregates before rounding
  and serialization; the API returns a clear 422. Tests cover missed/prevented
  amounts, cost products, combined totals and large unused cost assumptions.

## Dependency review

Initial npm audit: **31 findings (9 high, 22 moderate)**. Compatible exact updates
of Cloudflare Vite plugin/Wrangler and React/React DOM/RSC, plus an `image-size`
2.0.4 patch override, removed **all nine high findings**. Final audit:
**23 moderate, zero high/critical; production-only zero**. Propagated counts are
not independent exploits. Remaining roots are minimatch/lint, old esbuild under
Drizzle Kit, and Satori under legacy Vinext. Upstream resolution requires major
changes (or npm's inappropriate downgrade suggestions); `--force` was not used.
These tools must run only with trusted local source and no public dev servers.
The Netlify export contains no development server or server-function endpoint.

Python requirements audit found known advisories in the old Starlette and pytest
resolutions. Pinned FastAPI 0.140.13, Starlette 1.10.0 and pytest 9.0.3 pass all
backend checks and `pip check`; the updated requirements audit reports no known
vulnerabilities. ML library versions are unchanged to preserve reproducibility.
An upstream test-client deprecation recommends httpx2; httpx tests still pass.

## Actual checks

- Clean `npm ci`; seven frontend unit tests; ESLint; TypeScript; Next static build.
- 72 backend tests, including the new numeric and legacy-CLI regressions.
- Full fresh study, exact public-snapshot comparison and saved artifact verifier.
- 83 dashboard browser checks at 320/390/768/1440 pixels.
- 27 investigation checks at 390/1440 pixels against an isolated, freshly imported
  synthetic case store and loopback API: rejected credentials, roles, optimistic
  concurrency, notes, persisted decisions and redacted export. Tokens remain
  mode-0600 local files and memory-only browser inputs.
- Redacted Git-history secret scan and `git diff --check`.

The optional legacy `vinext build` was also attempted. It fails before building
because `vite.config.ts` imports the absent template module
`./build/sites-vite-plugin`. That pre-existing unsupported hosting path is not
part of the verified Netlify release. No Sites/Cloudflare deployment was made.

Deploy only the Next `out/` directory to the existing Netlify site. Compare
`/release.json`, `/evaluation.json`, page HTML and actual JS/CSS assets against
the committed build, and exercise the real public pages. The case API and model
artifacts remain local. Never publish credentials, SQLite files, raw datasets or
model bundles. GitHub Actions status is separate release evidence.
