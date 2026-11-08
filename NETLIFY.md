# Netlify deployment

Existing site: [fraudlens-poojan-desai](https://fraudlens-poojan-desai.netlify.app).
Site ID: `b6855c51-9f33-4cb4-b68f-a816db9ae76b`.

The production artifact is the Next.js static export in `out/`. It includes the
current independent model-comparison panel, original four-window study, public
evaluation/model-comparison snapshots and
local investigation interface. FastAPI, model training, the case database and
credentials remain local; this deployment does not create a hosted case API or
live model-serving service. Use the README's loopback setup for the complete
investigation workflow. Authenticated case writes are not exposed publicly.

## Build and publish to the existing site

Use Node.js 22.13+ and an authenticated Netlify CLI:

```sh
npm ci
npm run test:unit
npm run lint
npm run build
netlify deploy --prod --dir out --no-build --site b6855c51-9f33-4cb4-b68f-a816db9ae76b
```

Only `out/` is uploaded. Never publish the repository root, `.env`, `work/`, runtime
databases, generated local tokens or executable model bundles. The legacy
Cloudflare/Sites helpers are excluded from this build. Deployment remains manual;
no site, account, security setting or GitHub build hook needs to be created.

## Verify the live revision

The build writes `out/release.json` with only the Git commit, repository URL,
synthetic study ID, UTC build time and static/local boundary. After publishing,
read [the public release manifest](https://fraudlens-poojan-desai.netlify.app/release.json)
and compare `source_commit` with the pushed commit. Confirm the existing site ID,
production deploy state and public HTML/evaluation bytes against the local export.
A static release manifest is provenance metadata, not a security certification.
