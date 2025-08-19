import { playTurnAnimation } from '../../FrontEnd/static/js/phaser/animation/turnAnimation.js';

function makeScene() {
  return {
    tweens: {
      add: ({ onUpdate, onComplete, onStop }) => {
        if (onUpdate) onUpdate();
        if (onComplete) onComplete();
        return { stop: () => { if (onStop) onStop(); } };
      },
      killTweensOf: () => {}
    },
    time: { delayedCall: (ms, fn) => fn() },
    game: { config: { width: 100, height: 50 } },
    playerSprites: {
      pg: { x: 0, y: 0, team: 'home', team_id: 'HOME' },
      sg: { x: 0, y: 0, team: 'home', team_id: 'HOME' },
      sf: { x: 0, y: 0, team: 'home', team_id: 'HOME' },
      pf: { x: 0, y: 0, team: 'home', team_id: 'HOME' },
      c: { x: 0, y: 0, team: 'home', team_id: 'HOME' },
      pgA: { x: 0, y: 0, team: 'away', team_id: 'AWAY' },
      sfA: { x: 0, y: 0, team: 'away', team_id: 'AWAY' },
      sgA: { x: 0, y: 0, team: 'away', team_id: 'AWAY' },
      pfA: { x: 0, y: 0, team: 'away', team_id: 'AWAY' },
      cA: { x: 0, y: 0, team: 'away', team_id: 'AWAY' }
    },
    playerInfo: {
      pg: { pos: 'PG', team_id: 'HOME', name: 'PG' },
      sg: { pos: 'SG', team_id: 'HOME', name: 'SG' },
      sf: { pos: 'SF', team_id: 'HOME', name: 'SF' },
      pf: { pos: 'PF', team_id: 'HOME', name: 'PF' },
      c: { pos: 'C', team_id: 'HOME', name: 'C' },
      pgA: { pos: 'PG', team_id: 'AWAY', name: 'PG A' },
      sfA: { pos: 'SF', team_id: 'AWAY', name: 'SF A' },
      sgA: { pos: 'SG', team_id: 'AWAY', name: 'SG A' },
      pfA: { pos: 'PF', team_id: 'AWAY', name: 'PF A' },
      cA: { pos: 'C', team_id: 'AWAY', name: 'C A' }
    },
    nameToId: { PG: 'pg', C: 'c', Rebounder: 'c' }
  };
}

const simData = { home_team_id: 'HOME', away_team_id: 'AWAY' };

function createBallSprite() {
  return {
    setPosition(x, y) { this.x = x; this.y = y; },
    setVisible() {},
    setDepth() {},
  };
}

// Putback make should trigger inbound setup
{
  const scene = makeScene();
  const ballSprite = createBallSprite();
  const turnData = {
    starting_possession_team_id: 'HOME',
    possession_team_id: 'HOME',
    result_type: 'MISS',
    rebounder_player_id: 'c',
    animations: [],
    events: [{ event_type: 'PUTBACK_ATTEMPT', shooterId: 'c', result: 'MAKE', duration: 0 }]
  };
  await playTurnAnimation({ scene, simData, playerSprites: scene.playerSprites, turnData, ballSprite });
  var inboundSetup = scene.ballAttachedToPlayerId === 'pgA';
}

// Putback miss should trigger rebound animation attaching ball to rebounderId
let reboundAttached;
{
  const scene = makeScene();
  const ballSprite = createBallSprite();
  const turnData = {
    starting_possession_team_id: 'HOME',
    possession_team_id: 'HOME',
    result_type: 'MISS',
    rebounder_player_id: 'c',
    animations: [],
    events: [{ event_type: 'PUTBACK_ATTEMPT', shooterId: 'c', result: 'MISS', duration: 0, rebound: { rebounderId: 'pg', ballSpot: { x: 0, y: 0 } } }]
  };
  await playTurnAnimation({ scene, simData, playerSprites: scene.playerSprites, turnData, ballSprite });
  reboundAttached = scene.ballAttachedToPlayerId;
}

// Kickout reset should attach ball to PG and start new turn
let kickoutResult;
{
  const scene = makeScene();
  const ballSprite = createBallSprite();
  scene.startNextHalfCourtOffense = () => { scene.newTurn = true; };
  const turnData = {
    starting_possession_team_id: 'HOME',
    possession_team_id: 'HOME',
    result_type: 'MISS',
    rebounder_player_id: 'c',
    animations: [],
    events: [{ event_type: 'KICKOUT_RESET', rebounderId: 'c', pgId: 'pg', pass: { fromCoords: { x: 0, y: 0 }, toCoords: { x: 1, y: 1 }, duration: 0 } }]
  };
  await playTurnAnimation({ scene, simData, playerSprites: scene.playerSprites, turnData, ballSprite });
  kickoutResult = { attached: scene.ballAttachedToPlayerId, newTurn: scene.newTurn === true };
}

console.log(JSON.stringify({ inboundSetup, reboundAttached, kickoutResult }));
