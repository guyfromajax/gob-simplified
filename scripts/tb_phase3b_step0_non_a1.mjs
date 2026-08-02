/**
 * Phase 3b Step 0 (correct proxy) — re-render a non-A1 court and confirm
 * bit-identity with the shipped JPEG.
 *
 * Usage: node scripts/tb_phase3b_step0_non_a1.mjs [slug=ada]
 */
import { execFileSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');
const slug = process.argv[2] || 'ada';
const A1 = new Set([
  'bentley_truman',
  'lancaster',
  'four_corners',
  'morristown',
  'ocean_city',
  'little_york',
  'xavien',
  'south_lancaster',
]);

if (A1.has(slug)) {
  console.error('Refuse: %s is an A1 exclusion. Pick a non-A1 slug.', slug);
  process.exit(2);
}

const shipped = path.join(ROOT, `FrontEnd/static/images/teams/${slug}/${slug}_court.jpg`);
const outDir = path.join(ROOT, 'tmp/court-template/step0-non-a1');
const backup = path.join(outDir, `${slug}_shipped_court.jpg`);
const rerender = path.join(outDir, `${slug}_rerender_court.jpg`);

if (!existsSync(shipped)) {
  console.error('Missing shipped court', shipped);
  process.exit(1);
}

mkdirSync(outDir, { recursive: true });
copyFileSync(shipped, backup);
execFileSync('node', ['scripts/generate_non_a1_courts.mjs', '--force', `--team`, slug], {
  cwd: ROOT,
  stdio: 'inherit',
});
copyFileSync(shipped, rerender);
copyFileSync(backup, shipped);

const a = readFileSync(backup);
const b = readFileSync(rerender);
const equal = a.length === b.length && a.equals(b);

const report = {
  slug,
  status: equal ? 'PASS' : 'FAIL',
  exact_bytes_equal: equal,
  shipped_bytes: a.length,
  rerender_bytes: b.length,
  a1_exclusions: [...A1],
};
writeFileSync(path.join(outDir, `step0_${slug}_bytes.json`), JSON.stringify(report, null, 2));

console.log(JSON.stringify(report, null, 2));
if (!equal) process.exit(1);
console.log('A1 exclusions (8):', [...A1].join(', '));
console.log('VERDICT: PASS — shipped court is bit-identical to a fresh render from the constants.');
