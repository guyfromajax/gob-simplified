#!/usr/bin/env node
'use strict';
const fs = require('fs');
const http = require('http');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('@playwright/test');

const ROOT = process.env.MEASURE_ROOT || path.resolve(__dirname, '../..');
const PORT = Number(process.env.PORT || 0);
if (!PORT) throw new Error('PORT required');
const BASE = `http://127.0.0.1:${PORT}`;
const RUNS = Number(process.env.RUNS || 5);

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }
function httpOk(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => { res.resume(); resolve(res.statusCode === 200); });
    req.on('error', () => resolve(false));
    req.setTimeout(2000, () => { req.destroy(); resolve(false); });
  });
}

async function startServer() {
  const sqlite = `/tmp/gob-scout-clicks-${PORT}.sqlite`;
  for (const f of [sqlite, `${sqlite}-wal`, `${sqlite}-shm`]) fs.rmSync(f, { force: true });
  const env = { ...process.env, PORT: String(PORT), GOB_LOOPBACK_PORT: String(PORT), GOB_DESKTOP_E2E_SQLITE: sqlite };
  delete env.CI;
  const py = process.env.PYTHON_PATH || path.join(ROOT, '.venv', 'bin', 'python');
  const log = fs.openSync(`/tmp/gob-scout-clicks-${PORT}.log`, 'w');
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
  const times = [];
  try {
    for (let i = 0; i < RUNS; i += 1) {
      const boot = await browser.newContext();
      const bootPage = await boot.newPage();
      await bootPage.goto(`${BASE}/mode-select.html`);
      const res = await bootPage.request.post(`${BASE}/franchise/select-team`, { data: { team_name: 'Lancaster' } });
      const body = await res.json();
      await boot.close();
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
      await ctx.addInitScript((port) => { window.GOB_BUILD_PROFILE = 'desktop'; window.GOB_LOOPBACK_PORT = Number(port); }, PORT);
      const page = await ctx.newPage();
      const q = new URLSearchParams({ franchise_id: body.franchise_id, tab: 'home-tab' });
      if (body.user_team_id || body.team_id) {
        const tid = String(body.user_team_id || body.team_id);
        q.set('team_id', tid);
        q.set('user_team_id', tid);
      }
      await page.goto(`${BASE}/franchise-command-center.html?${q}`);
      await page.waitForSelector('#home-tab .office-col .nx-name', { timeout: 30000 });
      await page.click('.rail [data-gob-section="prep"]');
      await page.waitForSelector('#training-view .training-container .drill-group, #training-view .slider, #training-view .ps', { timeout: 30000 });
      const before = await page.evaluate(() => {
        const el = document.querySelector('#scouting-view .opp-n');
        return el ? { text: el.innerText, vis: el.getBoundingClientRect().height > 0 } : null;
      });
      const t0 = Date.now();
      await page.click('#gob-subtabs .tb[data-key="scouting-view"]');
      await page.waitForSelector('#scouting-view .opp-n', { timeout: 30000 });
      const ms = Date.now() - t0;
      const name = await page.locator('#scouting-view .opp-n').innerText();
      times.push({ ms, name, before });
      await ctx.close();
    }
  } finally {
    await browser.close();
    if (server) server.kill('SIGTERM');
  }
  const sorted = times.map((x) => x.ms).slice().sort((a, b) => a - b);
  const med = sorted[Math.floor(sorted.length / 2)];
  console.log(JSON.stringify({ median: med, worst: sorted[sorted.length - 1], times }, null, 2));
})().catch((err) => { console.error(err); process.exit(1); });
