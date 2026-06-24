/**
 * @jest-environment jsdom
 */

import { updateStrategyBars } from './strategyBars.js';

function makeDom() {
  document.body.innerHTML = `
    <div id="sb-strat-away"></div>
    <div id="sb-strat-home"></div>
  `;
}

test('updateStrategyBars reveals stacks on first turn with four call fields', () => {
  makeDom();
  const turn = {
    possession_team_id: 'HOME_ID',
    offense_tempo_call: 'fast',
    offense_aggression_call: 'aggressive',
    defense_tempo_call: 'slow',
    defense_aggression_call: 'passive',
  };
  const simData = {
    home_team_id: 'HOME_ID',
    away_team_id: 'AWAY_ID',
    teams: {
      HOME_ID: { strategy_settings: { alterations: 3 } },
      AWAY_ID: { strategy_settings: { alterations: 1 } },
    },
  };

  updateStrategyBars(turn, 'HOME_ID', simData);

  const away = document.getElementById('sb-strat-away');
  const home = document.getElementById('sb-strat-home');
  expect(away.classList.contains('is-visible')).toBe(true);
  expect(home.classList.contains('is-visible')).toBe(true);
  expect(away.querySelector('[data-row="alt"] .val').textContent).toBe('LESS');
  expect(home.querySelector('[data-row="tempo"] .val').textContent).toBe('FAST');
});

test('updateStrategyBars no-ops without four call fields', () => {
  makeDom();
  updateStrategyBars({ result_type: 'TIMEOUT' }, 'HOME_ID', {});
  expect(document.getElementById('sb-strat-away').classList.contains('is-visible')).toBe(false);
});
