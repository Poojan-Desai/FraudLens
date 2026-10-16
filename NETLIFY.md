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

FraudLens uses Next.js static export. Five strategy tests and the production build passed. Legacy Cloudflare/Sites helpers remain in source but are excluded from the Netlify application build. Demo copy distinguishes illustrative strategy curves and transaction explanations from recorded synthetic-data model evaluation; unsupported real-benchmark and latency claims were removed.
