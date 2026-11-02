import { execFileSync } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';

// Public build provenance only. Never include environment, credentials or paths.
let sourceCommit = null;
try {
  const candidate = execFileSync('git', ['rev-parse', 'HEAD'], {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'ignore'],
  }).trim();
  if (/^[0-9a-f]{40}$/i.test(candidate)) sourceCommit = candidate;
} catch {
  const candidate = process.env.COMMIT_REF ?? '';
  if (/^[0-9a-f]{40}$/i.test(candidate)) sourceCommit = candidate;
}
const study = JSON.parse(await readFile('public/evaluation.json', 'utf8'));
if (typeof study.study_id !== 'string' || !/^[0-9a-f]{16}$/i.test(study.study_id)) {
  throw new Error('The public synthetic study must have a valid study identifier.');
}
const release = {
  project: 'FraudLens',
  source_repository: 'https://github.com/Poojan-Desai/FraudLens',
  source_commit: sourceCommit,
  study_id: study.study_id,
  built_at: new Date().toISOString(),
  deployment_scope: 'Static synthetic-study dashboard; investigation API is local only.',
};
await writeFile('out/release.json', `${JSON.stringify(release, null, 2)}\n`);
console.log(`Static release provenance written for ${sourceCommit ?? 'unavailable commit'}.`);
