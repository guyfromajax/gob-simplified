// @ts-check
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const RENDERER = fs.readFileSync(
  path.join(__dirname, '../../FrontEnd/static/fcc-tournament-style-a.js'),
  'utf8'
);

const BYE_TEAM = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const TEAM_2 = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const TEAM_3 = 'cccccccccccccccccccccccc';

test('three-team region keeps the bye team visible after Round 1 resolves', async ({ page }) => {
  await page.setContent('<div id="bracket"></div>');
  await page.addScriptTag({ content: RENDERER });
  await page.evaluate(({ byeTeam, team2, team3 }) => {
    window.FccTournamentStyleA.renderInto(document.getElementById('bracket'), {
      sectionTitle: 'Region B Tournament',
      layout: 'compact4',
      tierHint: 'region',
      bracket: {
        round1: [{
          home_team: team2,
          away_team: team3,
          winner: team3,
          score: { home: 72, away: 81 },
        }],
        round2: [],
        // R1_0 has already been replaced by the winner, matching the persisted
        // Week 31/completed-bracket shape that previously rendered TBD / TBD.
        final: [{
          home_team: byeTeam,
          away_team: team3,
          winner: null,
          score: {},
        }],
      },
      teamIdToNameMap: {
        [byeTeam]: 'Bye Team',
        [team2]: 'Team 2',
        [team3]: 'Team 3',
      },
      teamIdMetaMap: {},
      topData: { week: 31 },
      allBrackets: true,
    });
  }, { byeTeam: BYE_TEAM, team2: TEAM_2, team3: TEAM_3 });

  const roundOneCards = page.locator('.fcc-tb-region-col').first().locator('.fcc-tb-mu');
  await expect(roundOneCards).toHaveCount(2);
  await expect(roundOneCards.nth(0).locator('.fcc-tb-name')).toHaveText(['Bye Team', 'BYE']);
  await expect(roundOneCards.nth(1).locator('.fcc-tb-name')).toHaveText(['Team 2', 'Team 3']);
});
