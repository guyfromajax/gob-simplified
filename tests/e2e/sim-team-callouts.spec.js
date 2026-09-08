// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Sim Game team callouts', () => {
  test('abbr callout copy never repeats the full team name', async ({ page }) => {
    await page.goto('/');
    const result = await page.evaluate(async () => {
      const { CALLOUT_PACK, fillCalloutLine } = await import('/js/phaser/utils/simCalloutCopy.js');
      const values = { TEAM: 'South Lancaster', RUN: '10–0', EDGE: 10, STAT: 'rebounding' };
      const categories = ['run', 'advantage', 'disadvantage'];
      return categories.flatMap((id) => CALLOUT_PACK.categories[id].lines.map((line) => ({
        id,
        template: line,
        rendered: fillCalloutLine(line, values),
      })));
    });

    for (const row of result) {
      expect(row.template).not.toContain('{TEAM}');
      expect(row.rendered).not.toContain('South Lancaster');
    }
  });

  test('callout accent is the exact color selected for that worm line', async ({ page }) => {
    await page.goto('/');
    const result = await page.evaluate(async () => {
      const { calloutAccentColor } = await import('/js/phaser/utils/simGamePresentation.js');
      const teams = {
        home: { color: '#7BC143' },
        away: { color: '#F2A900' },
      };
      return {
        home: calloutAccentColor({ side: 'home', color: 'red' }, teams),
        away: calloutAccentColor({ side: 'away', color: 'blue' }, teams),
      };
    });

    // Semantic category colors must not override the primary/secondary color chosen
    // by readableTeamPresentationColor for the corresponding worm line.
    expect(result.home).toBe('#7BC143');
    expect(result.away).toBe('#F2A900');
  });
});
