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
    rimHoldMs: 800,
  },
  reboundPass: {
    moveDuration: 400,
    moveEase: 'Sine.easeInOut',
    passDuration: 150,
    passEase: 'Sine.easeInOut',
  },
};

const overrides =
  (typeof globalThis !== 'undefined' && globalThis.animation_config) || {};

export const animationConfig = {
  enableBallTween: overrides.enableBallTween ?? defaults.enableBallTween,
  pass: { ...defaults.pass, ...(overrides.pass || {}) },
  inbound: { ...defaults.inbound, ...(overrides.inbound || {}) },
  kickout: { ...defaults.kickout, ...(overrides.kickout || {}) },
  steal: { ...defaults.steal, ...(overrides.steal || {}) },
  freeThrow: { ...defaults.freeThrow, ...(overrides.freeThrow || {}) },
  fastBreak: { ...defaults.fastBreak, ...(overrides.fastBreak || {}) },
  reboundPass: { ...defaults.reboundPass, ...(overrides.reboundPass || {}) },
};

export default animationConfig;
