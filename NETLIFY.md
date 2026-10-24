# Netlify deployment

Live URL: https://fraudlens-poojan-desai.netlify.app

Migrated on October 5, 2026. The interactive browser demo is preserved. Python backends, data pipelines, and cloud integrations remain reproducible local/source components; the Netlify deployment does not turn those components into live services.

## Build and publish

Use Node.js 22 or newer and an authenticated Netlify CLI.

```sh
npm ci
npm run build
netlify link --id b6855c51-9f33-4cb4-b68f-a816db9ae76b
netlify deploy --prod --dir out --no-build
```

Only `out` is uploaded. Source files and local data are not served. The original ChatGPT Sites deployment is retained. Netlify deployments are currently manual; no GitHub build hook was added.

FraudLens uses Next.js static export. Seven strategy tests and the production build passed. Legacy Cloudflare/Sites helpers remain in source but are excluded from the Netlify application build. The current local branch adds precomputed held-out model-score threshold analysis; transaction explanations and attack examples remain authored and labeled. A deployment of this branch requires separate authorization; the live URL still serves its previously deployed revision.
