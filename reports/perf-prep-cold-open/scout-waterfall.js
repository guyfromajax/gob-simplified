#!/usr/bin/env node
'use strict';
/**
 * One cold Scouting open, same click path as measure_nav_timing.js
 * (rail Prep → training done → Scouting sub-tab). Prints the request
 * waterfall from the click until #scouting-view .opp-n.
 */
const fs = require('fs');
const http = require('http');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('@playwright/test');
const { stubAuth } = require('../../tests/e2e/helpers/auth');

const ROOT = process.env.MEASURE_ROOT || path.resolve(__dirname, '../..');
const PORT = Number(process.env.PORT || 0);
if (!PORT) throw new Error('PORT required');
const BASE = `http://127.0.0.1:${PORT}`;
const PROFILE = process.env.PROFILE || 'desktop';
const OUT = process.env.OUT || '/tmp/scout-waterfall.json';

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }
function httpOk(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => { res.resume(); resolve(res.statusCode === 200); });
    req.on('error', () => resolve(false));
    req.setTimeout(2000, () => { req.destroy(); resolve(false); });
  });
}

async function startServer() {
  const sqlite = `/tmp/gob-scout-waterfall-${PORT}.sqlite`;
  for (const f of [sqlite, `${sqlite}-wal`, `${sqlite}-shm`]) fs.rmSync(f, { force: true });
  const env = { ...process.env, PORT: String(PORT), GOB_LOOPBACK_PORT: String(PORT), GOB_DESKTOP_E2E_SQLITE: sqlite };
  delete env.CI;
  const py = process.env.PYTHON_PATH || path.join(ROOT, '.venv', 'bin', 'python');
  const log = fs.openSync(`/tmp/gob-scout-waterfall-${PORT}.log`, 'w');
  const child = spawn(py, ['tests/e2e/helpers/seed_and_serve_desktop.py'], { cwd: ROOT, env, stdio: ['ignore', log, log] });
  for (let i = 0; i < 180; i += 1) {
    if (await httpOk(`${BASE}/app-config`)) return child;
    if (child.exitCode !== null) throw new Error(`server exited ${child.exitCode}`);
    await sleep(1000);
  }
  throw new Error('server timeout');
}

(async () => {
  const server = await startServer();
  const browser = await chromium.launch();
  try {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    if (PROFILE === 'desktop') {
      await ctx.addInitScript((port) => { window.GOB_BUILD_PROFILE = 'desktop'; window.GOB_LOOPBACK_PORT = Number(port); }, PORT);
    } else {
      process.env.BASE_URL = BASE;
      await stubAuth(ctx);
    }
    const boot = await browser.newContext();
    const bootPage = await boot.newPage();
    await bootPage.goto(`${BASE}/mode-select.html`);
    const res = await bootPage.request.post(`${BASE}/franchise/select-team`, { data: { team_name: 'Lancaster' } });
    if (!res.ok()) throw new Error(`select-team ${res.status()}`);
    const body = await res.json();
    await boot.close();
    const fid = body.franchise_id;
    const tid = String(body.user_team_id || body.team_id || '');

    const page = await ctx.newPage();
    const q = new URLSearchParams({ franchise_id: fid, tab: 'home-tab' });
    if (tid) { q.set('team_id', tid); q.set('user_team_id', tid); }
    await page.goto(`${BASE}/franchise-command-center.html?${q}`);
    await page.waitForSelector('#home-tab .office-col .nx-name', { timeout: 30000 });

    await page.click('.rail [data-gob-section="prep"]');
    await page.waitForSelector('#training-view .training-container .drill-group, #training-view .slider, #training-view .ps', { timeout: 30000 });

    const events = [];
    const t0 = Date.now();
    page.on('request', (req) => {
      events.push({ t: Date.now() - t0, kind: 'req', method: req.method(), url: req.url() });
    });
    page.on('response', (resp) => {
      events.push({ t: Date.now() - t0, kind: 'res', status: resp.status(), url: resp.url() });
    });

    await page.click('#gob-subtabs .tb[data-key="scouting-view"]');
    await page.waitForSelector('#scouting-view .opp-n', { timeout: 30000 });
    const painted = Date.now() - t0;

    const resources = await page.evaluate(() => {
      return performance.getEntriesByType('resource').map((e) => ({
        name: e.name.replace(location.origin, ''),
        start: Math.round(e.startTime),
        dur: Math.round(e.duration),
        transfer: e.transferSize,
        initiator: e.initiatorType,
      })).filter((e) => /scouting|viewLoader|prepEmbed|attributeDisplay|playerYear|play-next-game|team-data|scouting-report|rt-buckets|prep-v2/i.test(e.name));
    });

    const ctxDump = await page.evaluate(() => {
      const fc = window.FranchiseContext;
      let fcFid = '';
      try { fcFid = fc && fc.get ? (fc.get('franchise_id') || '') : ''; } catch (err) { fcFid = 'ERR ' + err.message; }
      return {
        urlFid: (location.search.match(/franchise_id=([^&]+)/) || [])[1] || '',
        fcFid,
        fcReady: !!(fc && typeof fc.get === 'function'),
      };
    });

    const out = { painted, ctxDump, events, resources };
    fs.writeFileSync(OUT, JSON.stringify(out, null, 2));
    console.log(JSON.stringify({ painted, ctxDump, nEvents: events.length, resources }, null, 2));
  } finally {
    await browser.close();
    if (server) server.kill('SIGTERM');
  }
})().catch((err) => { console.error(err); process.exit(1); });
