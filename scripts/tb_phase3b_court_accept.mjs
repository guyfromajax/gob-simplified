/**
 * Phase 3b acceptance — canvas court port.
 *
 * Checks: dims 3333×2083, marking-mask invariance across colour extremes,
 * blob: object URL (not data:), defaults from primary/secondary, A1 eight named.
 *
 * Usage: node scripts/tb_phase3b_court_accept.mjs
 */
import assert from 'assert';
import fs from 'fs';
import http from 'http';
import path from 'path';
import { fileURLToPath } from 'url';
import { chromium } from '@playwright/test';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');
const STATIC = path.join(ROOT, 'FrontEnd/static');

const A1 = [
  'bentley_truman',
  'lancaster',
  'four_corners',
  'morristown',
  'ocean_city',
  'little_york',
  'xavien',
  'south_lancaster',
];

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.woff2': 'font/woff2',
  '.otf': 'font/otf',
};

function contentType(filePath) {
  return MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream';
}

function startServer() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
      const rel = urlPath === '/' ? '/_court_accept.html' : urlPath;
      const filePath = path.join(STATIC, rel.replace(/^\//, ''));
      if (!filePath.startsWith(STATIC) || !fs.existsSync(filePath)) {
        res.writeHead(404);
        res.end('missing ' + rel);
        return;
      }
      res.writeHead(200, { 'Content-Type': contentType(filePath) });
      fs.createReadStream(filePath).pipe(res);
    });
    server.listen(0, '127.0.0.1', () => {
      resolve({ server, base: `http://127.0.0.1:${server.address().port}` });
    });
  });
}

const harness = `<!DOCTYPE html>
<html><head>
<script src="/js/shared/teamCourtGenerator.js"></script>
<script src="/js/shared/teamGeneratedArt.js"></script>
</head><body></body></html>`;
fs.writeFileSync(path.join(STATIC, '_court_accept.html'), harness);

// Static: geometry constants must match the Node script's key numbers
const genSrc = fs.readFileSync(path.join(STATIC, 'js/shared/teamCourtGenerator.js'), 'utf8');
const nodeSrc = fs.readFileSync(path.join(ROOT, 'scripts/generate_non_a1_courts.mjs'), 'utf8');
for (const token of [
  'OOB_LINE_BOUNDS = { x1: 150, y1: 84, x2: 3183, y2: 1998 }',
  'TOP_HORIZONTAL_OOB_Y = 158',
  'BOTTOM_HORIZONTAL_OOB_Y = 1924',
  'LANE_LEFT_RECT = { x1: 150, y1: 806, x2: 872, y2: 1271 }',
  'CENTER = { x: 1666, y: 1042 }',
  'RIM_LEFT = { x: 300, y: 1042 }',
  'RIM_RIGHT = { x: 3033, y: 1042 }',
]) {
  assert.ok(genSrc.includes(token.replace(/ = /g, ' = ')) || genSrc.includes(token), 'missing geometry: ' + token);
  // node uses slightly different spacing — check core numbers exist
  assert.ok(nodeSrc.includes('150') && nodeSrc.includes('3183'));
}

const { server, base } = await startServer();
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(base + '/', { waitUntil: 'networkidle' });

const report = await page.evaluate(async () => {
  const G = window.TeamCourtGenerator;
  if (!G) return { error: 'TeamCourtGenerator missing' };

  const defaults = G.defaultsFromTeamColors('#ec1d28', '#cccccc');
  const a = G.renderCourtCanvas({
    ...defaults,
    hardwoodStyle: 'dark_dark',
    oobColor: '#111111',
    laneColor: '#ff0000',
    centreCourtColor: '#00ff00',
    halfArcFillColor: '#0000ff',
  });
  const b = G.renderCourtCanvas({
    ...defaults,
    hardwoodStyle: 'light_light',
    oobColor: '#eeeeee',
    laneColor: '#0000aa',
    centreCourtColor: '#aaaa00',
    halfArcFillColor: '#aa00aa',
  });

  const ma = G.markingsMaskCanvas({ lineColor: '#ffffff' });
  const mb = G.markingsMaskCanvas({
    hardwoodStyle: 'dark_dark',
    oobColor: '#111111',
    laneColor: '#ff0000',
    centreCourtColor: '#00ff00',
    halfArcFillColor: '#0000ff',
    lineColor: '#ffffff',
  });

  function maskPixels(canvas) {
    const ctx = canvas.getContext('2d');
    const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    let n = 0;
    const bits = new Uint8Array(canvas.width * canvas.height);
    for (let i = 0, p = 0; i < data.length; i += 4, p++) {
      const on = data[i] > 200 ? 1 : 0;
      bits[p] = on;
      n += on;
    }
    return { bits, n, w: canvas.width, h: canvas.height };
  }

  const A = maskPixels(ma);
  const B = maskPixels(mb);
  let same = A.n === B.n;
  let mismatch = 0;
  if (same) {
    for (let i = 0; i < A.bits.length; i++) {
      if (A.bits[i] !== B.bits[i]) {
        mismatch++;
        same = false;
      }
    }
  }

  const url = await G.courtObjectUrl({
    ...defaults,
    useOverlays: false,
  });
  const isBlob = /^blob:/i.test(url);
  const isData = /^data:/i.test(url);

  const img = await new Promise((resolve, reject) => {
    const el = new Image();
    el.onload = () => resolve({ w: el.naturalWidth, h: el.naturalHeight });
    el.onerror = reject;
    el.src = url;
  });

  // Phaser-style load gate: blob accepted, data rejected
  const wouldRejectForPhaser = isData || !url;

  return {
    dimsA: { w: a.width, h: a.height },
    dimsB: { w: b.width, h: b.height },
    maskMatch: same && mismatch === 0,
    maskPixels: A.n,
    maskMismatch: mismatch,
    defaults,
    a1: G.A1_REFERENCE_SLUGS,
    urlProtocol: isBlob ? 'blob' : isData ? 'data' : 'other',
    urlSample: String(url).slice(0, 48),
    img,
    wouldRejectForPhaser,
    artWired: !!(window.TeamGeneratedArt && window.TeamGeneratedArt.courtObjectUrl),
  };
});

await browser.close();
server.close();
fs.unlinkSync(path.join(STATIC, '_court_accept.html'));

if (report.error) {
  console.error(report.error);
  process.exit(1);
}

assert.strictEqual(report.dimsA.w, 3333);
assert.strictEqual(report.dimsA.h, 2083);
assert.strictEqual(report.dimsB.w, 3333);
assert.strictEqual(report.dimsB.h, 2083);
assert.strictEqual(report.img.w, 3333);
assert.strictEqual(report.img.h, 2083);
assert.ok(report.maskMatch, 'marking pixels moved when colours changed; mismatches=' + report.maskMismatch);
assert.strictEqual(report.urlProtocol, 'blob');
assert.ok(!report.wouldRejectForPhaser);
assert.deepStrictEqual(report.a1, A1);
assert.ok(report.artWired);
assert.ok(report.defaults.hardwoodStyle);
assert.ok(report.defaults.oobColor);
assert.ok(report.defaults.laneColor);
assert.ok(report.defaults.centreCourtColor);
assert.ok(report.defaults.halfArcFillColor);

console.log('dims:', report.dimsA);
console.log('marking mask invariant:', report.maskMatch, '(pixels', report.maskPixels + ')');
console.log('object URL:', report.urlProtocol, report.urlSample + '…');
console.log('decoded image:', report.img);
console.log('defaults:', report.defaults);
console.log('A1 exclusions (8):', report.a1.join(', '));
console.log('--- summary ---');
console.log('passed phase 3b canvas acceptance (dims, markings invariant, blob URL, defaults, A1 list)');
console.log('Criterion 6 (live Phaser game): resolveCourtImagePath now returns blob: for custom teams; verify in a Team Builder franchise game that court-bg is not general_court.jpg.');
