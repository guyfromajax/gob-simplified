const { test } = require('node:test');
const assert = require('node:assert/strict');

const runnerPromise = import('../possession/PossessionRunner.js');
const statePromise = import('../../state/gameStateMachine.js');

function createTimelineRecorder() {
  const records = [];
  const listeners = new Map();
  const timeline = {
    add(config) {
      records.push(config);
      return this;
    },
    once(event, callback) {
      if (!listeners.has(event)) listeners.set(event, []);
      listeners.get(event).push(callback);
      return this;
    },
    play() {
      for (const config of records) {
        config.onStart?.();
        config.onComplete?.();
      }
      (listeners.get('complete') || []).forEach((cb) => cb());
    },
  };
  return { timeline, records, listeners };
}

function createTweenStub(invocations) {
  return (config) => {
    invocations.push(config);
    config.onStart?.();
    config.onUpdate?.();
    if (config.targets) {
      if (Array.isArray(config.targets)) {
        config.targets.forEach((target) => {
          if (typeof config.x === 'number') target.x = config.x;
          if (typeof config.y === 'number') target.y = config.y;
        });
      } else {
        if (typeof config.x === 'number') config.targets.x = config.x;
        if (typeof config.y === 'number') config.targets.y = config.y;
      }
    }
    config.onComplete?.();
    return { once() {} };
  };
}

test('PossessionRunner schedules frames and emits debug events', async () => {
  globalThis.DEBUG_ANIM = true;
  const { PossessionRunner } = await runnerPromise;
  const { States, transitions } = await statePromise;

  const timelineRecorder = createTimelineRecorder();
  const tweenCalls = [];
  const scene = {
    tweens: {
      createTimeline() {
        return timelineRecorder.timeline;
      },
      add: createTweenStub(tweenCalls),
    },
    events: {
      emitted: [],
      emit(event, payload) {
        this.emitted.push({ event, payload });
      },
    },
    game: { config: { width: 100, height: 50 } },
  };

  const stateMachine = {
    state: States.Inbound,
    transitionCalls: [],
    transition(next, payload = {}) {
      const allowed = transitions[this.state] || [];
      if (!allowed.includes(next)) {
        throw new Error(`Invalid transition: ${this.state} -> ${next}`);
      }
      this.transitionCalls.push({ next, payload, from: this.state });
      this.state = next;
    },
    is(value) {
      return this.state === value;
    },
  };

  scene.stateMachine = stateMachine;

  const ballSprite = {
    setPosition(x, y) {
      this.x = x;
      this.y = y;
    },
    setVisible() {},
    setDepth() {},
  };

  const playerSprites = {
    pg: {
      playerId: 'pg',
      setPosition(x, y) {
        this.x = x;
        this.y = y;
      },
    },
    sg: {
      playerId: 'sg',
      setPosition(x, y) {
        this.x = x;
        this.y = y;
      },
    },
  };

  const helperCalls = {
    attach: [],
    passes: [],
    shots: [],
  };

  const graph = {
    context: {
      possessionId: 'pos-1',
      turnId: 'turn-1',
      turnIndex: 0,
    },
    setup: {
      ball: { ownerId: 'pg', coords: { x: 20, y: 20 } },
      players: {
        pg: { x: 20, y: 20, hasBall: true, teamId: 'HOME', position: 'PG' },
        sg: { x: 40, y: 22, teamId: 'HOME', position: 'SG' },
      },
      order: ['pg', 'sg'],
    },
    timeline: {
      frames: [
        {
          timestamp: 0,
          duration: 200,
          players: {
            pg: { x: 24, y: 20, hasBall: true, teamId: 'HOME', position: 'PG' },
            sg: { x: 44, y: 24, teamId: 'HOME', position: 'SG' },
          },
        },
        {
          timestamp: 200,
          duration: 200,
          players: {
            pg: { x: 40, y: 20, hasBall: false, teamId: 'HOME', position: 'PG' },
            sg: { x: 48, y: 24, hasBall: true, teamId: 'HOME', position: 'SG' },
          },
          passes: [
            { timestamp: 200, fromId: 'pg', toId: 'sg', duration: 180 },
          ],
        },
        {
          timestamp: 400,
          duration: 200,
          players: {
            sg: { x: 60, y: 25, hasBall: true, teamId: 'HOME', position: 'SG' },
          },
          actions: [
            { playerId: 'sg', action: 'shoot' },
          ],
        },
      ],
    },
    terminal: {
      shot: { outcome: 'MAKE', shooterId: 'sg', points: 2 },
      rebound: null,
      turnover: null,
    },
  };

  const config = {
    helpers: {
      attachBallToPlayer(sceneArg, ballArg, spriteArg) {
        helperCalls.attach.push(spriteArg.playerId);
      },
      runPass(sceneArg, payload) {
        helperCalls.passes.push(payload);
        return Promise.resolve();
      },
      shootBall(opts) {
        helperCalls.shots.push(opts);
        return Promise.resolve();
      },
      animateRebound() {
        return Promise.resolve();
      },
    },
    turnIndex: 0,
    createTimeline() {
      return timelineRecorder.timeline;
    },
  };

  const runner = new PossessionRunner({
    scene,
    ballSprite,
    playerSprites,
    graph,
    config,
  });

  await runner.run();

  assert.equal(helperCalls.attach[0], 'pg');
  assert.equal(helperCalls.passes.length, 1);
  assert.equal(helperCalls.passes[0].fromId, 'pg');
  assert.equal(helperCalls.passes[0].toId, 'sg');
  assert.equal(helperCalls.shots.length, 1);
  assert.equal(helperCalls.shots[0].shooterId, 'sg');

  assert.equal(timelineRecorder.records.length, graph.timeline.frames.length);
  assert.ok(scene.events.emitted.some((evt) => evt.event === 'possessionRunner:step'));
  assert.ok(scene.events.emitted.some((evt) => evt.event === 'possessionRunner:postStep'));
  assert.ok(scene.events.emitted.some((evt) => evt.event === 'possessionRunner:transition'));

  const transitionNames = stateMachine.transitionCalls.map((entry) => entry.next);
  assert.deepEqual(transitionNames, ['HalfCourt', 'ShotAttempt', 'Inbound']);

  globalThis.DEBUG_ANIM = false;
});
