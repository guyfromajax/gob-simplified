// @ts-check
/**
 * Prep polish: Game Plan layout and copy, Playbooks controls, the shared save
 * toast, and the leave prompt (only real edits; in-app switches use the app's
 * own confirm). Stubbed from a captured real-franchise fixture.
 *
 * POLISH_SHOTS=1 also writes reports/polish-prep-plan/*.png.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TEAM = 'Lancaster';
const OUT = path.join(__dirname, '../../reports/polish-prep-plan');
const SHOTS = process.env.POLISH_SHOTS === '1';

test.describe.configure({ timeout: 120000 });

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

/** Real CMDs are all 0 in a new franchise; spread them so the sort shows. */
function playbooksWithCmd() {
  const pb = clone(FIXTURE.playbooks);
  const cmd = {};
  pb.set_plays.forEach((play, i) => { cmd[play.play_id] = 30 + ((i * 37) % 61); });
  ['set_plays', 'set_play_inside', 'set_play_attack', 'set_play_outside'].forEach((key) => {
    (pb[key] || []).forEach((play) => { play.effectiveness = cmd[play.play_id]; });
  });
  pb.set_plays.reverse();
  return pb;
}

async function fulfillJson(route, body, status) {
  await route.fulfill({ status: status || 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, saves) {
  const playbooks = playbooksWithCmd();
  await page.route('**/*', async (route) => {
    const request = route.request();
    const method = request.method();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const api = pathname.startsWith('/api/')
      || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/')
      || pathname === '/teams'
      || pathname === '/app-config';
    if (!api) {
      await route.continue();
      return;
    }
    if (pathname === '/api/auth/me') return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    if (pathname === '/franchise/command-center/data') return fulfillJson(route, FIXTURE.cc);
    if (pathname === '/franchise/team-data') return fulfillJson(route, FIXTURE.teamData);
    if (pathname === '/franchise/training-points') return fulfillJson(route, FIXTURE.trainingPoints);
    if (pathname === '/franchise/league-news') return fulfillJson(route, FIXTURE.news);
    if (pathname === '/franchise/standings') return fulfillJson(route, FIXTURE.standings);
    if (pathname === '/teams') return fulfillJson(route, FIXTURE.teams);
    if (pathname.startsWith('/roster/')) return fulfillJson(route, FIXTURE.roster);
    if (pathname === '/franchise/player/development-focus' && method === 'POST') {
      const body = request.postDataJSON() || {};
      return fulfillJson(route, { ok: true, training_position: body.training_position, training_focus: body.training_focus });
    }
    if (pathname === '/api/gameplan') {
      if (method === 'PUT') {
        saves.push('gameplan');
        return fulfillJson(route, { success: true });
      }
      return fulfillJson(route, FIXTURE.gameplan);
    }
    if (pathname === '/api/playbooks/preview-shot-weights') return fulfillJson(route, FIXTURE.preview);
    if (pathname === '/api/playbooks') {
      if (method === 'POST') {
        saves.push('playbooks');
        return fulfillJson(route, { success: true, position_shot_weights: FIXTURE.preview.position_shot_weights });
      }
      return fulfillJson(route, playbooks);
    }
    return fulfillJson(route, {});
  });
}

async function openFcc(page, tab, saves) {
  await stubAuth(page);
  await page.addInitScript(() => {
    try { sessionStorage.setItem('gameplan_suppress_warning', ''); } catch (e) { /* storage off */ }
  });
  await installApi(page, saves || []);
  const q = new URLSearchParams({ franchise_id: FID, team_id: TEAM, user_team_id: TEAM, tab });
  await page.goto(`/franchise-command-center.html?${q}`);
}

const READY = {
  'training-view': '#training-view .devfocus-select, #training-view .pdg-grid',
  'game-plan-view': '#game-plan-view #slider-offense',
  'playbooks-view': '#playbooks-view .play',
};

async function waitReady(page, tab) {
  await expect(page.locator(READY[tab]).first()).toBeVisible({ timeout: 30000 });
  await page.waitForTimeout(400);
}

async function wouldPrompt(page) {
  return page.evaluate(() => {
    const e = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(e);
    return e.defaultPrevented;
  });
}

async function goToSchedule(page) {
  await page.getByRole('button', { name: 'Team', exact: true }).click();
  await page.getByRole('tab', { name: 'Schedule', exact: true }).click();
}

function watchDialogs(page) {
  const seen = [];
  page.on('dialog', async (dialog) => {
    seen.push(dialog.type());
    await dialog.dismiss();
  });
  return seen;
}

async function shot(page, name, size) {
  if (!SHOTS) return;
  fs.mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: path.join(OUT, `${name}-${size.width}x${size.height}.png`) });
}

test.describe('leave prompt', () => {
  for (const tab of ['training-view', 'game-plan-view', 'playbooks-view']) {
    test(`${tab}: no edits, switch to Schedule, no prompt`, async ({ page }) => {
      const dialogs = watchDialogs(page);
      await openFcc(page, tab);
      await waitReady(page, tab);
      expect(await wouldPrompt(page)).toBe(false);
      await goToSchedule(page);
      await page.waitForTimeout(600);
      await expect(page.locator('.gob-leave-confirm')).toHaveCount(0);
      expect(await wouldPrompt(page)).toBe(false);
      expect(dialogs).toEqual([]);
    });
  }

  test('game plan: move a slider and back is not an edit', async ({ page }) => {
    await openFcc(page, 'game-plan-view');
    await waitReady(page, 'game-plan-view');
    await page.locator('#slider-offense').focus();
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowLeft');
    expect(await wouldPrompt(page)).toBe(false);
    await goToSchedule(page);
    await expect(page.locator('.gob-leave-confirm')).toHaveCount(0);
  });

  test('game plan: real edit, in-app switch uses the in-app confirm', async ({ page }) => {
    const dialogs = watchDialogs(page);
    await openFcc(page, 'game-plan-view');
    await waitReady(page, 'game-plan-view');
    await page.locator('#slider-offense').focus();
    await page.keyboard.press('ArrowRight');
    expect(await wouldPrompt(page)).toBe(true);

    const team = page.getByRole('button', { name: 'Team', exact: true });
    const confirm = page.getByRole('alertdialog', { name: 'Unsaved Game Plan' });
    await team.click();
    await expect(confirm).toBeVisible();
    await confirm.getByRole('button', { name: 'Keep Editing' }).click();
    await expect(confirm).toHaveCount(0);
    await expect(page.locator('#game-plan-view #slider-offense')).toBeVisible();

    await team.click();
    await expect(confirm).toBeVisible();
    await confirm.getByRole('button', { name: 'Discard' }).click();
    await expect(page.locator('#game-plan-view')).toBeHidden();
    await page.getByRole('tab', { name: 'Schedule', exact: true }).click();
    await expect(page.locator('.gob-leave-confirm')).toHaveCount(0);
    expect(await wouldPrompt(page)).toBe(false);
    expect(dialogs).toEqual([]);
  });

  test('playbooks: real edit, in-app switch, save from the confirm', async ({ page }) => {
    const saves = [];
    const dialogs = watchDialogs(page);
    await openFcc(page, 'playbooks-view', saves);
    await waitReady(page, 'playbooks-view');
    await page.locator('#playbooks-view .et-slider[data-sl]').first().focus();
    await page.keyboard.press('ArrowRight');
    expect(await wouldPrompt(page)).toBe(true);

    await page.getByRole('button', { name: 'Team', exact: true }).click();
    const confirm = page.getByRole('alertdialog', { name: 'Unsaved Playbooks' });
    await expect(confirm).toBeVisible();
    await confirm.getByRole('button', { name: 'Save Playbooks' }).click();
    await expect(confirm).toHaveCount(0);
    await expect(page.locator('#playbooks-view')).toBeHidden();
    await page.getByRole('tab', { name: 'Schedule', exact: true }).click();
    expect(saves).toEqual(['playbooks']);
    expect(await wouldPrompt(page)).toBe(false);
    expect(dialogs).toEqual([]);
  });

  test('training: player-dev saves on change, so no leave prompt', async ({ page }) => {
    const dialogs = watchDialogs(page);
    await openFcc(page, 'training-view');
    await waitReady(page, 'training-view');
    const focus = page.locator('#training-view .devfocus-select[data-devfocus-field="training_focus"]').first();
    await focus.selectOption('offensive');
    expect(await wouldPrompt(page)).toBe(false);
    await goToSchedule(page);
    await page.waitForTimeout(400);
    await expect(page.locator('.gob-leave-confirm')).toHaveCount(0);
    expect(dialogs).toEqual([]);
  });
});

test.describe('game plan', () => {
  for (const size of [{ width: 1280, height: 720 }, { width: 1920, height: 1080 }]) {
    test(`layout and copy at ${size.width}`, async ({ page }) => {
      await page.setViewportSize(size);
      await openFcc(page, 'game-plan-view');
      await waitReady(page, 'game-plan-view');
      const view = page.locator('#game-plan-view');

      const tracks = await view.locator('.gt.strategy-slider').evaluateAll((els) => els.map((el) => {
        const b = el.getBoundingClientRect();
        const stops = Array.from(el.querySelectorAll('.gt-s, .gt-stop, [data-stop]')).map((s) => {
          const r = s.getBoundingClientRect();
          return Math.round((r.left + r.width / 2 - b.left) * 10) / 10;
        });
        const section = el.closest('section');
        return { id: el.id, side: section ? section.getAttribute('aria-label') : '', left: b.left, right: b.right, stops };
      }));
      expect(tracks.length).toBeGreaterThanOrEqual(12);
      const byColumn = {};
      tracks.forEach((t) => {
        (byColumn[t.side] = byColumn[t.side] || []).push(t);
      });
      expect(Object.keys(byColumn).sort()).toEqual(['Defense', 'Offense']);
      const widths = tracks.map((t) => t.right - t.left);
      expect(Math.max(...widths) - Math.min(...widths)).toBeLessThanOrEqual(1);
      Object.values(byColumn).forEach((col) => {
        const lefts = col.map((t) => t.left);
        const rights = col.map((t) => t.right);
        expect(Math.max(...lefts) - Math.min(...lefts), JSON.stringify(col.map((t) => [t.id, t.left]))).toBeLessThanOrEqual(1);
        expect(Math.max(...rights) - Math.min(...rights)).toBeLessThanOrEqual(1);
        const first = col[0].stops;
        col.forEach((t) => {
          expect(t.stops.length).toBe(first.length);
          t.stops.forEach((x, i) => expect(Math.abs(x - first[i])).toBeLessThanOrEqual(1));
        });
      });

      await expect(view.locator('.sh h2')).toHaveCount(0);
      await expect(view.getByRole('heading', { name: 'Offense', exact: true })).toHaveCount(0);
      await expect(view.getByRole('heading', { name: 'Defense', exact: true })).toHaveCount(0);
      const execution = view.locator('.grp-h', { hasText: 'Execution' });
      const transition = view.locator('.grp-h', { hasText: 'Transition' });
      await expect(execution).toBeVisible();
      await expect(transition).toBeVisible();
      const ex = await execution.boundingBox();
      const tr = await transition.boundingBox();
      expect(Math.abs(((ex?.y || 0) + (ex?.height || 0)) - ((tr?.y || 0) + (tr?.height || 0)))).toBeLessThanOrEqual(1);
      const exFont = await execution.evaluate((el) => getComputedStyle(el).font);
      const trFont = await transition.evaluate((el) => getComputedStyle(el).font);
      expect(exFont).toBe(trFont);

      await expect(view.locator('[data-effect="tempo"]')).toHaveText('Work the offense or shoot fast.');
      await expect(view.locator('[data-effect="defense"]')).toHaveText('Man uses talent. Zone uses IQ.');
      await expect(view.locator('[data-effect="aggression"]')).toHaveText('Play it safe or take more risks.');
      await expect(view.locator('[data-effect="alterations"]')).toHaveText('Follow the script or read and react.');
      await expect(view).not.toContainText('Paint touches', { ignoreCase: true });
      await expect(view).not.toContainText('Perimeter shots', { ignoreCase: true });

      await shot(page, 'game-plan', size);
    });
  }

  test('shot diet (i) shows the tooltip on hover and on focus', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openFcc(page, 'game-plan-view');
    await waitReady(page, 'game-plan-view');
    const info = page.locator('#game-plan-view .slider-nest__info');
    const bubble = page.locator('#attribute-tooltip-bubble');
    const copy = 'These three share touches — raise one, the others compete.';

    await info.hover();
    await expect(bubble).toBeVisible();
    await expect(bubble).toHaveText(copy);
    await page.mouse.move(5, 5);
    await expect(bubble).toBeHidden();

    await info.focus();
    await expect(bubble).toBeVisible();
    await expect(bubble).toHaveText(copy);
    await shot(page, 'game-plan-tooltip', { width: 1280, height: 720 });
    await page.setViewportSize({ width: 1920, height: 1080 });
    await info.blur();
    await info.focus();
    await expect(bubble).toBeVisible();
    await shot(page, 'game-plan-tooltip', { width: 1920, height: 1080 });
  });

  test('save shows the shared toast, gone by 2s, and stays on the view', async ({ page }) => {
    const saves = [];
    await openFcc(page, 'game-plan-view', saves);
    await waitReady(page, 'game-plan-view');
    await page.locator('#slider-offense').focus();
    await page.keyboard.press('ArrowRight');
    await page.locator('#btn-save-game-plan').click();
    const toast = page.locator('.gob-save-toast');
    await expect(toast).toHaveText('Game plan saved');
    await expect(toast).toBeVisible();
    await expect(toast).toHaveAttribute('aria-live', 'polite');
    expect(saves).toEqual(['gameplan']);
    await page.waitForTimeout(2000);
    await expect(toast).toBeHidden();
    await expect(page.locator('#game-plan-view #slider-offense')).toBeVisible();
    expect(await wouldPrompt(page)).toBe(false);
  });
});

test.describe('playbooks', () => {
  test('no LIVE, toggle beside the editor, divider, focus order, top-level locks', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openFcc(page, 'playbooks-view');
    await waitReady(page, 'playbooks-view');
    const view = page.locator('#playbooks-view');

    await expect(page.locator('.psw-live-pill')).toHaveCount(0);
    await expect(view.locator('.psw-strip-label')).not.toContainText('LIVE');
    await expect(page.locator('.pg-tools .playbooks-tabs')).toHaveCount(0);
    await expect(view.locator('.playbooks-side-row .playbooks-tabs')).toBeVisible();

    const groups = view.locator('.psw-group');
    await expect(groups).toHaveCount(2);
    const divider = await groups.nth(1).evaluate((el) => getComputedStyle(el).boxShadow);
    expect(divider).not.toBe('none');

    const setPlays = await view.locator('#set-plays-grid .play').evaluateAll((els) => els.map((el) => ({
      focus: el.dataset.focus,
      cmd: Number(el.querySelector('.cmd b')?.textContent || 0),
      meta: el.querySelector('.pn span')?.textContent || '',
    })));
    expect(setPlays.length).toBeGreaterThan(3);
    const rank = { inside: 0, attack: 1, outside: 2 };
    for (let i = 1; i < setPlays.length; i += 1) {
      const a = setPlays[i - 1];
      const b = setPlays[i];
      expect(rank[a.focus]).toBeLessThanOrEqual(rank[b.focus]);
      if (a.focus === b.focus) expect(a.cmd).toBeGreaterThanOrEqual(b.cmd);
    }
    // The focus is the sub-section head a play sits under (Inside / Attack / Outside),
    // so the row's own line names only the target shooter.
    setPlays.forEach((p) => expect(p.meta.startsWith('Target shooter ')).toBe(true));
    await expect(view.locator('#set-plays-grid .pb-sub h3')).toHaveText(['Inside', 'Attack', 'Outside']);

    const firstSet = view.locator('#set-plays-grid .play').first();
    const lock = firstSet.locator('[data-lock]');
    await expect(lock).toBeVisible();
    await expect(firstSet).not.toHaveClass(/\bopen\b/);
    await expect(view.locator('.pdet [data-lock], .play-lock')).toHaveCount(0);
    const lockBox = await lock.boundingBox();
    const trackBox = await firstSet.locator('.wb').boundingBox();
    expect(Math.abs((lockBox?.y || 0) + (lockBox?.height || 0) / 2 - ((trackBox?.y || 0) + (trackBox?.height || 0) / 2))).toBeLessThanOrEqual(2);
    expect((trackBox?.width || 0)).toBeGreaterThanOrEqual(118);
    await lock.click();
    await expect(view.locator('#set-plays-grid .play').first().locator('[data-lock]')).toHaveAttribute('aria-pressed', 'true');

    await shot(page, 'playbooks', { width: 1280, height: 720 });
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.waitForTimeout(300);
    await shot(page, 'playbooks', { width: 1920, height: 1080 });
  });

  test('arrow keys nudge 1, Shift+arrow nudges 5, steps unchanged', async ({ page }) => {
    await openFcc(page, 'playbooks-view');
    await waitReady(page, 'playbooks-view');
    const slider = page.locator('#playbooks-view .et-slider[data-sl]').first();
    const id = await slider.getAttribute('data-sl');
    const value = async () => Number(await page.locator(`#playbooks-view .et-slider[data-sl="${id}"]`).getAttribute('aria-valuenow'));
    await slider.focus();
    const start = await value();
    await page.keyboard.press('ArrowRight');
    expect(await value()).toBe(start + 1);
    await page.keyboard.press('Shift+ArrowRight');
    expect(await value()).toBe(start + 6);
    await page.keyboard.press('Shift+ArrowLeft');
    await page.keyboard.press('ArrowLeft');
    expect(await value()).toBe(start);
    const input = page.locator(`#playbooks-view .et-pct-input[data-pct="${id}"]`);
    await expect(input).toHaveValue(String(start));
  });

  test('save shows the shared toast, gone by 2s', async ({ page }) => {
    const saves = [];
    for (const size of [{ width: 1280, height: 720 }, { width: 1920, height: 1080 }]) {
      await page.setViewportSize(size);
      await openFcc(page, 'playbooks-view', saves);
      await waitReady(page, 'playbooks-view');
      await page.locator('#playbooks-view .et-slider[data-sl]').first().focus();
      await page.keyboard.press('ArrowRight');
      const before = await page.locator('#playbooks-view .playbooks-layout, #playbooks-view .pbc').first().boundingBox();
      await page.locator('#save-btn').click();
      const toast = page.locator('.gob-save-toast');
      await expect(toast).toHaveText('Playbooks saved');
      await expect(toast).toBeVisible();
      await expect(toast).toHaveAttribute('aria-live', 'polite');
      await expect(toast).toHaveCSS('border-left-width', '0px');
      const after = await page.locator('#playbooks-view .playbooks-layout, #playbooks-view .pbc').first().boundingBox();
      expect(after?.y).toBe(before?.y);
      await page.waitForTimeout(250);
      await shot(page, 'playbooks-toast', size);
      await page.waitForTimeout(1750);
      await expect(toast).toBeHidden();
      await expect(page.locator('#playbooks-view .play').first()).toBeVisible();
      expect(await wouldPrompt(page)).toBe(false);
    }
    expect(saves).toEqual(['playbooks', 'playbooks']);
  });
});
