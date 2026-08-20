// @ts-check
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const FccRosterData = require('../../FrontEnd/static/js/shared/fccRosterData.js');
const FCC_SOURCE = fs.readFileSync(
  path.join(__dirname, '../../FrontEnd/static/franchise-command-center.js'), 'utf8'
);

function player(id) {
  return { _id: id, name: id };
}

test('full roster payload keeps 12 Varsity and 3 Practice Squad players', () => {
  const payload = FccRosterData.normalize({
    players: Array.from({ length: 12 }, (_, i) => player(`v${i}`)),
    training_squad: [player('ps1'), player('ps2'), player('ps3')],
    practice_squad_recruits: [],
  });
  expect(payload.players).toHaveLength(12);
  expect(FccRosterData.practiceSquadPlayers(payload).map((p) => p._id))
    .toEqual(['ps1', 'ps2', 'ps3']);
});

test('Practice Squad scope includes assigned players and signed recruits', () => {
  const payload = {
    players: [],
    training_squad: [player('assigned')],
    practice_squad_recruits: [player('recruit')],
  };
  expect(FccRosterData.practiceSquadPlayers(payload).map((p) => p._id))
    .toEqual(['assigned', 'recruit']);
});

test('session restore preserves the complete roster payload', () => {
  const restored = FccRosterData.fromSessionCache({
    rosterData: {
      players: Array.from({ length: 12 }, (_, i) => player(`v${i}`)),
      training_squad: [player('ps1'), player('ps2'), player('ps3')],
    },
  });
  expect(restored.players).toHaveLength(12);
  expect(FccRosterData.practiceSquadPlayers(restored)).toHaveLength(3);
});

test('legacy session cache remains safe and warms Varsity only', () => {
  const restored = FccRosterData.fromSessionCache({ rosterPlayers: [player('v1')] });
  expect(restored.players).toHaveLength(1);
  expect(FccRosterData.practiceSquadPlayers(restored)).toEqual([]);
});

test('FCC scope and session wiring use the full roster cache, not top-data summary', () => {
  const selector = FCC_SOURCE.match(/function fccPracticeSquadPlayers\(\) \{([\s\S]*?)\n\}/)?.[1] || '';
  expect(selector).toContain('userRosterDataCache');
  expect(selector).not.toContain('commandCenterTopDataCache');
  expect(FCC_SOURCE).toContain('rosterData: userRosterDataCache || null');
  expect(FCC_SOURCE).toContain('renderTeam(userRosterDataCache)');
});
