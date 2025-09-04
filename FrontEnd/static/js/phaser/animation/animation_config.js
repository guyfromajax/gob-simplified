const defaults = {
  // Enable ball tweening by default; tests can override via global animation_config
  enableBallTween: true,
  pass: {
    duration: 150,
    easing: 'Sine.easeInOut',
    arc: null,
  },
  inbound: {
    duration: 150,
    easing: 'Sine.easeInOut',
    arc: null,
  },
  kickout: {
    duration: 300,
    easing: 'Sine.easeInOut',
    arc: null,
  },
  steal: {
    duration: 150,
    easing: 'Sine.easeInOut',
    arc: null,
  },
  rebound: {
    // Area (in grid units) around the rim where missed shots can land
    bounceArea: { x: 6, y: 6 },
    // Duration in ms for players to collapse toward the rebound spot
    playerMoveMs: 300,
    // Delay before possession is considered secured
    attachDelayMs: 1000,
  },
  freeThrow: {
    lineupMoveMs: 800,
    shooterPrepMs: 400,
    shotMs: 500,
    arcHeight: 40,
    rimHoldMs: 300,
  },
  fastBreak: {
    sprintSpeed: 1.5, // multiplier
    laneSpacing: 6,
    passMs: 250,
    shotMs: 500,
    arcHeight: 60,
    // Time to hold the ball at the rim after a made fast break shot
    rimHoldMs: 2000,
    // Extra pause after fast break sequence completes
    endPauseMs: 3000,
  },
  offensiveRebound: { pauseMs: 1000 },
  putback: { duration: 500, easing: 'Sine.easeInOut' },
};

const overrides =
  (typeof globalThis !== 'undefined' && globalThis.animation_config) || {};

export const animationConfig = {
  enableBallTween: overrides.enableBallTween ?? defaults.enableBallTween,
  pass: { ...defaults.pass, ...(overrides.pass || {}) },
  inbound: { ...defaults.inbound, ...(overrides.inbound || {}) },
  kickout: { ...defaults.kickout, ...(overrides.kickout || {}) },
  steal: { ...defaults.steal, ...(overrides.steal || {}) },
  rebound: {
    bounceArea: {
      ...defaults.rebound.bounceArea,
      ...(overrides.rebound?.bounceArea || {}),
    },
    playerMoveMs:
      overrides.rebound?.playerMoveMs ?? defaults.rebound.playerMoveMs,
    attachDelayMs:
      overrides.rebound?.attachDelayMs ?? defaults.rebound.attachDelayMs,
  },
  freeThrow: { ...defaults.freeThrow, ...(overrides.freeThrow || {}) },
  fastBreak: { ...defaults.fastBreak, ...(overrides.fastBreak || {}) },
  offensiveRebound: {
    ...defaults.offensiveRebound,
    ...(overrides.offensiveRebound || {}),
  },
  putback: { ...defaults.putback, ...(overrides.putback || {}) },
};

export default animationConfig;
