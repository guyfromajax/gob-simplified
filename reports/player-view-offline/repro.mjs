/**
 * One-off desktop/loopback reproduction. Not a product test.
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BASE = 'http://127.0.0.1:8777';
const OUT = __dirname;

function ensureDir() {
  fs.mkdirSync(OUT, { recursive: true });
}

async function waitReady(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  }, { timeout: 30000 });
}

async function main() {
  ensureDir();
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  });
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  await context.addInitScript(() => {
    window.GOB_BUILD_PROFILE = 'desktop';
    window.GOB_LOOPBACK_PORT = 8777;
  });
  const page = await context.newPage();
  const consoleLines = [];
  const failed = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      consoleLines.push(`[${msg.type()}] ${msg.text()}`);
    }
  });
  page.on('requestfailed', (req) => {
    failed.push(`${req.method()} ${req.url()} ${req.failure()?.errorText || ''}`);
  });
  page.on('response', async (res) => {
    const url = res.url();
    if (url.includes('player-detail') || url.includes('/player/')) {
      consoleLines.push(`[http ${res.status()}] ${url}`);
    }
  });

  const create = await page.request.post(BASE + '/franchise/select-team', {
    data: { team_name: 'Lancaster' },
  });
  const created = await create.json();
  const fid = created.franchise_id;
  const ccRes = await page.request.get(`${BASE}/franchise/command-center/data?franchise_id=${fid}`);
  const cc = await ccRes.json();
  const tid = cc.team_id || cc.user_team_id || created.user_team_id || created.team_id;
  const note = { fid, tid, createStatus: create.status(), created, cc };
  fs.writeFileSync(path.join(OUT, 'create.json'), JSON.stringify(note, null, 2));

  const rosterRes = await page.request.get(`${BASE}/roster/Lancaster?franchise_id=${fid}&profile=1`);
  const roster = await rosterRes.json();
  const first = (roster.players || [])[0] || {};
  const pid = first._id || first.player_id || first.id;
  fs.writeFileSync(path.join(OUT, 'roster-first.json'), JSON.stringify({
    status: rosterRes.status(),
    playerCount: (roster.players || []).length,
    firstKeys: Object.keys(first),
    pid,
    name: first.name,
  }, null, 2));

  const detailRes = await page.request.get(
    `${BASE}/franchise/player-detail?franchise_id=${fid}&player_id=${encodeURIComponent(pid || '')}`
  );
  let detailBody = null;
  try { detailBody = await detailRes.json(); } catch (e) { detailBody = await detailRes.text(); }
  fs.writeFileSync(path.join(OUT, 'api-player-detail.json'), JSON.stringify({
    status: detailRes.status(),
    body: detailBody,
  }, null, 2));

  const fcc = `${BASE}/franchise-command-center.html?franchise_id=${fid}&team_id=${tid}&tab=roster-view`;
  await page.goto(fcc);
  await waitReady(page);
  try {
    await page.waitForSelector('#roster-view a.gob-player', { timeout: 20000 });
  } catch (err) {
    const dump = await page.evaluate(() => ({
      url: location.href,
      search: location.search,
      ctx: window.FranchiseContext ? window.FranchiseContext.getAll() : null,
      rosterText: (document.querySelector('#roster-view')?.innerText || '').slice(0, 800),
      errors: [...document.querySelectorAll('.gob-view-error')].map((el) => el.textContent),
    }));
    fs.writeFileSync(path.join(OUT, 'roster-missing.json'), JSON.stringify(dump, null, 2));
    await page.screenshot({ path: path.join(OUT, 'offline-roster-missing-1280.png') });
    throw err;
  }

  const href = await page.locator('#roster-view a.gob-player').first().getAttribute('href');
  const beforeClick = await page.evaluate(() => ({
    search: location.search,
    ctx: window.FranchiseContext ? window.FranchiseContext.getAll() : null,
    profile: window.GOB_BUILD_PROFILE,
    provider: window.FranchiseContext && window.FranchiseContext._provider
      ? window.FranchiseContext._provider.constructor.name
      : null,
  }));

  await page.locator('#roster-view a.gob-player').first().evaluate((a) => a.click());
  await page.waitForTimeout(1500);

  const afterClick = await page.evaluate(() => ({
    search: location.search,
    tab: new URLSearchParams(location.search).get('tab'),
    player_id: new URLSearchParams(location.search).get('player_id'),
    ctx: window.FranchiseContext ? window.FranchiseContext.getAll() : null,
    hero: document.querySelector('#player-view .gob-hero-n')?.textContent || '',
    error: document.querySelector('#player-view .gob-view-error')?.textContent || '',
    htmlSnippet: (document.querySelector('#player-view')?.innerText || '').slice(0, 400),
  }));

  await page.screenshot({ path: path.join(OUT, 'offline-before-1280.png'), fullPage: false });

  fs.writeFileSync(path.join(OUT, 'roster-click.json'), JSON.stringify({
    href,
    beforeClick,
    afterClick,
    consoleLines,
    failed,
  }, null, 2));

  // Leaders path
  await page.goto(`${BASE}/franchise-command-center.html?franchise_id=${fid}&team_id=${tid}&tab=leaders-view`);
  await waitReady(page);
  const leadersReady = await page.locator('#leaders-view a.gob-player').count().catch(() => 0);
  let leadersAfter = { skip: 'no player links' };
  if (leadersReady > 0) {
    await page.locator('#leaders-view a.gob-player').first().evaluate((a) => a.click());
    await page.waitForTimeout(1500);
    leadersAfter = await page.evaluate(() => ({
      search: location.search,
      player_id: new URLSearchParams(location.search).get('player_id'),
      ctxPlayer: window.FranchiseContext ? window.FranchiseContext.get('player_id') : null,
      hero: document.querySelector('#player-view .gob-hero-n')?.textContent || '',
      error: document.querySelector('#player-view .gob-view-error')?.textContent || '',
    }));
    await page.screenshot({ path: path.join(OUT, 'offline-leaders-before-1280.png'), fullPage: false });
  } else {
    leadersAfter = {
      skip: 'no player links',
      text: await page.locator('#leaders-view').innerText().catch(() => ''),
    };
  }
  fs.writeFileSync(path.join(OUT, 'leaders-click.json'), JSON.stringify(leadersAfter, null, 2));

  // Office POTG
  await page.goto(`${BASE}/franchise-command-center.html?franchise_id=${fid}&team_id=${tid}&tab=home-tab`);
  await waitReady(page);
  const potg = await page.evaluate(() => {
    const links = [...document.querySelectorAll('#home-tab a[href]')].map((a) => ({
      text: (a.textContent || '').trim().slice(0, 80),
      href: a.getAttribute('href'),
    }));
    return {
      playerLinks: links.filter((l) => /player-view|player-detail|player_id/.test(l.href || '')),
      allHrefsSample: links.slice(0, 20),
      text: (document.querySelector('#home-tab')?.innerText || '').slice(0, 800),
    };
  });
  fs.writeFileSync(path.join(OUT, 'office-potg.json'), JSON.stringify(potg, null, 2));
  if (potg.playerLinks.length) {
    await page.locator(`a[href="${potg.playerLinks[0].href}"]`).first().evaluate((a) => a.click());
    await page.waitForTimeout(1500);
    const officeAfter = await page.evaluate(() => ({
      search: location.search,
      player_id: new URLSearchParams(location.search).get('player_id'),
      ctxPlayer: window.FranchiseContext ? window.FranchiseContext.get('player_id') : null,
      hero: document.querySelector('#player-view .gob-hero-n')?.textContent || '',
      error: document.querySelector('#player-view .gob-view-error')?.textContent || '',
    }));
    fs.writeFileSync(path.join(OUT, 'office-potg-after.json'), JSON.stringify(officeAfter, null, 2));
    await page.screenshot({ path: path.join(OUT, 'offline-office-before-1280.png'), fullPage: false });
  }

  // Direct hard-nav to player-view
  if (pid) {
    await page.goto(`${BASE}/franchise-command-center.html?franchise_id=${fid}&team_id=${tid}&tab=player-view&player_id=${encodeURIComponent(pid)}`);
    await waitReady(page);
    await page.waitForTimeout(800);
    const hard = await page.evaluate(() => ({
      search: location.search,
      player_id: new URLSearchParams(location.search).get('player_id'),
      ctxPlayer: window.FranchiseContext ? window.FranchiseContext.get('player_id') : null,
      hero: document.querySelector('#player-view .gob-hero-n')?.textContent || '',
      error: document.querySelector('#player-view .gob-view-error')?.textContent || '',
    }));
    fs.writeFileSync(path.join(OUT, 'hard-nav.json'), JSON.stringify(hard, null, 2));
    await page.screenshot({ path: path.join(OUT, 'offline-hardnav-1280.png'), fullPage: false });
  }

  await browser.close();
  console.log('done', { fid, pid, afterClick, api: detailRes.status() });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
