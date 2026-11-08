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
const comparison = JSON.parse(await readFile('public/model-comparison.json', 'utf8'));
if (!/^[0-9a-f]{16}$/.test(comparison.plan_id) || typeof comparison.comparison?.promotion_gate_passed !== 'boolean') {
  throw new Error('The independent model comparison must have a valid plan and gate result.');
}
const release = {
  project: 'FraudLens',
  source_repository: 'https://github.com/Poojan-Desai/FraudLens',
  source_commit: sourceCommit,
  study_id: study.study_id,
  model_comparison_plan_id: comparison.plan_id,
  model_comparison_gate_passed: comparison.comparison.promotion_gate_passed,
  built_at: new Date().toISOString(),
  deployment_scope: 'Static synthetic model comparison and original policy dashboard; training, scoring and investigation API are local only.',
};
await writeFile('out/release.json', `${JSON.stringify(release, null, 2)}\n`);
console.log(`Static release provenance written for ${sourceCommit ?? 'unavailable commit'}.`);
