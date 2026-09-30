#!/usr/bin/env node
'use strict';
/**
 * Cold Scouting open: click → #scouting-view .opp-n.
 * Same path as reports/perf-prep-cold-open/scout-waterfall.js
 * (Office → Prep/Training → Scouting). One seed, N runs, desktop + online.
 *
 *   LABEL=before node reports/prep-scouting-speed-sfx/measure-waterfall.js
 */
const fs = require('fs');
const http = require('http');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('@playwright/test');
const { stubAuth } = require('../../tests/e2e/helpers/auth');

const ROOT = process.env.MEASURE_ROOT || path.resolve(__dirname, '../..');
const PORT = Number(process.env.PORT || 8173);
const BASE = `http://127.0.0.1:${PORT}`;
const RUNS = Number(process.env.RUNS || 5);
const LABEL = process.env.LABEL || 'run';
const WARM = process.env.WARM === '1';
const SKIP_PREFETCH = process.env.SKIP_PREFETCH === '1';
const OUT_DIR = process.env.OUT_DIR || path.resolve(__dirname);
const PY = process.env.PYTHON_PATH || path.join(process.env.HOME, 'gob-simplified/.venv/bin/python');

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }
function httpOk(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => { res.resume(); resolve(res.statusCode === 200); });
    req.on('error', () => resolve(false));
    req.setTimeout(2000, () => { req.destroy(); resolve(false); });
  });
}

function summarize(events) {
  const reqs = events.filter((e) => e.kind === 'req');
  const interesting = reqs.filter((e) => /play-next-game|team-data|scouting-report/.test(e.url));
  return interesting.map((e) => ({
    t: e.t,
    method: e.method,
    path: e.url.replace(BASE, '').split('?')[0],
  }));
}

async function startServer() {
  const sqlite = `/tmp/gob-scout-speed-${PORT}.sqlite`;
  for (const f of [sqlite, `${sqlite}-wal`, `${sqlite}-shm`]) fs.rmSync(f, { force: true });
  const env = { ...process.env, PORT: String(PORT), GOB_LOOPBACK_PORT: String(PORT), GOB_DESKTOP_E2E_SQLITE: sqlite };
  delete env.CI;
  const log = fs.openSync(`/tmp/gob-scout-speed-${PORT}.log`, 'w');
  const child = spawn(PY, ['tests/e2e/helpers/seed_and_serve_desktop.py'], { cwd: ROOT, env, stdio: ['ignore', log, log] });
  for (let i = 0; i < 180; i += 1) {
    if (await httpOk(`${BASE}/app-config`)) return child;
    if (child.exitCode !== null) throw new Error(`server exited ${child.exitCode}`);
    await sleep(1000);
  }
  throw new Error('server timeout');
}

async function seedFranchise(browser) {
  const boot = await browser.newContext();
  const bootPage = await boot.newPage();
  await bootPage.goto(`${BASE}/mode-select.html`);
  const res = await bootPage.request.post(`${BASE}/franchise/select-team`, { data: { team_name: 'Lancaster' } });
  if (!res.ok()) throw new Error(`select-team ${res.status()}`);
  const body = await res.json();
  await boot.close();
  return {
    fid: body.franchise_id,
    tid: String(body.user_team_id || body.team_id || ''),
  };
}

async function oneOpen(browser, profile, fid, tid, shotPath) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  if (profile === 'desktop') {
    await ctx.addInitScript((port) => {
      window.GOB_BUILD_PROFILE = 'desktop';
      window.GOB_LOOPBACK_PORT = Number(port);
    }, PORT);
  } else {
    process.env.BASE_URL = BASE;
    await stubAuth(ctx);
  }
  if (SKIP_PREFETCH) {
    await ctx.addInitScript(() => { window.__gobSkipScoutingPrefetch = true; });
  }
  const page = await ctx.newPage();
  const q = new URLSearchParams({ franchise_id: fid, tab: 'home-tab' });
  if (tid) { q.set('team_id', tid); q.set('user_team_id', tid); }
  await page.goto(`${BASE}/franchise-command-center.html?${q}`);
  await page.waitForSelector('#home-tab .office-col .nx-name', { timeout: 30000 });

  await page.click('.rail [data-gob-section="prep"]');
  await page.waitForSelector('#training-view .training-container .drill-group, #training-view .slider, #training-view .ps', { timeout: 30000 });
  if (WARM) {
    await page.waitForFunction(() => {
      const cache = window.__gobScoutingReportCache;
      return !!(cache && Object.keys(cache).length);
    }, null, { timeout: 15000 }).catch(() => {});
  }

  const events = [];
  const t0 = Date.now();
  page.on('request', (req) => {
    events.push({ t: Date.now() - t0, kind: 'req', method: req.method(), url: req.url() });
  });
  page.on('response', (resp) => {
    events.push({ t: Date.now() - t0, kind: 'res', status: resp.status(), url: resp.url() });
  });

  const painted = await page.evaluate(() => {
    const tClick = performance.now();
    window.__scoutTrace = { t0: tClick, marks: [] };
    const orig = window.GOBViews && window.GOBViews.show;
    if (orig && !orig.__scoutWrapped) {
      window.GOBViews.show = function (id) {
        window.__scoutTrace.marks.push({ t: Math.round(performance.now() - window.__scoutTrace.t0), ev: 'show', id: id });
        const out = orig.apply(this, arguments);
        Promise.resolve(out).then(function () {
          window.__scoutTrace.marks.push({ t: Math.round(performance.now() - window.__scoutTrace.t0), ev: 'show-done', id: id });
        });
        return out;
      };
      window.GOBViews.show.__scoutWrapped = true;
    }
    const btn = document.querySelector('#gob-subtabs .tb[data-key="scouting-view"]');
    if (btn) btn.click();
    return new Promise((resolve) => {
      const deadline = tClick + 30000;
      const tick = () => {
        if (document.querySelector('#scouting-view .opp-n')) {
          resolve(Math.round(performance.now() - tClick));
          return;
        }
        if (performance.now() > deadline) {
          resolve(-1);
          return;
        }
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  });
  const pwT0 = Date.now();
  await page.waitForSelector('#scouting-view .opp-n', { state: 'attached', timeout: 30000 }).catch(() => {});
  const pwAttached = Date.now() - pwT0;
  const trace = await page.evaluate(() => {
    const origin = window.__scoutTrace && window.__scoutTrace.t0 != null
      ? window.__scoutTrace.t0 : 0;
    const marks = (performance.getEntriesByType('mark') || [])
      .filter((e) => String(e.name).indexOf('scouting-') === 0)
      .map((e) => ({ name: e.name, t: Math.round(e.startTime - origin) }));
    return { page: window.__scoutTrace || null, marks: marks };
  });
  const breakdown = { painted, pwAttached, warm: WARM, skipPrefetch: SKIP_PREFETCH, trace };
  if (shotPath) {
    await page.screenshot({ path: shotPath, fullPage: false });
  }
  const waterfall = summarize(events);
  await ctx.close();
  return { painted, breakdown, waterfall };
}

(async () => {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const server = await startServer();
  const browser = await chromium.launch();
  try {
    const seed = await seedFranchise(browser);
    const result = { label: LABEL, seed, runs: { desktop: [], online: [] } };
    let shot = true;
    for (const profile of ['desktop', 'online']) {
      for (let i = 0; i < RUNS; i += 1) {
        const shotPath = shot ? path.join(OUT_DIR, `scouting-${LABEL}-1280.png`) : null;
        const one = await oneOpen(browser, profile, seed.fid, seed.tid, shotPath);
        shot = false;
        result.runs[profile].push(one);
        console.log(JSON.stringify({ label: LABEL, profile, i: i + 1, painted: one.painted, breakdown: one.breakdown, waterfall: one.waterfall }));
      }
    }
    const outFile = path.join(OUT_DIR, `waterfall-${LABEL}.json`);
    fs.writeFileSync(outFile, JSON.stringify(result, null, 2));
    console.log('WROTE', outFile);
  } finally {
    await browser.close();
    if (server) server.kill('SIGTERM');
  }
})().catch((err) => { console.error(err); process.exit(1); });
