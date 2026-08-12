/**
 * Phase 3b — parameter-space sweep: browser port vs Node oracle.
 *
 * For every Node-equivalent combination of the five court controls, render both
 * sides (overlays off) and diff pixels. The Node script is the exact oracle.
 *
 * Node-equivalent mapping:
 *   hardwoodStyle     → HARDWOOD_VARIANTS key (all 9 exist in the oracle)
 *   outsideWoodColor  → HARDWOOD_TONES[variant.outside] (outside wood / main floor;
 *                        NOT the 3PT key lobes — those are inside wood from the style)
 *   laneColor         → resolveAssignmentColor(lane token)
 *   halfArcFillColor  → resolveAssignmentColor(half-circle token)
 *   oobColor          → resolveAssignmentColor(oob token)
 *
 * Port-only (no Node reference — reported, not skipped silently):
 *   arbitrary hex for centre/lane/half/oob that is not a token resolution
 *
 * Usage: node scripts/tb_phase3b_param_sweep.mjs
 */
import assert from 'assert';
import { execFileSync } from 'node:child_process';
import fs from 'fs';
import http from 'http';
import path from 'path';
import { fileURLToPath } from 'url';
import { chromium } from '@playwright/test';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');
const STATIC = path.join(ROOT, 'FrontEnd/static');
const OUT_DIR = path.join(ROOT, 'tmp/court-template/param-sweep');
const PRIMARY = '#27408E';
const SECONDARY = '#FF00FF';

const HARDWOOD_KEYS = [
  'light_light',
  'light_medium',
  'light_dark',
  'medium_light',
  'medium_medium',
  'medium_dark',
  'dark_light',
  'dark_medium',
  'dark_dark',
];
const LANE_KEYS = ['primary', 'secondary'];
const HALF_KEYS = ['primary', 'secondary'];
const OOB_KEYS = ['black', 'primary'];

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
};

function startServer() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
      const rel = urlPath === '/' ? '/_court_sweep.html' : urlPath;
      const filePath = path.join(STATIC, rel.replace(/^\//, ''));
      if (!filePath.startsWith(STATIC) || !fs.existsSync(filePath)) {
        res.writeHead(404);
        res.end('missing');
        return;
      }
      res.writeHead(200, {
        'Content-Type': MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream',
      });
      fs.createReadStream(filePath).pipe(res);
    });
    server.listen(0, '127.0.0.1', () => {
      resolve({ server, base: `http://127.0.0.1:${server.address().port}` });
    });
  });
}

function renderOracle(combo) {
  const outPath = path.join(
    OUT_DIR,
    `oracle_${combo.hardwood}_${combo.lane}_${combo.half}_${combo.oob}.png`
  );
  const raw = execFileSync(
    'node',
    [
      'scripts/generate_non_a1_courts.mjs',
      '--oracle-render',
      '--hardwood',
      combo.hardwood,
      '--lane',
      combo.lane,
      '--half',
      combo.half,
      '--oob',
      combo.oob,
      '--primary',
      PRIMARY,
      '--secondary',
      SECONDARY,
      '--out',
      outPath,
    ],
    { cwd: ROOT, encoding: 'utf8' }
  );
  const report = JSON.parse(raw.trim().split('\n').filter(Boolean).pop());
  return { outPath, report };
}

function aeDiff(oraclePath, portPath) {
  // Absolute-error pixel count; JPEG encode on both sides means a small fuzz.
  let ae = 0;
  try {
    execFileSync('magick', ['compare', '-metric', 'AE', '-fuzz', '2%', oraclePath, portPath, 'null:'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  } catch (err) {
    // ImageMagick compare exits 1 when images differ; stderr holds the AE count.
    const raw = String((err && err.stderr) || err.stdout || '0').trim();
    ae = Number(raw.split(/\s+/)[0]) || 0;
  }
  const meta = execFileSync('magick', ['identify', '-format', '%w %h', oraclePath], {
    encoding: 'utf8',
  })
    .trim()
    .split(/\s+/)
    .map(Number);
  const total = meta[0] * meta[1];
  return { ae, total, ratio: total ? ae / total : 1 };
}

fs.mkdirSync(OUT_DIR, { recursive: true });
fs.writeFileSync(
  path.join(STATIC, '_court_sweep.html'),
  '<!doctype html><script src="/js/shared/teamCourtGenerator.js"></script>'
);

const combos = [];
for (const hardwood of HARDWOOD_KEYS) {
  for (const lane of LANE_KEYS) {
    for (const half of HALF_KEYS) {
      for (const oob of OOB_KEYS) {
        combos.push({ hardwood, lane, half, oob });
      }
    }
  }
}

const { server, base } = await startServer();
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto(`${base}/_court_sweep.html`);

const failures = [];
const results = [];

for (const combo of combos) {
  const { outPath: oraclePath, report } = renderOracle(combo);
  const resolved = report.resolved;
  const portPath = path.join(
    OUT_DIR,
    `port_${combo.hardwood}_${combo.lane}_${combo.half}_${combo.oob}.png`
  );

  const portB64 = await page.evaluate(
    ({ resolved, hardwood }) => {
      const G = window.TeamCourtGenerator;
      const canvas = G.renderCourtCanvas({
        hardwoodStyle: hardwood,
        // Match Node outside wood exactly (style outside tone).
        outsideWoodColor: resolved.outside_wood,
        laneColor: resolved.lane_color,
        halfArcFillColor: resolved.half_circle_color,
        oobColor: resolved.oob_color,
        lineColor: resolved.line_color,
        primary: resolved.primary,
        secondary: resolved.secondary,
        useOverlays: false,
      });
      return canvas.toDataURL('image/png').split(',')[1];
    },
    { resolved, hardwood: combo.hardwood }
  );
  fs.writeFileSync(portPath, Buffer.from(portB64, 'base64'));

  function hexAt(img, x, y) {
    return execFileSync('magick', [img, '-format', `%[hex:u.p{${x},${y}}]`, 'info:'], {
      encoding: 'utf8',
    })
      .trim()
      .slice(0, 6)
      .toLowerCase();
  }
  function hexClose(a, b, tol = 2) {
    const pa = [0, 2, 4].map((i) => parseInt(a.slice(i, i + 2), 16));
    const pb = [0, 2, 4].map((i) => parseInt(b.slice(i, i + 2), 16));
    return pa.every((v, i) => Math.abs(v - pb[i]) <= tol);
  }

  // Semantic probes for the five colour params (grain/blur AE is informational —
  // canvas vs ImageMagick hardwood finish is not bit-identical by design).
  //
  // Region probes (must not conflate inside vs outside wood):
  //   (1600,1042) midcourt          → outside_wood (= outsideWoodColor)
  //   (400,450)   left 3PT lobe     → inside_wood  (style only; not outsideWoodColor)
  const halfProbe = hexAt(portPath, 950, 1042);
  const expectHalf = resolved.half_circle_color.replace('#', '').toLowerCase();
  const outsideProbe = hexAt(portPath, 1600, 1042);
  const expectOutside = resolved.outside_wood.replace('#', '').toLowerCase();
  const insideProbe = hexAt(portPath, 400, 450);
  const expectInside = resolved.inside_wood.replace('#', '').toLowerCase();
  const laneProbe = hexAt(portPath, 500, 1042);
  const expectLane = resolved.lane_color.replace('#', '').toLowerCase();
  const oobProbe = hexAt(portPath, 40, 40);
  const expectOob = resolved.oob_color.replace('#', '').toLowerCase();
  const oracleHalf = hexAt(oraclePath, 950, 1042);
  const oracleOutside = hexAt(oraclePath, 1600, 1042);
  const oracleInside = hexAt(oraclePath, 400, 450);
  const oracleLane = hexAt(oraclePath, 500, 1042);
  const oracleOob = hexAt(oraclePath, 40, 40);

  const diff = aeDiff(oraclePath, portPath);

  const outside_ok =
    hexClose(outsideProbe, expectOutside, 3) && hexClose(outsideProbe, oracleOutside, 4);
  // Grain/blur shifts inside-lobe samples more than flat midcourt; widen expect tol.
  const inside_ok =
    hexClose(insideProbe, expectInside, 12) && hexClose(insideProbe, oracleInside, 6);
  // When style splits tones, outsideWoodColor must not have painted the key lobe.
  const region_split_ok =
    expectInside === expectOutside || !hexClose(insideProbe, expectOutside, 8);

  const row = {
    combo,
    half_arc_ok: hexClose(halfProbe, expectHalf, 3) && hexClose(halfProbe, oracleHalf, 4),
    outside_ok,
    inside_ok,
    region_split_ok,
    // legacy alias used by earlier report consumers
    centre_ok: outside_ok,
    lane_ok: hexClose(laneProbe, expectLane, 3) && hexClose(laneProbe, oracleLane, 4),
    oob_ok: hexClose(oobProbe, expectOob, 3) && hexClose(oobProbe, oracleOob, 4),
    halfProbe,
    expectHalf,
    oracleHalf,
    outsideProbe,
    expectOutside,
    oracleOutside,
    insideProbe,
    expectInside,
    oracleInside,
    laneProbe,
    expectLane,
    oobProbe,
    expectOob,
    diff,
  };
  results.push(row);

  if (
    !row.half_arc_ok ||
    !row.outside_ok ||
    !row.inside_ok ||
    !row.region_split_ok ||
    !row.lane_ok ||
    !row.oob_ok
  ) {
    failures.push(row);
  }
}

await browser.close();
server.close();
try {
  fs.unlinkSync(path.join(STATIC, '_court_sweep.html'));
} catch (e) { /* ignore */ }

const portOnlyNote = {
  note:
    'Arbitrary hex for outsideWoodColor / laneColor / halfArcFillColor / oobColor ' +
    'beyond Node token resolutions has no oracle output — those are port extensions. ' +
    'This sweep covers the Node token space (9 hardwood × lane × half × oob) with ' +
    'outsideWoodColor locked to the style outside tone.',
  node_hardwood_keys: HARDWOOD_KEYS.length,
  combos_tested: combos.length,
};

fs.writeFileSync(
  path.join(OUT_DIR, 'sweep_report.json'),
  JSON.stringify({ portOnlyNote, failures: failures.length, results }, null, 2)
);

console.log(JSON.stringify({
  status: failures.length ? 'FAIL' : 'PASS',
  combos: combos.length,
  failures: failures.length,
  portOnlyNote,
  sampleFailure: failures[0] || null,
}, null, 2));

if (failures.length) process.exit(1);
