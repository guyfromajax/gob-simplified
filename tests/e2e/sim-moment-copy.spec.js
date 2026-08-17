// @ts-check
/**
 * Moment copy pipeline — the .md is the source of truth, the pack is the fallback.
 *
 * Acceptance (brief §10): all copy sourced from sim-moment-copy.md; zero copy in source.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const S = path.join(__dirname, '../../FrontEnd/static');

const load = (page) => page.evaluate(() => import('/js/phaser/utils/simMomentCopy.js'));

async function mod(page) {
  await page.goto('/');
  // The real page (court.html) loads api-config.js, which owns the /static-vs-root split.
  // Without it copyUrl() falls back to the bare root path, which only works in production.
  await page.addScriptTag({ url: '/js/config/api-config.js' });
  await page.waitForFunction(() => !!(window.API_CONFIG && window.API_CONFIG.buildStaticPath));
  return page.evaluate(() => import('/js/phaser/utils/simMomentCopy.js').then((m) => { window.__c = m; return true; }));
}

test.describe('parsing', () => {
  test('parses the shipped copy file into every card type', async ({ page }) => {
    await mod(page);
    const m = await page.evaluate(async () => {
      const res = await fetch(window.__c.copyUrl());
      const parsed = window.__c.parseCopyMd(await res.text());
      return {
        ok: res.ok,
        version: parsed.version,
        ids: Object.keys(parsed.categories),
        emptyCats: Object.entries(parsed.categories).filter(([, c]) => !c.lines.length).map(([k]) => k),
        context: parsed.context.length,
        usable: window.__c.isUsablePack(parsed),
        sampleTag: parsed.categories.three && parsed.categories.three.tag,
        sampleColor: parsed.categories.milestone20 && parsed.categories.milestone20.color,
      };
    });
    expect(m.ok).toBe(true);
    expect(m.usable).toBe(true);
    expect(m.emptyCats).toEqual([]);
    expect(m.ids).toEqual(expect.arrayContaining([
      'bucket', 'three', 'paint', 'board', 'dime', 'stock',
      'milestone10', 'milestone20', 'milestone30', 'doubleDouble', 'boards10',
      'streak', 'cold', 'foul', 'run',
    ]));
    expect(m.sampleTag).toBe('3PM');        // tag overrides the id
    expect(m.sampleColor).toBe('gold');
    expect(m.context).toBeGreaterThanOrEqual(4);
    expect(m.version).toMatch(/^\d{4}\.\d{2}/);
  });

  test('context rows carry all six pipe-delimited fields', async ({ page }) => {
    await mod(page);
    const rows = await page.evaluate(async () => {
      const res = await fetch(window.__c.copyUrl());
      return window.__c.parseCopyMd(await res.text()).context;
    });
    for (const r of rows) {
      for (const k of ['setting', 'value', 'stat', 'now', 'base', 'league']) {
        expect(r[k], `${k} on ${JSON.stringify(r)}`).toBeTruthy();
      }
    }
  });

  test('a truncated or empty file is not accepted as a pack', async ({ page }) => {
    await mod(page);
    const m = await page.evaluate(() => ({
      empty: window.__c.isUsablePack(window.__c.parseCopyMd('')),
      partial: window.__c.isUsablePack(window.__c.parseCopyMd('### bucket · tag BUCKET\n- {NAME} {PTS} PTS\n')),
    }));
    expect(m.empty).toBe(false);
    expect(m.partial).toBe(false);
  });
});

test.describe('loading', () => {
  test('prefers the .md and reports it as the source', async ({ page }) => {
    await mod(page);
    const m = await page.evaluate(async () => {
      window.__c.resetMomentCopy();
      const p = await window.__c.loadMomentCopy({ force: true });
      return { source: p.source, cats: Object.keys(p.categories).length };
    });
    expect(m.source).toContain('sim-moment-copy.md');
    expect(m.cats).toBeGreaterThanOrEqual(15);
  });

  test('falls back to the bundled pack when the file cannot be fetched', async ({ page }) => {
    await page.route('**/sim-moment-copy.md**', (r) => r.fulfill({ status: 404, body: '' }));
    await mod(page);
    const m = await page.evaluate(async () => {
      window.__c.resetMomentCopy();
      const p = await window.__c.loadMomentCopy({ force: true });
      return { source: p.source, cats: Object.keys(p.categories).length, ctx: p.context.length };
    });
    expect(m.source).toContain('fallback');
    expect(m.cats).toBeGreaterThanOrEqual(8);
    expect(m.ctx).toBeGreaterThan(0);
  });

  test('a network error degrades rather than rejecting — playback must not die on copy', async ({ page }) => {
    await page.route('**/sim-moment-copy.md**', (r) => r.abort());
    await mod(page);
    const m = await page.evaluate(async () => {
      window.__c.resetMomentCopy();
      const p = await window.__c.loadMomentCopy({ force: true });
      return p.source;
    });
    expect(m).toContain('fallback');
  });
});

test.describe('slot filling', () => {
  test('fills slots from the values bag', async ({ page }) => {
    await mod(page);
    const out = await page.evaluate(() =>
      window.__c.fillLine('{NAME} {PTS} ON {FGM}-{FGA}', { NAME: 'REYES', PTS: 24, FGM: 9, FGA: 14 }));
    expect(out).toBe('REYES 24 ON 9-14');
  });

  test('a template needing a slot the event lacks is rejected, not printed raw', async ({ page }) => {
    await mod(page);
    const m = await page.evaluate(() => ({
      missing: window.__c.fillLine('{NAME} {AST} AST', { NAME: 'REYES' }),
      zeroIsFine: window.__c.fillLine('{NAME} {PTS} PTS', { NAME: 'REYES', PTS: 0 }),
    }));
    expect(m.missing).toBeNull();
    expect(m.zeroIsFine).toBe('REYES 0 PTS');   // 0 is a real value, not a missing one
  });

  test('pickLine only returns variants this event can fill', async ({ page }) => {
    await mod(page);
    const m = await page.evaluate(async () => {
      const pack = await window.__c.loadMomentCopy();
      const picks = [];
      for (let i = 0; i < 40; i += 1) {
        picks.push(window.__c.pickLine(pack, 'bucket', { NAME: 'REYES', PTS: 12 }, () => i / 40));
      }
      return picks;
    });
    for (const p of m) {
      expect(p).not.toBeNull();
      expect(p.line).not.toMatch(/\{[A-Z]+\}/);   // never a raw slot on screen
      expect(p.line).toContain('REYES');
      expect(p.tag).toBe('BUCKET');
    }
  });

  test('returns null when no variant can be filled at all', async ({ page }) => {
    await mod(page);
    const out = await page.evaluate(async () => {
      const pack = await window.__c.loadMomentCopy();
      return window.__c.pickLine(pack, 'bucket', {}, () => 0);
    });
    expect(out).toBeNull();
  });
});

test('zero card copy lives in the presentation or assembler source', () => {
  // The acceptance criterion, enforced: card lines are data, not code.
  const md = fs.readFileSync(path.join(S, 'sim-moment-copy.md'), 'utf8');
  const lines = md.split(/\r?\n/).filter((l) => l.trim().startsWith('- ') && l.includes('{'));
  expect(lines.length).toBeGreaterThan(20);
  const sources = ['js/phaser/utils/simGamePresentation.js', 'js/phaser/utils/simTimelineAssembler.js']
    .map((f) => fs.readFileSync(path.join(S, f), 'utf8'));
  for (const src of sources) {
    expect(src).not.toMatch(/\{NAME\}|\{PTS\}|\{REB\}|\{AST\}/);
  }
});
