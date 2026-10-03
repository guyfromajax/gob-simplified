/**
 * v3 training, offline: the Training playbook choice is saved on the desktop SQLite store.
 *
 * A real franchise on the desktop server (playwright.desktop.config.js), no API doubles:
 * choose a Custom Playbook, find it the default in a fresh session, switch back, choose it
 * again, run a real training with it, and read the same choice back afterwards. The real
 * training also shows the carried plays are the ones that trained.
 *
 *   V3T_SHOTS=after   shots to reports/v3-training/
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || process.env.GOB_LOOPBACK_PORT || '8767';
const OUT = path.join(__dirname, '../../reports/v3-training');
const PHASE = process.env.V3T_SHOTS || '';
const LONG = 600000;

test.describe.configure({ mode: 'serial', timeout: 900000 });

let fid = '';

test.afterAll(async ({ request }) => {
  // Leave the desktop e2e sqlite as we found it (two-franchise cap).
  if (fid) await request.delete('/franchise/' + fid).catch(() => {});
});

test('offline: the Custom Playbook choice and its plays are saved, used and kept', async ({ browser, request }) => {
  const create = await request.post('/franchise/select-team', { data: { team_name: 'Lancaster' } });
  expect(create.ok(), await create.text()).toBeTruthy();
  fid = (await create.json()).franchise_id;
  const next = await (await request.post('/franchise/play-next-game', { data: { franchise_id: fid } })).json();
  const tid = String(next.home === 'Lancaster' ? next.home_id : next.away_id);
  const q = (extra) => new URLSearchParams(Object.assign(
    { franchise_id: fid, team_id: tid, user_team_id: tid, mode: 'franchise' }, extra || {},
  )).toString();
  const savedChoice = async () => {
    const res = await request.get('/franchise/training-points', { params: { franchise_id: fid } });
    expect(res.ok(), await res.text()).toBeTruthy();
    return (await res.json()).training_playbook_choice;
  };

  // A session is one browser context: a new one starts with empty sessionStorage.
  const session = async () => {
    const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
    context.setDefaultTimeout(45000);
    context.setDefaultNavigationTimeout(90000);
    const page = await context.newPage();
    await page.addInitScript((port) => {
      window.GOB_BUILD_PROFILE = 'desktop';
      window.GOB_LOOPBACK_PORT = Number(port);
      window.alert = () => {};
    }, PORT);
    return { context, page };
  };
  const openTraining = async (page) => {
    await page.goto('/training.html?' + q({ from: 'locker-room' }));
    await page.waitForFunction(() => {
      const overlay = document.getElementById('page-load-overlay');
      return !overlay || getComputedStyle(overlay).display === 'none';
    });
    await expect(page.locator('#playbook-mode-current-btn')).toBeVisible();
    await expect(page.locator('#submit-btn')).toBeVisible();
    await page.waitForTimeout(600);
  };
  const selected = (page) => page.evaluate(() => (
    document.getElementById('playbook-mode-custom-btn').classList.contains('is-selected') ? 'custom' : 'current-playbooks'
  ));
  const shot = async (page, name) => {
    if (!PHASE) return;
    fs.mkdirSync(OUT, { recursive: true });
    await page.mouse.move(0, 0);
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(OUT, PHASE + '-4-offline-' + name + '-1280.png'), animations: 'disabled' });
  };
  /** On the Custom Playbook page: pick two offense plays and two defenses, save, land on Training. */
  const chooseCustom = async (page) => {
    await page.locator('#playbook-mode-custom-btn').click();
    await page.waitForURL(/training-playbooks\.html/);
    await expect(page.locator('#tp-offense-grid .tp-card').first()).toBeVisible();
    const pick = async (grid) => {
      const cards = page.locator(grid + ' .tp-card:not(.is-selected)');
      const ids = [];
      for (let i = 0; i < 2; i += 1) {
        const card = cards.first();
        ids.push(await card.getAttribute('data-id'));
        await card.click();
      }
      return ids;
    };
    const focus = { offense: await pick('#tp-offense-grid'), defense: await pick('#tp-defense-grid') };
    await expect(page.locator('#tp-dock-off-pct')).toHaveText('50%');
    await expect(page.locator('#tp-dock-def-pct')).toHaveText('50%');
    await page.locator('#tp-save').click();
    await page.waitForURL(/training\.html/);
    return focus;
  };
  const sorted = (focus) => ({ offense: focus.offense.slice().sort(), defense: focus.defense.slice().sort() });

  // 1. A new franchise trains Current Playbooks.
  expect(await savedChoice()).toEqual({ mode: 'current-playbooks', focus: null });
  let { context, page } = await session();
  await openTraining(page);
  expect(await selected(page)).toBe('current-playbooks');

  // 2. Choose a Custom Playbook: it is written to the SQLite save before the page leaves.
  const first = await chooseCustom(page);
  let saved = await savedChoice();
  expect(saved.mode).toBe('custom');
  expect(sorted(saved.focus)).toEqual(sorted(first));
  await context.close();

  // 3. A fresh session: Custom Playbook is the default, with those plays.
  ({ context, page } = await session());
  await openTraining(page);
  expect(await selected(page)).toBe('custom');
  await expect(page.locator('#custom-playbook-banner')).toBeVisible();
  expect(sorted(await page.evaluate(() => JSON.parse(sessionStorage.getItem('gob_training_playbook_focus'))))).toEqual(sorted(first));
  await shot(page, 'custom-default-fresh-session');

  // 4. Switch back: saved, and a fresh session opens on Current Playbooks.
  await page.locator('#playbook-mode-current-btn').click();
  await expect.poll(async () => (await savedChoice()).mode).toBe('current-playbooks');
  await context.close();
  ({ context, page } = await session());
  await openTraining(page);
  expect(await selected(page)).toBe('current-playbooks');

  // 5. Choose it again, then run a real training in another fresh session.
  const focus = await chooseCustom(page);
  await context.close();
  ({ context, page } = await session());
  await openTraining(page);
  expect(await selected(page)).toBe('custom');
  await page.locator('#auto-train-btn').click();
  await page.locator('#auto-train-modal-close').click().catch(() => {});
  await expect(page.locator('#submit-btn')).toBeEnabled({ timeout: 15000 });
  const sent = page.waitForRequest((req) => req.url().includes('/franchise/run-training/user') && req.method() === 'POST');
  await page.locator('#submit-btn').click();
  const body = (await sent).postDataJSON().training_data;
  expect(body.playbook_training_mode).toBe('custom');
  expect(sorted(body.training_playbook_focus)).toEqual(sorted(focus));
  await page.waitForURL(/training-report\.html/, { timeout: LONG });

  // 6. Training did not touch the setting.
  saved = await savedChoice();
  expect(saved.mode).toBe('custom');
  expect(sorted(saved.focus)).toEqual(sorted(focus));

  // 7. The real training put its play points on the carried plays and nowhere else.
  const reportRes = await request.get('/franchise/training-report', { params: { franchise_id: fid, team_id: tid, week: 1 }, timeout: LONG });
  expect(reportRes.ok(), await reportRes.text()).toBeTruthy();
  const reportData = await reportRes.json();
  // The report keys a play's gain by its id (a fixture keys by name; accept either).
  const playbooks = await (await request.get('/api/playbooks', { params: { mode: 'franchise', franchise_id: fid, team_id: tid } })).json();
  const offense = (playbooks.motion || []).concat(playbooks.set_plays || []);
  const idOf = {};
  offense.forEach((play) => { idOf[String(play.play_id)] = String(play.play_id); idOf[play.name] = String(play.play_id); });
  const gained = Object.entries(reportData.plays_effectiveness_changes || {})
    .filter(([, delta]) => Number(delta) > 0).map(([key]) => idOf[key] || key).sort();
  test.info().annotations.push({ type: 'offline-training', description: 'carried ' + JSON.stringify(focus.offense) + ' gained ' + JSON.stringify(gained) });
  // Offense install points were spent (Auto-Train): both carried plays trained, and no other play did.
  expect(offense.length).toBeGreaterThan(4);
  expect(gained).toEqual(focus.offense.slice().sort());
  await context.close();
});
