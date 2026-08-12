/**
 * Measure full court render cost (canvas + JPEG blob) — gob-asset-architecture §3.2.
 *
 * Desktop: default Chromium.
 * Low-end proxy: CDP Emulation.setCPUThrottlingRate(4) (4× slowdown).
 *
 * Usage: node scripts/tb_phase3b_court_render_timing.mjs
 */
import fs from 'fs';
import http from 'http';
import path from 'path';
import { fileURLToPath } from 'url';
import { chromium } from '@playwright/test';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');
const STATIC = path.join(ROOT, 'FrontEnd/static');
const OUT = path.join(ROOT, 'tmp/court-template/render-timing.json');

const COURT = {
  hardwoodStyle: 'dark_light',
  oobColor: '#112233',
  laneColor: '#AABBCC',
  outsideWoodColor: '#FFEEDD',
  halfArcFillColor: '#010203',
  primary: '#ec1d28',
  secondary: '#15181f',
  useOverlays: false,
};

async function startServer() {
  const server = http.createServer((req, res) => {
    const rel = decodeURIComponent((req.url || '/').split('?')[0]);
    const p = path.join(STATIC, rel);
    if (!p.startsWith(STATIC) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) {
      res.writeHead(404);
      res.end();
      return;
    }
    res.writeHead(200);
    fs.createReadStream(p).pipe(res);
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const port = server.address().port;
  return { server, base: `http://127.0.0.1:${port}` };
}

async function measure(page, label, cpuThrottle) {
  const client = await page.context().newCDPSession(page);
  await client.send('Emulation.setCPUThrottlingRate', { rate: cpuThrottle });

  const samples = await page.evaluate(async (court) => {
    const G = window.TeamCourtGenerator;
    const times = [];
    // Warm once (fonts/overlays path unused with useOverlays:false).
    G.renderCourtCanvas(court);
    for (let i = 0; i < 5; i += 1) {
      const t0 = performance.now();
      const canvas = G.renderCourtCanvas(court);
      await new Promise((resolve, reject) => {
        canvas.toBlob(
          (blob) => (blob ? resolve(blob) : reject(new Error('toBlob failed'))),
          'image/jpeg',
          0.92
        );
      });
      times.push(performance.now() - t0);
    }
    times.sort((a, b) => a - b);
    const sum = times.reduce((a, b) => a + b, 0);
    return {
      samples_ms: times.map((t) => Math.round(t * 10) / 10),
      median_ms: Math.round(times[Math.floor(times.length / 2)] * 10) / 10,
      mean_ms: Math.round((sum / times.length) * 10) / 10,
      min_ms: Math.round(times[0] * 10) / 10,
      max_ms: Math.round(times[times.length - 1] * 10) / 10,
    };
  }, COURT);

  await client.send('Emulation.setCPUThrottlingRate', { rate: 1 });
  return { label, cpu_throttle: cpuThrottle, ...samples };
}

const html = `<!doctype html><html><body>
<script src="/js/shared/teamCourtGenerator.js"></script>
</body></html>`;
fs.writeFileSync(path.join(STATIC, '_court_timing.html'), html);

const { server, base } = await startServer();
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto(`${base}/_court_timing.html`);

const desktop = await measure(page, 'desktop', 1);
const lowEndProxy = await measure(page, 'low_end_proxy_4x_cpu', 4);

await browser.close();
server.close();
try {
  fs.unlinkSync(path.join(STATIC, '_court_timing.html'));
} catch (e) { /* ignore */ }

const report = {
  measured_at: new Date().toISOString(),
  note:
    'Full 3333×2083 canvas render + JPEG blob (useOverlays:false). ' +
    'low_end_proxy uses CDP 4× CPU throttle — not a physical device. ' +
    'Architecture stays parameters-only; add a disposable cache only if these are slow.',
  desktop,
  low_end_proxy: lowEndProxy,
};

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
