// @ts-check
/** team-roster-view.html redirects into the roster module view. */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

const S = path.join(__dirname, '../../FrontEnd/static');
const read = (name) => fs.readFileSync(path.join(S, name), 'utf8');

test('team-roster-view.html redirects into the roster module', async ({ page }) => {
  const html = read('team-roster-view.html');
  expect(html).toContain("params.get('mode') === 'practice_squad' && params.get('ps_team_id')");
  expect(html).toContain("params.set('tab', 'roster-view')");
  expect(html).toContain("location.replace('/franchise-command-center.html'");

  await stubAuth(page);
  await page.goto('/team-roster-view.html?mode=franchise&franchise_id=f1&team_id=t1&team_name=Lancaster&return_tab=standings-tab');
  await page.waitForURL(/franchise-command-center\.html/);
  const url = new URL(page.url());
  expect(url.searchParams.get('tab')).toBe('roster-view');
  expect(url.searchParams.get('franchise_id')).toBe('f1');
  expect(url.searchParams.get('team_id')).toBe('t1');
  expect(url.searchParams.get('team_name')).toBe('Lancaster');
  expect(url.searchParams.get('return_tab')).toBe('standings-tab');
});

test('the roster module is one attribute grid', () => {
  const view = read('js/shared/views/rosterView.js');
  expect(view).toContain('GOB_AttrTiles');
  expect(view).toContain('tileHtml');
  expect(view).toContain('Starters');
  expect(view).toContain('Bench');
  expect(view).toContain("id: 'varsity'");
  expect(view).toContain("id: 'practice'");
  expect(view).not.toContain('data-tr-view');
  expect(view).not.toContain('scholarship');
});
