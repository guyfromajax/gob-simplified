const { test } = require('node:test');
const assert = require('node:assert/strict');

const normalizerPromise = import('../possession/normalizeTurn.js');

function baseSimData() {
  return {
    home_team_id: 'HOME',
    away_team_id: 'AWAY',
    players: [
      { playerId: 'pg', team: 'home', team_id: 'HOME', pos: 'PG', name: 'Home PG' },
      { playerId: 'sg', team: 'home', team_id: 'HOME', pos: 'SG', name: 'Home SG' },
      { playerId: 'pf', team: 'home', team_id: 'HOME', pos: 'PF', name: 'Home PF' },
      { playerId: 'sf', team: 'home', team_id: 'HOME', pos: 'SF', name: 'Home SF' },
      { playerId: 'pgA', team: 'away', team_id: 'AWAY', pos: 'PG', name: 'Away PG' },
      { playerId: 'wing', team: 'away', team_id: 'AWAY', pos: 'SF', name: 'Away Wing' },
    ],
  };
}

test('normalizeTurn organizes a half-court possession with explicit passes', async () => {
  const { normalizeTurn } = await normalizerPromise;

  const turn = {
    id: 'turn-hco',
    possession_id: 'pos-1',
    possession_team_id: 'HOME',
    result_type: 'MAKE',
    text: 'PG drills the jumper off the kick-out.',
    shooter_id: 'pg',
    assist_id: 'sg',
    points: 2,
    score: { HOME: 52, AWAY: 48 },
    clock: '5:12',
    quarter: 3,
    passes: [
      { timestamp: 400, fromId: 'pg', toId: 'sg', duration: 180 },
      { timestamp: 600, fromId: 'sg', toId: 'pg', duration: 160 },
    ],
    animations: [
      {
        playerId: 'pg',
        teamId: 'HOME',
        position: 'PG',
        hasBallAtStep: [true, true, false],
        movement: [
          { timestamp: 0, coords: { x: 40, y: 24 }, action: 'handle_ball' },
          { timestamp: 400, coords: { x: 50, y: 24 }, action: 'pass' },
          { timestamp: 600, coords: { x: 54, y: 24 }, action: 'receive' },
          { timestamp: 800, coords: { x: 60, y: 23 }, action: 'shoot' },
        ],
      },
      {
        playerId: 'sg',
        teamId: 'HOME',
        position: 'SG',
        movement: [
          { timestamp: 0, coords: { x: 32, y: 20 }, action: 'drift' },
          { timestamp: 400, coords: { x: 45, y: 22 }, action: 'receive' },
          { timestamp: 600, coords: { x: 52, y: 23 }, action: 'pass' },
          { timestamp: 800, coords: { x: 58, y: 23 }, action: 'space' },
        ],
      },
      {
        playerId: 'ball',
        hasBallAtStep: [true, false, false, false],
        movement: [
          { timestamp: 0, coords: { x: 40, y: 24 }, action: 'handle_ball' },
          { timestamp: 400, coords: { x: 45, y: 22 }, action: 'receive' },
          { timestamp: 600, coords: { x: 54, y: 24 }, action: 'pass' },
          { timestamp: 800, coords: { x: 90, y: 25 }, action: 'shoot' },
        ],
      },
    ],
  };

  const normalized = normalizeTurn(turn, baseSimData());

  assert.equal(normalized.context.offenseTeamId, 'HOME');
  assert.equal(normalized.context.defenseTeamId, 'AWAY');
  assert.deepEqual(normalized.setup.order, ['pg', 'sg']);
  assert.equal(normalized.setup.players.pg.hasBall, true);
  assert.equal(normalized.setup.players.sg.position, 'SG');

  const frameTimestamps = normalized.timeline.frames.map(frame => frame.timestamp);
  assert.equal(frameTimestamps[0], 0);
  assert.equal(frameTimestamps.at(-1), 800);
  assert.ok(frameTimestamps.includes(400));
  assert.ok(frameTimestamps.includes(580));
  assert.ok(frameTimestamps.includes(600));
  assert.ok(frameTimestamps.includes(760));
  assert.equal(normalized.timeline.frames[0].players.pg.x, 40);
  const passAt400 = normalized.timeline.frames.find(frame => frame.timestamp === 400);
  const passAt600 = normalized.timeline.frames.find(frame => frame.timestamp === 600);
  assert.equal(passAt400?.passes?.[0]?.fromId, 'pg');
  assert.equal(passAt600?.passes?.[0]?.toId, 'pg');
  assert.ok(
    normalized.timeline.frames.some(frame => (frame.actions || []).some(action => action.action === 'shoot'))
  );

  assert.equal(normalized.terminal.shot.points, 2);
  assert.equal(normalized.terminal.shot.shooterId, 'pg');
  assert.equal(normalized.terminal.shot.timestamp, 800);
  assert.equal(normalized.terminal.rebound, null);
});


test('normalizeTurn infers passes and fast break metadata', async () => {
  const { normalizeTurn } = await normalizerPromise;

  const turn = {
    id: 'turn-fb',
    possession_id: 'pos-fb',
    possession_team_id: 'AWAY',
    fast_break: true,
    result_type: 'FAST_BREAK',
    shooter_id: 'wing',
    points: 2,
    animations: [
      {
        playerId: 'pgA',
        teamId: 'AWAY',
        hasBallAtStep: [true, true, false],
        movement: [
          { timestamp: 0, coords: { x: 60, y: 25 }, action: 'handle_ball' },
          { timestamp: 300, coords: { x: 70, y: 25 }, action: 'pass' },
          { timestamp: 700, coords: { x: 82, y: 25 }, action: 'trail' },
        ],
      },
      {
        playerId: 'wing',
        teamId: 'AWAY',
        movement: [
          { timestamp: 0, coords: { x: 64, y: 30 }, action: 'sprint' },
          { timestamp: 300, coords: { x: 72, y: 26 }, action: 'receive' },
          { timestamp: 700, coords: { x: 90, y: 25 }, action: 'shoot' },
        ],
      },
      {
        playerId: 'ball',
        hasBallAtStep: [true, false, false],
        movement: [
          { timestamp: 0, coords: { x: 60, y: 25 }, action: 'handle_ball' },
          { timestamp: 300, coords: { x: 72, y: 26 }, action: 'receive' },
          { timestamp: 700, coords: { x: 90, y: 25 }, action: 'shoot' },
        ],
      },
    ],
  };

  const normalized = normalizeTurn(turn, baseSimData());

  assert.equal(normalized.context.offenseTeamId, 'AWAY');
  assert.equal(normalized.context.fastBreak, true);
  assert.equal(normalized.timeline.passes.length, 1);
  assert.equal(normalized.timeline.passes[0].source, 'inferred');
  assert.equal(normalized.timeline.passes[0].fromId, 'pgA');
  assert.equal(normalized.timeline.passes[0].toId, 'wing');
  assert.ok(normalized.timeline.frames.some(frame => (frame.passes || []).length === 1));
  assert.equal(normalized.terminal.shot.fastBreak, true);
});


test('normalizeTurn captures offensive rebound context', async () => {
  const { normalizeTurn } = await normalizerPromise;

  const turn = {
    id: 'turn-or',
    possession_id: 'pos-or',
    possession_team_id: 'HOME',
    result_type: 'MAKE',
    text: 'SF misses, PF cleans it up.',
    shooter_id: 'pf',
    rebounder_id: 'pf',
    rebound_team_id: 'HOME',
    rebound_outcome: 'OFFENSIVE_REBOUND',
    points: 2,
    animations: [
      {
        playerId: 'sf',
        teamId: 'HOME',
        hasBallAtStep: [true, true, false],
        movement: [
          { timestamp: 0, coords: { x: 48, y: 20 }, action: 'handle_ball' },
          { timestamp: 600, coords: { x: 68, y: 22 }, action: 'shoot' },
          { timestamp: 900, coords: { x: 70, y: 23 }, action: 'rebound' },
        ],
      },
      {
        playerId: 'pf',
        teamId: 'HOME',
        movement: [
          { timestamp: 0, coords: { x: 52, y: 28 }, action: 'box_out' },
          { timestamp: 600, coords: { x: 66, y: 26 }, action: 'crash' },
          { timestamp: 900, coords: { x: 68, y: 24 }, action: 'rebound' },
          { timestamp: 1100, coords: { x: 70, y: 23 }, action: 'shoot' },
        ],
      },
      {
        playerId: 'ball',
        hasBallAtStep: [true, false, false, false],
        movement: [
          { timestamp: 0, coords: { x: 48, y: 20 }, action: 'handle_ball' },
          { timestamp: 600, coords: { x: 90, y: 25 }, action: 'shoot' },
          { timestamp: 900, coords: { x: 68, y: 24 }, action: 'rebound' },
          { timestamp: 1100, coords: { x: 90, y: 25 }, action: 'shoot' },
        ],
      },
    ],
  };

  const normalized = normalizeTurn(turn, baseSimData());

  assert.equal(normalized.terminal.rebound.rebounderId, 'pf');
  assert.equal(normalized.terminal.rebound.offensive, true);
  assert.equal(normalized.terminal.rebound.timestamp, 900);
  const finalFrame = normalized.timeline.frames[normalized.timeline.frames.length - 1];
  assert.equal(finalFrame.timestamp, 1100);
  assert.equal(finalFrame.duration, 0);
  assert.ok(finalFrame.actions.some(action => action.action === 'shoot'));
});
