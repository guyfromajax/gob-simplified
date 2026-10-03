#!/usr/bin/env node
/**
 * Coverage map + tab-vs-page timing for the franchise shell. Read-only against the product.
 *
 * Starts tests/e2e/helpers/seed_and_serve_desktop.py (throwaway SQLite, loopback user) and
 * creates a franchise the way desktop-play-flow.spec.js does. Each pass gets its own franchise.
 *
 * Profiles:
 *   desktop  GOB_BUILD_PROFILE=desktop (the loopback cookie + init flag), as the desktop specs do.
 *   online   the web build: the desktop cookie is hidden from page scripts and auth is stubbed with
 *            tests/e2e/helpers/auth.js. Same server, so server time is local SQLite in both.
 *
 * Passes (--pass=static,probe,smoke,timing; default static,smoke,timing):
 *   static   scan FrontEnd/static/*.html: html.gob, tokens, redirect target, inbound links, specs.
 *   probe    print what each view panel holds after it settles (used to pick the selectors below).
 *   smoke    open every page in both profiles; record where it lands, errors, failed API calls.
 *   timing   click -> content painted, cold (first open, fresh browser context) and warm (second
 *            open, same page), --runs times per profile. Flags skeleton, blank frames, layout shift,
 *            and saves 1280 screencast frames for flagged screens under --shots.
 *
 * Usage:
 *   PORT=8121 node scripts/measure_nav_timing.js --out=/tmp/nav-timing.json --runs=5 \
 *     --shots=reports/coverage-map [--reuse] [--pass=timing]
 * Needs PLAYWRIGHT_BROWSERS_PATH pointing at an installed Chromium when the default cache is not used.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');
const { chromium } = require('@playwright/test');
const { stubAuth } = require('../tests/e2e/helpers/auth');

const ROOT = path.resolve(__dirname, '..');
const STATIC = path.join(ROOT, 'FrontEnd', 'static');
const SPECS = path.join(ROOT, 'tests', 'e2e');

const args = Object.fromEntries(process.argv.slice(2).map((a) => {
  const m = a.match(/^--([^=]+)(?:=(.*))?$/);
  return m ? [m[1], m[2] === undefined ? '1' : m[2]] : [a, '1'];
}));
const PORT = Number(args.port || process.env.PORT || 0);
if (!PORT) throw new Error('Pass --port or PORT (pick a free one; check lsof first)');
const BASE = `http://127.0.0.1:${PORT}`;
const RUNS = Number(args.runs || 5);
const OUT = args.out || '/tmp/nav-timing.json';
const SHOTS = args.shots ? path.resolve(ROOT, args.shots) : '';
const PASSES = (args.pass || 'static,smoke,timing').split(',');
const VIEWPORT = { width: 1280, height: 800 };
const JUMP_CLS = 0.05;
const ONLY = args.only ? new Set(args.only.split(',')) : null;
const want = (key) => !ONLY || ONLY.has(key);

/* ------------------------------------------------------------------ screens */

// First entry of each section is what the rail opens. done = first real row/card, not the skeleton.
const SECTIONS = [
  { id: 'team', views: [
    { id: 'roster-view', done: '#roster-view .gob-tbl tbody tr' },
    { id: 'player-stats-view', done: '#player-stats-view .gob-tbl tbody tr' },
    { id: 'team-attributes-view', done: '#team-attributes-view .gob-mrow' },
    { id: 'team-schedule-view', done: '#team-schedule-view tr[data-week]' },
    { id: 'practice-squad-view', done: '#practice-squad-view .gob-ps-tiers, #practice-squad-view .gob-ps-bracket, #practice-squad-view .gob-ps-empty' },
  ] },
  { id: 'prep', views: [
    { id: 'training-view', done: '#training-view .training-container .drill-group' },
    { id: 'game-plan-view', done: '#game-plan-view .resource-page-container .gpr' },
    { id: 'playbooks-view', done: '#playbooks-view .playbooks-main .play' },
    { id: 'scouting-view', done: '#scouting-view .opp-n' },
  ] },
  { id: 'league', views: [
    { id: 'standings-view', done: '#standings-view .gob-tbl tbody tr' },
    { id: 'rankings-view', done: '#rankings-view .leaders-table tbody tr' },
    { id: 'leaders-view', done: '#leaders-view .gob-ldb .ldb-r' },
    { id: 'team-stats-view', done: '#team-stats-view tbody tr' },
    { id: 'league-schedule-view', done: '#league-schedule-view tbody tr' },
    { id: 'tournament-view', done: '#tournament-view .gob-tour-status, #tournament-view .fcc-tb-mu', lock: true },
  ] },
  { id: 'news', views: [
    { id: 'news-view', done: '#news-view .gob-news-row, #news-view .gob-news-empty' },
    { id: 'awards-view', done: '#awards-view tbody tr, #awards-view .gob-news-empty, #awards-view .gob-awards-empty' },
  ] },
];

// .office-col .card ships in the HTML as .office-skel; the opponent name only comes from data.
const OFFICE_DONE = '#home-tab .office-col .nx-name';

const DRILLS = [
  { id: 'player-view', from: 'roster-view', section: 'team', click: '#roster-view a.gob-player', done: '#player-view .gob-hero-n' },
  { id: 'team-view', from: 'standings-view', section: 'league', click: '#standings-view a.gob-team', done: '#team-view .gob-hero-n' },
];

// A drill link that still points at a redirect stub reloads the document, so it is timed
// cross-document; an in-app link is timed in the page.
const STUB_LINK = /\/(team-roster-view|player-detail)\.html/;
async function isPageLink(page, click) {
  const href = await page.evaluate((c) => { const el = document.querySelector(c); return el ? el.getAttribute('href') || '' : ''; }, click);
  return STUB_LINK.test(href);
}

// Full pages the rail itself leaves for.
const RAIL_PAGES = [
  { id: 'recruiting.html', click: '.rail [data-gob-section="recruiting"]', done: '#hub-pool tbody tr.rec, #hub-weekly tbody tr, #hub-weekly .gob-tcard, #hub-board .gob-tcard' },
  { id: 'tutorial.html', click: '.rail a.rail-i.util[href="/tutorial.html"]', done: '.cats .tile' },
  { id: 'mode-select.html', click: '#gob-rail-exit', done: '.franchise-home-card, .franchise-empty-state' },
];

/* ------------------------------------------------------------------ helpers */

function median(xs) {
  const s = xs.slice().sort((a, b) => a - b);
  if (!s.length) return null;
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

function httpOk(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => { res.resume(); resolve(res.statusCode === 200); });
    req.on('error', () => resolve(false));
    req.setTimeout(2000, () => { req.destroy(); resolve(false); });
  });
}

async function startServer() {
  if (args.reuse) {
    if (!(await httpOk(`${BASE}/app-config`))) throw new Error(`--reuse but nothing answers on ${BASE}`);
    return null;
  }
  if (await httpOk(`${BASE}/app-config`)) throw new Error(`Port ${PORT} is in use; pick another or pass --reuse`);
  const sqlite = `/tmp/gob-nav-timing-${PORT}.sqlite`;
  for (const f of [sqlite, `${sqlite}-wal`, `${sqlite}-shm`]) fs.rmSync(f, { force: true });
  const env = { ...process.env, PORT: String(PORT), GOB_LOOPBACK_PORT: String(PORT), GOB_DESKTOP_E2E_SQLITE: sqlite };
  delete env.CI;
  const py = process.env.PYTHON_PATH || path.join(ROOT, '.venv', 'bin', 'python');
  const log = fs.openSync(`/tmp/gob-nav-timing-${PORT}.log`, 'w');
  const child = spawn(py, ['tests/e2e/helpers/seed_and_serve_desktop.py'], { cwd: ROOT, env, stdio: ['ignore', log, log] });
  for (let i = 0; i < 180; i += 1) {
    if (await httpOk(`${BASE}/app-config`)) return child;
    if (child.exitCode !== null) throw new Error(`server exited ${child.exitCode}; see /tmp/gob-nav-timing-${PORT}.log`);
    await sleep(1000);
  }
  child.kill('SIGTERM');
  throw new Error('server did not answer /app-config in 180s');
}

async function createFranchise(browser) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto(`${BASE}/mode-select.html`);
  const res = await page.request.post(`${BASE}/franchise/select-team`, { data: { team_name: 'Lancaster' } });
  if (!res.ok()) throw new Error(`select-team ${res.status()} ${await res.text()}`);
  const body = await res.json();
  await ctx.close();
  return { fid: body.franchise_id, tid: String(body.user_team_id || body.team_id || '') };
}

// The loopback user holds two franchises; remove only the one this script made.
async function deleteFranchise(browser, f) {
  const ctx = await browser.newContext();
  const res = await ctx.request.delete(`${BASE}/franchise/${encodeURIComponent(f.fid)}`);
  await ctx.close();
  if (!res.ok()) process.stderr.write(`delete ${f.fid}: ${res.status()}\n`);
}

// Runs at document start in every top-level document: arms page-to-page timing and records paint.
function navProbe() {
  if (window.top !== window) return;
  const white = (c) => !c || c === 'rgba(0, 0, 0, 0)' || c === 'transparent' || c === 'rgb(255, 255, 255)';
  const vis = (sel) => {
    const els = document.querySelectorAll(sel);
    for (const el of els) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight) {
        const cs = getComputedStyle(el);
        if (cs.visibility !== 'hidden' && cs.opacity !== '0' && (el.innerText || '').trim()) return true;
      }
    }
    return false;
  };
  window.__navVis = vis;
  let arm = null;
  try { arm = JSON.parse(sessionStorage.getItem('__navArm') || 'null'); } catch (e) { arm = null; }
  if (!arm) return;
  const origin = performance.timeOrigin;
  const rel = () => origin + performance.now() - arm.t0;
  const shifts = [];
  let fcp = null;
  try {
    const desc = (n) => { if (!n || !n.tagName) return '?'; const c = typeof n.className === 'string' && n.className.trim() ? '.' + n.className.trim().split(/\s+/).slice(0, 2).join('.') : ''; return n.tagName.toLowerCase() + (n.id ? '#' + n.id : '') + c; };
    new PerformanceObserver((l) => l.getEntries().forEach((e) => shifts.push({ at: origin + e.startTime - arm.t0, v: e.value, src: (e.sources || []).map((x) => desc(x.node)) }))).observe({ type: 'layout-shift', buffered: true });
    new PerformanceObserver((l) => l.getEntries().forEach((e) => { if (e.name === 'first-contentful-paint') fcp = origin + e.startTime - arm.t0; })).observe({ type: 'paint', buffered: true });
  } catch (e) { /* older engines */ }
  let whiteAfterPaint = 0;
  let skelAt = null;
  let blankFrames = 0;
  let blankAt = null;
  let doneAt = null;
  const tick = () => {
    const t = rel();
    const body = document.body;
    if (fcp !== null && doneAt === null && body) {
      const bgH = getComputedStyle(document.documentElement).backgroundColor;
      const bgB = getComputedStyle(body).backgroundColor;
      if (white(bgH) && white(bgB)) whiteAfterPaint += 1;
      if (skelAt === null && vis('.gob-view-skel, .spinner, .loading-spinner, .skeleton, [class*="skel"]')) skelAt = t;
      else if (skelAt === null && !(body.innerText || '').trim()) { blankFrames += 1; if (blankAt === null) blankAt = t; }
    }
    if (doneAt === null && vis(arm.done)) doneAt = t;
    if (doneAt !== null && t > doneAt + 500) {
      const inWin = shifts.filter((s) => s.at <= doneAt + 500).sort((a, b) => b.v - a.v);
      window.__navResult = {
        ms: doneAt, fcp, skelAt, blankFrames, blankAt, whiteAfterPaint,
        cls: inWin.reduce((a, s) => a + s.v, 0),
        bigShiftAt: inWin.length && inWin[0].v > 0 ? inWin[0].at : null,
        shiftSrc: inWin.slice(0, 3).map((s) => `${s.v.toFixed(3)} ${s.src.join(' + ')}`),
        landed: location.pathname + location.search,
      };
      sessionStorage.removeItem('__navArm');
      return;
    }
    if (t > arm.limit) {
      window.__navResult = { timeout: true, fcp, landed: location.pathname + location.search, shown: (document.body && document.body.innerText || '').replace(/\s+/g, ' ').slice(0, 240) };
      sessionStorage.removeItem('__navArm');
      return;
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function hideDesktopCookie() {
  const d = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie');
  Object.defineProperty(Document.prototype, 'cookie', {
    configurable: true,
    get() { return d.get.call(this).split(/;\s*/).filter((c) => c && !c.startsWith('GOB_BUILD_PROFILE=')).join('; '); },
    set(v) { d.set.call(this, v); },
  });
}

async function newProfileContext(browser, profile) {
  const ctx = await browser.newContext({ viewport: VIEWPORT });
  if (profile === 'desktop') {
    await ctx.addInitScript((port) => { window.GOB_BUILD_PROFILE = 'desktop'; window.GOB_LOOPBACK_PORT = Number(port); }, PORT);
  } else {
    await ctx.addInitScript(hideDesktopCookie);
    process.env.BASE_URL = BASE;
    await stubAuth(ctx);
  }
  await ctx.addInitScript(navProbe);
  return ctx;
}

function fccUrl(f, extra) {
  const q = new URLSearchParams({ franchise_id: f.fid });
  if (f.tid) { q.set('team_id', f.tid); q.set('user_team_id', f.tid); }
  q.set('tab', 'home-tab');
  Object.entries(extra || {}).forEach(([k, v]) => q.set(k, v));
  return `${BASE}/franchise-command-center.html?${q}`;
}

// Same-document: click and poll every frame until done is visible.
async function timeInPage(page, click, done, panel) {
  return page.evaluate(({ click, done, panel, jump }) => new Promise((resolve) => {
    const el = document.querySelector(click);
    if (!el) { resolve({ error: 'no click target ' + click }); return; }
    const vis = window.__navVis;
    const shifts = [];
    const desc = (n) => { if (!n || !n.tagName) return '?'; const c = typeof n.className === 'string' && n.className.trim() ? '.' + n.className.trim().split(/\s+/).slice(0, 2).join('.') : ''; return n.tagName.toLowerCase() + (n.id ? '#' + n.id : '') + c; };
    const po = new PerformanceObserver((l) => l.getEntries().forEach((e) => shifts.push({ at: e.startTime, v: e.value, src: (e.sources || []).map((x) => desc(x.node)) })));
    po.observe({ type: 'layout-shift', buffered: false });
    const t0 = performance.now();
    const epoch0 = performance.timeOrigin + t0;
    let skelAt = null;
    let blankFrames = 0;
    let blankAt = null;
    let doneAt = null;
    el.click();
    const tick = () => {
      const t = performance.now() - t0;
      if (doneAt === null) {
        const p = panel ? document.getElementById(panel) : null;
        if (p) {
          if (skelAt === null && p.querySelector('.gob-view-skel, .spinner, .loading-spinner')) skelAt = t;
          const r = p.getBoundingClientRect();
          if (r.height > 0 && !(p.innerText || '').trim() && !p.querySelector('.gob-view-skel')) { blankFrames += 1; if (blankAt === null) blankAt = t; }
        }
        if (vis(done)) doneAt = t;
      }
      if (doneAt !== null && t > doneAt + 500) {
        po.disconnect();
        const inWin = shifts.filter((s) => s.at - t0 <= doneAt + 500 && s.at >= t0).sort((a, b) => b.v - a.v);
        resolve({
          ms: doneAt, skelAt, blankFrames, blankAt, epoch0,
          cls: inWin.reduce((a, s) => a + s.v, 0),
          bigShiftAt: inWin.length && inWin[0].v > 0 ? inWin[0].at - t0 : null,
          shiftSrc: inWin.slice(0, 3).map((s) => `${s.v.toFixed(3)} ${s.src.join(' + ')}`),
          landed: location.pathname + location.search,
        });
        return;
      }
      if (t > 15000) {
        po.disconnect();
        const p = panel ? document.getElementById(panel) : null;
        resolve({ timeout: true, landed: location.pathname + location.search, shown: p ? (p.innerText || '').replace(/\s+/g, ' ').slice(0, 240) + ' | ' + p.innerHTML.slice(0, 200) : '' });
        return;
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }), { click, done, panel, jump: JUMP_CLS });
}

async function readNavResult(page, limitMs) {
  const end = Date.now() + limitMs + 5000;
  while (Date.now() < end) {
    try {
      const r = await page.evaluate(() => window.__navResult || null);
      if (r) return r;
    } catch (e) { /* navigating */ }
    await sleep(40);
  }
  return { timeout: true, landed: page.url() };
}

// Cross-document: arm sessionStorage, click, then read the result the next document wrote.
async function timeToPage(page, click, done) {
  const limit = 20000;
  const armed = await page.evaluate(({ click, done, limit }) => {
    const el = document.querySelector(click);
    if (!el) return 'no click target ' + click;
    const t0 = performance.timeOrigin + performance.now();
    sessionStorage.setItem('__navArm', JSON.stringify({ done, t0, limit }));
    window.__navResult = null;
    setTimeout(() => el.click(), 0);
    return t0;
  }, { click, done, limit });
  if (typeof armed === 'string') return { error: armed };
  const r = await readNavResult(page, limit);
  return Object.assign({ epoch0: armed }, r);
}

// First open of the app in a fresh context: from leaving a blank same-origin page to Office painted.
async function loadFcc(page, f) {
  await page.goto(`${BASE}/app-config`);
  const t0 = await page.evaluate(({ done, url }) => {
    const t = performance.timeOrigin + performance.now();
    sessionStorage.setItem('__navArm', JSON.stringify({ done, t0: t, limit: 30000 }));
    setTimeout(() => { location.href = url; }, 0);
    return t;
  }, { done: OFFICE_DONE, url: fccUrl(f) });
  const r = await readNavResult(page, 30000);
  return Object.assign({ epoch0: t0 }, r);
}

async function waitVisible(page, sel, timeout) {
  await page.waitForFunction((s) => window.__navVis && window.__navVis(s), sel, { timeout: timeout || 20000, polling: 'raf' });
}

async function railTo(page, section, firstDone) {
  await page.evaluate((s) => document.querySelector(`.rail [data-gob-section="${s}"]`).click(), section);
  await waitVisible(page, firstDone);
}

/* ------------------------------------------------------------------ screencast */

async function withScreencast(page, key, fn) {
  if (!SHOTS) return fn();
  const cdp = await page.context().newCDPSession(page);
  const frames = [];
  cdp.on('Page.screencastFrame', (f) => {
    frames.push({ data: f.data, ts: f.metadata.timestamp * 1000 });
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
  });
  await cdp.send('Page.startScreencast', { format: 'png', maxWidth: VIEWPORT.width, maxHeight: VIEWPORT.height, everyNthFrame: 1 });
  const r = await fn();
  await sleep(300);
  await cdp.send('Page.stopScreencast').catch(() => {});
  await cdp.detach().catch(() => {});
  if (r && r.epoch0 && frames.length) {
    const marks = [];
    if (r.skelAt !== null && r.skelAt !== undefined) marks.push(['skeleton', r.skelAt + 16]);
    if (r.bigShiftAt !== null && r.bigShiftAt !== undefined) marks.push(['shift', r.bigShiftAt + 16]);
    if (r.blankAt !== null && r.blankAt !== undefined) marks.push(['blank', r.blankAt + 16]);
    marks.push(['painted', r.ms + 16]);
    fs.mkdirSync(SHOTS, { recursive: true });
    r.shots = [];
    for (const [label, at] of marks) {
      const want = r.epoch0 + at;
      let best = frames[0];
      for (const fr of frames) if (Math.abs(fr.ts - want) < Math.abs(best.ts - want)) best = fr;
      const file = path.join(SHOTS, `${key}-${label}.png`);
      fs.writeFileSync(file, Buffer.from(best.data, 'base64'));
      r.shots.push(`${path.relative(ROOT, file)} (target ${Math.round(at)} ms, frame ${Math.round(best.ts - r.epoch0)} ms)`);
    }
  }
  return r;
}

/* ------------------------------------------------------------------ passes */

function lineOf(src, idx) { return src.slice(0, idx).split('\n').length; }

function walk(dir, out) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (['vendor', 'node_modules', 'images', 'sounds', 'fonts', 'music'].includes(e.name)) continue;
      walk(p, out);
    } else if (/\.(html|js|mjs)$/.test(e.name)) out.push(p);
  }
  return out;
}

function passStatic() {
  const pages = fs.readdirSync(STATIC).filter((n) => n.endsWith('.html')).sort();
  const sources = walk(STATIC, []).map((p) => ({ p, src: fs.readFileSync(p, 'utf8') }));
  const specs = fs.readdirSync(SPECS).filter((n) => n.endsWith('.spec.js')).map((n) => ({ n, src: fs.readFileSync(path.join(SPECS, n), 'utf8') }));
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const out = {};
  for (const name of pages) {
    const src = fs.readFileSync(path.join(STATIC, name), 'utf8');
    const tag = (src.match(/<html[^>]*>/i) || [''])[0];
    const head = src.slice(0, 2500);
    const rep = head.match(/location\.replace\(\s*['"]([^'"?]+)/);
    const tab = head.match(/set\(\s*['"]tab['"]\s*,\s*['"]([^'"]+)['"]/);
    const re = new RegExp(`(^|[^A-Za-z0-9_-])${esc(name)}`, 'g');
    const inbound = [];
    for (const s of sources) {
      if (path.basename(s.p) === name) continue;
      let m;
      re.lastIndex = 0;
      while ((m = re.exec(s.src))) inbound.push(`${path.relative(ROOT, s.p)}:${lineOf(s.src, m.index)}`);
    }
    const specHits = specs.filter((s) => { re.lastIndex = 0; return re.test(s.src); }).map((s) => s.n);
    out[name] = {
      gobClass: /class="[^"]*\bgob\b/.test(tag),
      htmlTag: tag,
      tokens: src.includes('/css/gob-tokens.css'),
      shell: src.includes('gobShell.js'),
      redirectTo: rep ? rep[1] : '',
      redirectTab: tab ? tab[1] : '',
      embedGuard: /get\(\s*['"]embed['"]\s*\)\s*===\s*['"]1['"]/.test(head),
      inbound,
      specs: specHits,
    };
  }
  const viewIds = SECTIONS.flatMap((s) => s.views.map((v) => v.id)).concat(['home-tab', 'player-view', 'team-view', 'training-report-view']);
  const viewSpecs = {};
  for (const id of viewIds) {
    const re = new RegExp(`['"#\`]${esc(id)}\\b`);
    viewSpecs[id] = specs.filter((s) => re.test(s.src)).map((s) => s.n);
  }
  return { pages: out, viewSpecs };
}

async function passProbe(browser) {
  const f = await createFranchise(browser);
  const ctx = await newProfileContext(browser, 'desktop');
  const page = await ctx.newPage();
  await page.goto(fccUrl(f));
  await page.waitForLoadState('networkidle').catch(() => {});
  await sleep(2500);
  const dump = (id) => page.evaluate((id) => {
    const h = id ? document.getElementById(id) : document.body;
    if (!h) return { missing: true };
    const cls = [...new Set([...h.querySelectorAll('[class]')].filter((e) => e.getBoundingClientRect().height > 0).map((e) => String(e.className).split(' ')[0]))].slice(0, 40);
    return { skel: !!h.querySelector('.gob-view-skel'), err: !!h.querySelector('.gob-view-error'), rows: h.querySelectorAll('tbody tr').length, cls, text: (h.innerText || '').slice(0, 200).replace(/\s+/g, ' '), url: location.pathname + location.search };
  }, id);
  const out = { office: await dump('home-tab') };
  for (const s of SECTIONS) {
    await page.evaluate((sid) => document.querySelector(`.rail [data-gob-section="${sid}"]`).click(), s.id);
    await sleep(600);
    for (const v of s.views) {
      await page.evaluate((id) => { const b = document.querySelector(`#gob-subtabs .tb[data-key="${id}"]`); if (b) b.click(); }, v.id);
      await page.waitForLoadState('networkidle').catch(() => {});
      await sleep(2500);
      out[v.id] = await dump(v.id);
    }
  }
  for (const p of RAIL_PAGES) {
    await page.goto(fccUrl(f));
    await sleep(2500);
    await page.evaluate((c) => { const el = document.querySelector(c); if (el) el.click(); }, p.click);
    await page.waitForLoadState('networkidle').catch(() => {});
    await sleep(3000);
    out[p.id] = await dump('');
  }
  await ctx.close();
  out.nav = {};
  for (const profile of ['desktop', 'online']) {
    out.nav[profile] = await navChecks(browser, f, profile);
    console.log('nav', profile, JSON.stringify(out.nav[profile]));
  }
  await deleteFranchise(browser, f);
  return out;
}

// Rail buttons from a drill-in, and browser Back after each kind of move, in one profile.
async function navChecks(browser, f, profile) {
  const ctx = await newProfileContext(browser, profile);
  const page = await ctx.newPage();
  // From a drill-in, does each rail section button still leave it?
  const out = { railFromDetail: {} };
  for (const d of DRILLS) {
    const sec = SECTIONS.find((s) => s.id === d.section);
    for (const target of ['office', 'team', 'league']) {
      try {
        await page.goto(fccUrl(f));
        await waitVisible(page, OFFICE_DONE, 30000);
        await railTo(page, d.section, sec.views[0].done);
        await page.evaluate((id) => { const b = document.querySelector(`#gob-subtabs .tb[data-key="${id}"]`); if (b) b.click(); }, d.from);
        await waitVisible(page, sec.views.find((v) => v.id === d.from).done);
        const reloads = await isPageLink(page, d.click);
        const click = page.evaluate((c) => document.querySelector(c).click(), d.click);
        if (reloads) await Promise.all([page.waitForNavigation({ url: new RegExp('tab=' + d.id) }), click]);
        else await click;
        await waitVisible(page, d.done, 15000);
        await page.evaluate((t) => document.querySelector(`.rail [data-gob-section="${t}"]`).click(), target);
        await sleep(1500);
        out.railFromDetail[`${d.id} -> ${target}`] = await page.evaluate(() => new URLSearchParams(location.search).get('tab'));
      } catch (err) {
        out.railFromDetail[`${d.id} -> ${target}`] = 'error: ' + String(err.message || err).split('\n')[0];
      }
    }
  }
  // Browser Back after each kind of move. Start: Office, then Team (rail push) so there is history.
  const where = () => page.evaluate(() => location.pathname.replace('/franchise-command-center.html', 'fcc') + ':' + (new URLSearchParams(location.search).get('tab') || ''));
  const moves = [
    ['rail push office->team', async () => { await railTo(page, 'team', SECTIONS[0].views[0].done); }],
    ['subtab replace roster->player-stats', async () => {
      await railTo(page, 'team', SECTIONS[0].views[0].done);
      await page.evaluate(() => document.querySelector('#gob-subtabs .tb[data-key="player-stats-view"]').click());
      await waitVisible(page, SECTIONS[0].views[1].done);
    }],
    ['drill roster->player-view', async () => {
      await railTo(page, 'team', SECTIONS[0].views[0].done);
      await page.evaluate(() => document.querySelector('#roster-view a.gob-player').click());
      await sleep(1500);
    }],
    ['drill standings->team-view', async () => {
      await railTo(page, 'league', SECTIONS[2].views[0].done);
      await page.evaluate(() => document.querySelector('#standings-view a.gob-team').click());
      await waitVisible(page, DRILLS[1].done, 15000);
      await sleep(1000);
    }],
  ].concat(RAIL_PAGES.map((p) => [`rail ${p.id}`, async () => {
    await Promise.all([page.waitForNavigation().catch(() => {}), page.evaluate((c) => document.querySelector(c).click(), p.click)]);
    await sleep(2000);
  }]));
  out.back = {};
  for (const [label, move] of moves) {
    try {
      await page.goto(fccUrl(f));
      await waitVisible(page, OFFICE_DONE, 30000);
      await move();
      const at = await where();
      await page.goBack({ timeout: 10000 }).catch(() => {});
      await sleep(2000);
      out.back[label] = { at, afterBack: await where() };
    } catch (err) {
      out.back[label] = { error: String(err.message || err).split('\n')[0] };
    }
  }
  await ctx.close();
  return out;
}

async function passSmoke(browser, pages) {
  const f = await createFranchise(browser);
  const res = {};
  for (const profile of ['desktop', 'online']) {
    const ctx = await newProfileContext(browser, profile);
    let remote = [];
    // Smoke only: keep runs off the network and count what a page tried to fetch remotely.
    await ctx.route((u) => !['127.0.0.1', 'localhost'].includes(u.hostname), (route) => {
      remote.push(new URL(route.request().url()).hostname);
      return route.abort();
    });
    res[profile] = {};
    for (const name of pages) {
      const page = await ctx.newPage();
      const errors = [];
      const failed = [];
      remote = [];
      page.on('pageerror', (e) => errors.push(String(e.message || e).slice(0, 160)));
      page.on('response', (r) => {
        const t = r.request().resourceType();
        if ((t === 'fetch' || t === 'xhr') && r.status() >= 400) failed.push(`${r.status()} ${new URL(r.url()).pathname}`);
      });
      const q = new URLSearchParams({ franchise_id: f.fid, mode: 'franchise' });
      if (f.tid) { q.set('team_id', f.tid); q.set('user_team_id', f.tid); }
      let status = 0;
      try {
        const r = await page.goto(`${BASE}/${encodeURIComponent(name)}?${q}`, { timeout: 20000 });
        status = r ? r.status() : 0;
        await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
        await sleep(600);
      } catch (e) { errors.push('goto: ' + String(e.message).slice(0, 120)); }
      let facts = {};
      try {
        facts = await page.evaluate(() => ({
          landed: location.pathname,
          tab: new URLSearchParams(location.search).get('tab') || '',
          htmlClass: document.documentElement.className,
          tokens: [...document.styleSheets].some((sh) => (sh.href || '').includes('/css/gob-tokens.css')),
          text: (document.body && document.body.innerText || '').trim().length,
          viewError: !!document.querySelector('.gob-view-error'),
          feedbackHidden: (() => { const b = document.getElementById('gob-rail-feedback'); return b ? b.hidden : null; })(),
          // The attribute alone can disagree with what is painted (.rail-i sets display).
          feedbackPainted: (() => { const b = document.getElementById('gob-rail-feedback'); return b ? getComputedStyle(b).display !== 'none' && b.getBoundingClientRect().height > 0 : null; })(),
        }));
      } catch (e) { facts = { landed: page.url(), evalError: true }; }
      res[profile][name] = Object.assign({ status, errors: [...new Set(errors)].slice(0, 5), failed: [...new Set(failed)].slice(0, 8), remote: [...new Set(remote)] }, facts);
      await page.close();
    }
    await ctx.close();
  }
  await deleteFranchise(browser, f);
  return res;
}

function summarize(r) {
  const flags = [];
  if (r.skelAt !== null && r.skelAt !== undefined) flags.push('skeleton');
  if (r.blankFrames > 1) flags.push('blank');
  if (r.whiteAfterPaint > 0) flags.push('white');
  if (r.cls >= JUMP_CLS) flags.push('jump');
  return flags;
}

async function timingSequence(browser, profile, capture) {
  const f = await createFranchise(browser);
  const ctx = await newProfileContext(browser, profile);
  const page = await ctx.newPage();
  const rec = {};
  const put = (key, phase, r) => {
    rec[key] = rec[key] || {};
    rec[key][phase] = Object.assign({ flags: r.ms !== undefined ? summarize(r) : [] }, r);
  };
  const shot = (key, phase, fn) => (capture && capture.has(`${key}:${phase}`) ? withScreencast(page, `${profile}-${key}-${phase}`, fn) : fn());

  put('franchise-command-center.html', 'cold', await shot('franchise-command-center.html', 'cold', () => loadFcc(page, f)));
  await waitVisible(page, OFFICE_DONE, 30000);

  const officeClick = '.rail [data-gob-section="office"]';
  const recover = async (key, phase, err) => {
    put(key, phase, { error: String(err.message || err).split('\n')[0] });
    await page.goto(fccUrl(f));
    await waitVisible(page, OFFICE_DONE, 30000);
  };
  for (const s of SECTIONS) {
    if (!s.views.some((v) => want(v.id))) continue;
    const first = s.views[0];
    const railClick = `.rail [data-gob-section="${s.id}"]`;
    // First tab of a section: the rail opens it. Time from Office, cold then warm.
    for (const phase of ['cold', 'warm']) {
      try {
        await railTo(page, 'office', OFFICE_DONE);
        put(first.id, phase, await shot(first.id, phase, () => timeInPage(page, railClick, first.done, first.id)));
      } catch (err) { await recover(first.id, phase, err); }
    }
    for (const v of s.views.slice(1)) {
      if (!want(v.id)) continue;
      const sub = `#gob-subtabs .tb[data-key="${v.id}"]`;
      for (const phase of ['cold', 'warm']) {
        try {
          const cur = await page.evaluate(() => new URLSearchParams(location.search).get('tab') || '');
          if (!s.views.some((x) => x.id === cur)) await railTo(page, s.id, first.done);
          await page.evaluate((sel) => { const b = document.querySelector(sel); if (b && b.getAttribute('aria-selected') !== 'true') b.click(); }, `#gob-subtabs .tb[data-key="${first.id}"]`);
          await waitVisible(page, first.done);
          const locked = await page.evaluate((sel) => { const b = document.querySelector(sel); return !b ? 'missing' : (b.classList.contains('is-locked') || b.getAttribute('aria-disabled') === 'true' ? 'locked' : ''); }, sub);
          if (locked) { put(v.id, phase, { skipped: locked }); continue; }
          put(v.id, phase, await shot(v.id, phase, () => timeInPage(page, sub, v.done, v.id)));
        } catch (err) { await recover(v.id, phase, err); }
      }
    }
  }
  if (want('training-report-view')) {
    const reportDone = '#training-report-view .training-notes-brief, #training-report-view .notes-placeholder';
    for (const phase of ['cold', 'warm']) {
      try {
        await railTo(page, 'office', OFFICE_DONE);
        const href = fccUrl(f, {
          tab: 'training-report-view', week: '1', from: 'office', origin: 'office', mode: 'franchise',
        });
        await page.evaluate((url) => {
          let a = document.getElementById('__time-training-report');
          if (!a) {
            a = document.createElement('a');
            a.id = '__time-training-report';
            document.body.appendChild(a);
          }
          a.href = url;
        }, href);
        put('training-report-view', phase, await shot('training-report-view', phase, () => (
          timeInPage(page, '#__time-training-report', reportDone, 'training-report-view')
        )));
      } catch (err) { await recover('training-report-view', phase, err); }
    }
  }
  if (want('home-tab')) try {
    await railTo(page, 'team', SECTIONS[0].views[0].done);
    put('home-tab', 'warm', await shot('home-tab', 'warm', () => timeInPage(page, officeClick, OFFICE_DONE, 'home-tab')));
  } catch (err) { await recover('home-tab', 'warm', err); }
  for (const d of DRILLS) {
    if (!want(d.id)) continue;
    const sec = SECTIONS.find((s) => s.id === d.section);
    const fromDone = sec.views.find((v) => v.id === d.from).done;
    for (const phase of ['cold', 'warm']) {
      try {
        if (phase === 'cold') {
          await page.goto(fccUrl(f));
          await waitVisible(page, OFFICE_DONE, 30000);
          await railTo(page, d.section, sec.views[0].done);
        }
        if (phase === 'warm' || sec.views[0].id !== d.from) {
          await page.evaluate((id) => document.querySelector(`#gob-subtabs .tb[data-key="${id}"]`).click(), d.from);
        }
        await waitVisible(page, fromDone);
        const reloads = await isPageLink(page, d.click);
        const r = await shot(d.id, phase, () => (reloads ? timeToPage(page, d.click, d.done) : timeInPage(page, d.click, d.done, d.id)));
        put(d.id, phase, Object.assign({ mode: reloads ? 'page' : 'in-app' }, r));
      } catch (err) {
        put(d.id, phase, { error: String(err.message || err).split('\n')[0] });
        await page.goto(fccUrl(f));
        await waitVisible(page, OFFICE_DONE, 30000);
      }
    }
  }

  for (const p of RAIL_PAGES) {
    if (!want(p.id)) continue;
    for (const phase of ['cold', 'warm']) {
      try {
        await page.goto(fccUrl(f));
        await waitVisible(page, OFFICE_DONE, 30000);
        put(p.id, phase, await shot(p.id, phase, () => timeToPage(page, p.click, p.done)));
      } catch (err) {
        put(p.id, phase, { error: String(err.message || err).split('\n')[0] });
      }
    }
  }
  await ctx.close();
  await deleteFranchise(browser, f);
  return rec;
}

async function passTiming(browser) {
  const out = { desktop: [], online: [] };
  for (const profile of ['desktop', 'online']) {
    for (let i = 0; i < RUNS; i += 1) {
      out[profile].push(await timingSequence(browser, profile, null));
      process.stderr.write(`timing ${profile} run ${i + 1}/${RUNS}\n`);
    }
  }
  const table = {};
  const capture = { desktop: new Set(), online: new Set() };
  for (const profile of Object.keys(out)) {
    for (const run of out[profile]) {
      for (const [key, phases] of Object.entries(run)) {
        for (const [phase, r] of Object.entries(phases)) {
          const row = ((table[key] = table[key] || {})[profile] = table[key][profile] || {});
          const cell = (row[phase] = row[phase] || { ms: [], flags: {}, skipped: '', timeouts: 0, errors: [] });
          if (r.skipped) cell.skipped = r.skipped;
          else if (r.timeout) { cell.timeouts += 1; cell.shown = r.shown; cell.landed = r.landed; }
          else if (r.error) cell.errors.push(r.error);
          else {
            cell.ms.push(Math.round(r.ms));
            for (const fl of r.flags) cell.flags[fl] = (cell.flags[fl] || 0) + 1;
            if (r.skelAt !== null && r.skelAt !== undefined) cell.skelMs = (cell.skelMs || []).concat(Math.round(r.ms - r.skelAt));
            cell.cls = Math.max(cell.cls || 0, Number(r.cls || 0));
            if (r.cls >= JUMP_CLS && r.shiftSrc) cell.shiftSrc = r.shiftSrc;
            if (r.blankFrames > 1) cell.blankFrames = Math.max(cell.blankFrames || 0, r.blankFrames);
            cell.landed = r.landed;
          }
        }
      }
    }
  }
  for (const [key, profs] of Object.entries(table)) {
    for (const [profile, phases] of Object.entries(profs)) {
      for (const [phase, c] of Object.entries(phases)) {
        c.median = median(c.ms);
        c.worst = c.ms.length ? Math.max(...c.ms) : null;
        if (c.skelMs) c.skelMedian = median(c.skelMs);
        if (['blank', 'white', 'jump'].some((fl) => (c.flags[fl] || 0) >= Math.ceil(RUNS / 2))) capture[profile].add(`${key}:${phase}`);
      }
    }
  }
  const shots = {};
  if (SHOTS) {
    for (const profile of Object.keys(capture)) {
      if (!capture[profile].size) continue;
      const rec = await timingSequence(browser, profile, capture[profile]);
      for (const [key, phases] of Object.entries(rec)) {
        for (const [phase, r] of Object.entries(phases)) if (r.shots) shots[`${profile}:${key}:${phase}`] = r.shots;
      }
    }
  }
  return { table, shots, runs: RUNS };
}

function printTiming(t) {
  const rows = [];
  for (const [key, profs] of Object.entries(t.table)) {
    for (const [profile, phases] of Object.entries(profs)) {
      const c = phases.cold || {};
      const w = phases.warm || {};
      const fl = (x) => Object.entries(x.flags || {}).map(([k, n]) => `${k}${n}`).join(' ');
      rows.push([key, profile, c.skipped || `${c.median ?? '-'}/${c.worst ?? '-'}`, w.skipped || `${w.median ?? '-'}/${w.worst ?? '-'}`, `${fl(c)} | ${fl(w)}`, (c.timeouts || 0) + (w.timeouts || 0)].join('\t'));
    }
  }
  console.log(['screen', 'profile', 'cold med/worst', 'warm med/worst', 'flags cold | warm', 'timeouts'].join('\t'));
  rows.forEach((r) => console.log(r));
}

async function main() {
  const started = Date.now();
  const result = { meta: { port: PORT, runs: RUNS, passes: PASSES, viewport: VIEWPORT, startedAt: new Date(started).toISOString() } };
  if (PASSES.includes('static')) result.static = passStatic();
  const needsServer = PASSES.some((p) => ['probe', 'smoke', 'timing'].includes(p));
  const server = needsServer ? await startServer() : null;
  let browser = null;
  try {
    if (needsServer) browser = await chromium.launch();
    if (PASSES.includes('probe')) {
      result.probe = await passProbe(browser);
      console.log(JSON.stringify(result.probe, null, 1));
    }
    if (PASSES.includes('smoke')) {
      const pages = fs.readdirSync(STATIC).filter((n) => n.endsWith('.html')).sort();
      result.smoke = await passSmoke(browser, pages);
    }
    if (PASSES.includes('timing')) {
      result.timing = await passTiming(browser);
      printTiming(result.timing);
    }
  } catch (err) {
    result.error = String(err.stack || err);
    throw err;
  } finally {
    fs.writeFileSync(OUT, JSON.stringify(result, null, 1));
    if (browser) await browser.close();
    if (server) {
      server.kill('SIGTERM');
      await sleep(1500);
      if (server.exitCode === null) server.kill('SIGKILL');
    }
  }
  result.meta.seconds = Math.round((Date.now() - started) / 1000);
  fs.writeFileSync(OUT, JSON.stringify(result, null, 1));
  console.log(`wrote ${OUT} in ${result.meta.seconds}s`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
