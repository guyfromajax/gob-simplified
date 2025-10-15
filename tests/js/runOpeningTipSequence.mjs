/**
 * Test for opening tip animation sequence
 * Run with: node --loader ./tests/js/openingTipLoader.mjs tests/js/runOpeningTipSequence.mjs
 */

import { runOpeningTipSequence } from '../../FrontEnd/static/js/phaser/animation/openingTip.js';

function makeScene() {
  const tweenResults = [];
  return {
    tweens: {
      add: ({ targets, x, y, duration, ease, yoyo, onComplete, onStop }) => {
        const result = {
          targets: Array.isArray(targets) ? targets : [targets],
          x, y, duration, ease, yoyo
        };
        tweenResults.push(result);
        
        // Simulate tween completion
        if (Array.isArray(targets)) {
          targets.forEach(t => {
            if (x !== undefined) t.x = x;
            if (y !== undefined) t.y = y;
          });
        } else if (targets) {
          if (x !== undefined) targets.x = x;
          if (y !== undefined) targets.y = y;
        }
        
        if (onComplete) onComplete();
        return { stop: () => { if (onStop) onStop(); } };
      },
      killTweensOf: () => {},
    },
    time: { delayedCall: (ms, fn) => fn() },
    game: { config: { width: 400, height: 200 } },
    events: { emit: () => {} },
    tweenResults, // Expose for testing
  };
}

function createPlayerSprites() {
  // Create 10 player sprites (5 home + 5 away)
  const homeIds = ['home-pg', 'home-sg', 'home-sf', 'home-pf', 'home-c'];
  const awayIds = ['away-pg', 'away-sg', 'away-sf', 'away-pf', 'away-c'];
  const sprites = {};
  
  for (const id of homeIds) {
    sprites[id] = { playerId: id, x: 0, y: 0, team: 'home' };
  }
  for (const id of awayIds) {
    sprites[id] = { playerId: id, x: 0, y: 0, team: 'away' };
  }
  
  return sprites;
}

function makeBall() {
  return { 
    setPosition(x, y) { this.x = x; this.y = y; }, 
    setVisible() {}, 
    setDepth() {}, 
    x: 200, 
    y: 100 
  };
}

// Mock appendToTextScroll
const originalAppendToTextScroll = global.appendToTextScroll;
let textScrollCalled = false;
let textScrollContent = '';

// Test 1: Opening tip with home team winning
const scene1 = makeScene();
scene1.playerSprites = createPlayerSprites();
scene1.ball = makeBall();

const turnData1 = {
  result_type: 'OPENING_TIP',
  text: 'Lancaster wins the opening tip!',
  winner: 'Lancaster C',
  ball_landing_coords: { x: 55, y: 28 },
  animations: [
    // Home center jumps
    {
      playerId: 'home-c',
      action: 'TIP_JUMP',
      start: { x: 48, y: 25 },
      jumpCoords: { x: 48, y: 29 },
      end: { x: 48, y: 25 }
    },
    // Away center jumps
    {
      playerId: 'away-c',
      action: 'TIP_JUMP',
      start: { x: 52, y: 25 },
      jumpCoords: { x: 52, y: 29 },
      end: { x: 52, y: 25 }
    },
    // Home PG converges
    {
      playerId: 'home-pg',
      action: 'CONVERGE_ON_BALL',
      start: { x: 37, y: 25 },
      end: { x: 55, y: 28 }
    },
    // Home SG converges
    {
      playerId: 'home-sg',
      action: 'CONVERGE_ON_BALL',
      start: { x: 43, y: 15 },
      end: { x: 53, y: 26 }
    },
    // Home SF converges
    {
      playerId: 'home-sf',
      action: 'CONVERGE_ON_BALL',
      start: { x: 45, y: 38 },
      end: { x: 54, y: 30 }
    },
    // Home PF converges
    {
      playerId: 'home-pf',
      action: 'CONVERGE_ON_BALL',
      start: { x: 46, y: 19 },
      end: { x: 54, y: 27 }
    },
    // Away PG converges
    {
      playerId: 'away-pg',
      action: 'CONVERGE_ON_BALL',
      start: { x: 64, y: 25 },
      end: { x: 56, y: 29 }
    },
    // Away SG converges
    {
      playerId: 'away-sg',
      action: 'CONVERGE_ON_BALL',
      start: { x: 58, y: 13 },
      end: { x: 57, y: 27 }
    },
    // Away SF converges
    {
      playerId: 'away-sf',
      action: 'CONVERGE_ON_BALL',
      start: { x: 55, y: 38 },
      end: { x: 56, y: 31 }
    },
    // Away PF converges
    {
      playerId: 'away-pf',
      action: 'CONVERGE_ON_BALL',
      start: { x: 56, y: 20 },
      end: { x: 57, y: 28 }
    }
  ]
};

let completed1 = false;
await runOpeningTipSequence(scene1, {
  playerSprites: scene1.playerSprites,
  ballSprite: scene1.ball,
  turnData: turnData1,
  onComplete: () => {
    completed1 = true;
  }
});

// Verify results
const result1 = {
  completed: completed1,
  totalTweens: scene1.tweenResults.length,
  // Count jump tweens (should be 3: 2 centers + 1 ball)
  jumpTweens: scene1.tweenResults.filter(t => t.yoyo === true).length,
  // Count converge tweens (should be 9: 8 players + 1 ball)
  convergeTweens: scene1.tweenResults.filter(t => t.yoyo !== true).length,
  // Verify ball landed at correct spot
  ballPosition: {
    x: scene1.ball.x,
    y: scene1.ball.y
  },
  expectedBallPosition: {
    x: turnData1.ball_landing_coords.x * 4,
    y: (50 - turnData1.ball_landing_coords.y) * 4
  }
};

// Test 2: Opening tip with away team winning
const scene2 = makeScene();
scene2.playerSprites = createPlayerSprites();
scene2.ball = makeBall();

const turnData2 = {
  result_type: 'OPENING_TIP',
  text: 'Bentley-Truman wins the opening tip!',
  winner: 'Bentley-Truman C',
  ball_landing_coords: { x: 45, y: 30 },
  animations: [
    // Same structure but ball lands on away side
    {
      playerId: 'home-c',
      action: 'TIP_JUMP',
      start: { x: 48, y: 25 },
      jumpCoords: { x: 48, y: 29 },
      end: { x: 48, y: 25 }
    },
    {
      playerId: 'away-c',
      action: 'TIP_JUMP',
      start: { x: 52, y: 25 },
      jumpCoords: { x: 52, y: 29 },
      end: { x: 52, y: 25 }
    },
    // 8 CONVERGE_ON_BALL animations...
    { playerId: 'home-pg', action: 'CONVERGE_ON_BALL', start: { x: 37, y: 25 }, end: { x: 46, y: 31 } },
    { playerId: 'home-sg', action: 'CONVERGE_ON_BALL', start: { x: 43, y: 15 }, end: { x: 44, y: 28 } },
    { playerId: 'home-sf', action: 'CONVERGE_ON_BALL', start: { x: 45, y: 38 }, end: { x: 46, y: 32 } },
    { playerId: 'home-pf', action: 'CONVERGE_ON_BALL', start: { x: 46, y: 19 }, end: { x: 44, y: 29 } },
    { playerId: 'away-pg', action: 'CONVERGE_ON_BALL', start: { x: 64, y: 25 }, end: { x: 45, y: 30 } },
    { playerId: 'away-sg', action: 'CONVERGE_ON_BALL', start: { x: 58, y: 13 }, end: { x: 46, y: 29 } },
    { playerId: 'away-sf', action: 'CONVERGE_ON_BALL', start: { x: 55, y: 38 }, end: { x: 44, y: 31 } },
    { playerId: 'away-pf', action: 'CONVERGE_ON_BALL', start: { x: 56, y: 20 }, end: { x: 46, y: 30 } }
  ]
};

let completed2 = false;
await runOpeningTipSequence(scene2, {
  playerSprites: scene2.playerSprites,
  ballSprite: scene2.ball,
  turnData: turnData2,
  onComplete: () => {
    completed2 = true;
  }
});

const result2 = {
  completed: completed2,
  totalTweens: scene2.tweenResults.length,
  jumpTweens: scene2.tweenResults.filter(t => t.yoyo === true).length,
  convergeTweens: scene2.tweenResults.filter(t => t.yoyo !== true).length,
  ballPosition: {
    x: scene2.ball.x,
    y: scene2.ball.y
  },
  expectedBallPosition: {
    x: turnData2.ball_landing_coords.x * 4,
    y: (50 - turnData2.ball_landing_coords.y) * 4
  }
};

// Output results
console.log(JSON.stringify({
  test1_homeWins: result1,
  test2_awayWins: result2,
  assertions: {
    test1_completed: result1.completed === true,
    test1_hasJumpTweens: result1.jumpTweens === 3,
    test1_hasConvergeTweens: result1.convergeTweens === 9,
    test1_totalTweens: result1.totalTweens === 12,
    test1_ballAtCorrectPosition: 
      result1.ballPosition.x === result1.expectedBallPosition.x &&
      result1.ballPosition.y === result1.expectedBallPosition.y,
    test2_completed: result2.completed === true,
    test2_hasJumpTweens: result2.jumpTweens === 3,
    test2_hasConvergeTweens: result2.convergeTweens === 9,
    test2_totalTweens: result2.totalTweens === 12,
    test2_ballAtCorrectPosition:
      result2.ballPosition.x === result2.expectedBallPosition.x &&
      result2.ballPosition.y === result2.expectedBallPosition.y
  }
}, null, 2));

