import { animateRebound } from '../../FrontEnd/static/js/phaser/animation/ballManager.js';
import { transitionFastBreakState } from '../../FrontEnd/static/js/phaser/animation/fastBreakStateHelpers.js';
import { createGameStateMachine, States } from '../../FrontEnd/static/js/phaser/state/gameStateMachine.js';

function makeScene() {
  const scene = {
    tweens: {
      add: ({ targets, x, y, onUpdate, onComplete, onStop }) => {
        const applyPosition = (target) => {
          if (!target) return;
          if (typeof x === 'number') target.x = x;
          if (typeof y === 'number') target.y = y;
        };
        if (Array.isArray(targets)) {
          targets.forEach(applyPosition);
        } else {
          applyPosition(targets);
        }
        if (onUpdate) onUpdate();
        if (onComplete) onComplete();
        return {
          once: () => {},
          stop: () => {
            if (onStop) onStop();
          }
        };
      },
      killTweensOf: () => {},
      createTimeline: () => {
        const timeline = {
          steps: [],
          once(event, handler) {
            if (event === 'complete') this._complete = handler;
          },
          add(config) {
            this.steps.push(config);
            return this;
          },
          play() {
            for (const cfg of this.steps) {
              const target = cfg.targets;
              if (target) {
                if (typeof cfg.x === 'number') target.x = cfg.x;
                if (typeof cfg.y === 'number') target.y = cfg.y;
              }
              if (cfg.onComplete) cfg.onComplete();
            }
            if (this._complete) this._complete();
          },
          stop() {}
        };
        return timeline;
      }
    },
    time: { delayedCall: (ms, cb) => { if (typeof cb === 'function') cb(); } },
    events: { emit: () => {} },
    game: { config: { width: 100, height: 50 } },
    stateMachine: createGameStateMachine(States.Rebound),
    skipToEnd: false,
    possessionFlipInProgress: false,
  };
  return scene;
}

function createBallSprite() {
  return {
    setPosition(x, y) { this.x = x; this.y = y; },
    setVisible() {},
    setDepth() {},
  };
}

function createPlayer(playerId, team) {
  return {
    playerId,
    team,
    team_id: team.toUpperCase(),
    x: 0,
    y: 0,
  };
}

const scene = makeScene();
const ballSprite = createBallSprite();
scene.ballSprite = ballSprite;

const playerSprites = {
  outlet: createPlayer('outlet', 'home'),
  wing: createPlayer('wing', 'home'),
};
scene.playerSprites = playerSprites;

const simData = {
  home_team_id: 'HOME',
  away_team_id: 'AWAY',
  turns: [
    { id: 'turn-0', result_type: 'MISS' },
    {
      id: 'turn-1',
      fast_break: true,
      result_type: 'FAST_BREAK',
      roles: { outlet_passer: 'outlet', outlet_receiver: 'wing' },
      animations: [
        { playerId: 'wing', start: { x: 40, y: 20 }, movement: [] },
        { playerId: 'outlet', start: { x: 30, y: 25 }, movement: [] },
      ],
      passes: [],
    },
  ],
};
scene.simData = simData;
scene.currentTurn = 0;

await animateRebound({
  scene,
  ballSprite,
  playerSprites,
  animations: [],
  rebounderId: 'outlet',
  ballSpot: { x: 30, y: 25 },
});

const afterReboundState = scene.stateMachine.state;

scene.currentTurn = 1;
let error = null;
let afterOutletState = scene.stateMachine.state;
try {
  transitionFastBreakState(scene, States.FastBreakOutlet, { debugStepIndex: 0 });
  afterOutletState = scene.stateMachine.state;
  transitionFastBreakState(scene, States.FastBreak, { debugStepIndex: 1 });
} catch (err) {
  error = err?.message || String(err);
}

const finalState = scene.stateMachine.state;

console.log(JSON.stringify({ afterReboundState, afterOutletState, finalState, error }));
