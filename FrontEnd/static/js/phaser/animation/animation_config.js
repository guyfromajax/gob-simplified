const defaults = {
  // Enable ball tweening by default; tests can override via global animation_config
  enableBallTween: true,
  pass: {
    duration: 150,
    easing: 'Sine.easeInOut',
    arc: null,
  },
  possession: {
    targetFrameMs: 320,
    minFrameMs: 120,
    maxFrameMs: 900,
    minDurationScale: 0.35,
    maxDurationScale: 6,
    minPassDurationMs: 160,
    maxPassDurationMs: 750,
  },
  inbound: {
    duration: 150,
    easing: 'Sine.easeInOut',
    arc: null,
    // Hold after ball placed with inbound passer. SIP only (single application);
    // BIP no longer holds here (May 2026 responsiveness update).
    holdAfterPlaceMs: 200,
  },
  shot: {
    // Rim hold: ball at rim after make/miss (HCO normal)
    rimHoldMs: 1000,
    // After "It's Good!" / AND-1 before inbound (announcement hold)
    makeAnnouncementHoldMs: 1000,
    // Made shot rim hold in ballManager path (announcement hold)
    madeRimHoldMs: 1000,
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
  outletSetup: {
    playerMoveMs: 800,
    passMs: 300,
    easing: 'Sine.easeInOut',
  },
  rebound: {
    // Area (in grid units) around the rim where missed shots can land
    bounceArea: { x: 6, y: 6 },
    // Duration in ms for players to collapse toward the rebound spot
    playerMoveMs: 300,
    // Delay before possession is considered secured
    attachDelayMs: 500,
  },
  freeThrow: {
    lineupMoveMs: 800,
    shooterPrepMs: 400,
    shotMs: 500,
    useArc: false,
    arcHeight: 40,
    rimHoldMs: 300,
    // Made FT rim hold (non-final); announcement hold
    makeRimHoldMs: 1000,
  },
  fastBreak: {
    sprintSpeed: 1.5, // multiplier
    laneSpacing: 6,
    passMs: 250,
    outletMoveMs: 300, // duration for outlet receiver advance
    shotMs: 350, // synced to 1 game second (350ms = 1 game s)
    arcHeight: 60,
    // Time to hold the ball at the rim after a made fast break shot
    rimHoldMs: 1000,
    // Announcement hold after "It's Good!" (FB make)
    makeAnnouncementHoldMs: 1000,
    // Announcement hold after "Great Stop!" (FB defensive stop); 0 game time
    defensiveStopHoldMs: 500,
    // Rim Runner outlet-denied + hold-up: shared phase for BH/receiver + AG horizontal drifts.
    // Floors wall-clock so a tiny primary move doesn't collapse to 50ms (warp) for everyone.
    agDriftSharedPhaseMinMs: 520,
  },
  offensiveRebound: { pauseMs: 1000 },
  putback: { duration: 500, easing: 'Sine.easeInOut' },
  finalTurn: {
    holdClockOutMs: 1800,
    holdFinalShotMs: 2000, // Hold at rim (make) or bounce (miss) before quarter end; no BIP/rebound
    // Final Turn UESS hold: BH holds in alignment until scoreboard reaches this remaining time.
    latePassTargetSecOutside: 3,
    latePassTargetSecAttack: 4,
    alignment: { ease: 'Linear' },
    moveDelayMs: 0, // Optional delay before BH/shooter movement (e.g. 1500 for "3–5 seconds remaining" feel)
  },
  quickFoul: {
    sprintSpeedMultiplier: 1.5,
    maxGridRadius: 2,
  },
  heartbeat: {
    enabled: true,
    amplitudePx: 1.4, // Render-space drift in pixels (does not touch gameplay x/y)
    jitterPx: 0.2,
    // BPM mapping:
    // NG=1.00 -> minBpm, NG=0.01 -> maxBpm
    minBpm: 75,
    maxBpm: 750,
  },
  // Flourishes: in-place "micro-movements" rendered in RENDER SPACE only (like
  // the heartbeat — never mutates gameplay x/y). Per-kind defaults used when the
  // backend Flourish payload omits a field. See flourishes.js + animationStepSchema.js.
  flourish: {
    reachIn: {
      amplitudePx: 11, // Lunge distance toward the ball (render-space px)
      durationMs: 450, // Full out-and-back (yoyo)
      ease: 'Back.easeOut',
    },
    pumpFake: {
      amplitudeGrid: 2, // Out 2 grid on Y, yoyo returns 2 grid to shooter
      durationMs: 380, // 190ms out + 190ms back (wall time)
      ease: 'Quad.easeOut',
    },
    rattle: {
      amplitudePx: 4,
      cycleMs: 120,
      cycles: 3,
      ease: 'Sine.easeInOut',
    },
    gather: {
      amplitudeGrid: 0.6, // Subtle square-up dip (render space; no gameplay coord change)
      durationMs: 400, // ~MICRO_FLOURISH_BEAT_T at 1× playback
      ease: 'Quad.easeOut',
    },
    fumble: {
      magPx: 11,
      freqHz: 6,
      durationMs: 660,
    },
    idleWander: {
      radiusGrid: 1.0, // Max render-space drift radius (grid units); no gameplay coord change
      durationMs: 900, // Fallback when the backend omits a per-beat duration
    },
  },
  dunk: {
    risePx: 22,
    rattleMagPx: 6,
    rattleMs: 280,
    ballRaise: 0.35, // fraction of player sprite display height above head at apex
  },
  possession: {
    msPerTick: 1,
    minFrameDurationMs: 120,
    minPassDurationMs: 150,
  },
};

const overrides =
  (typeof globalThis !== 'undefined' && globalThis.animation_config) || {};

export const FT_BETWEEN_SHOTS_DELAY_MS =
  overrides.FT_BETWEEN_SHOTS_DELAY_MS ?? 0;

export const FAST_BREAK_END_PAUSE_MS =
  overrides.FAST_BREAK_END_PAUSE_MS ?? 3000;

export const animationConfig = {
  enableBallTween: overrides.enableBallTween ?? defaults.enableBallTween,
  pass: { ...defaults.pass, ...(overrides.pass || {}) },
  possession: { ...defaults.possession, ...(overrides.possession || {}) },
  inbound: { ...defaults.inbound, ...(overrides.inbound || {}) },
  shot: { ...defaults.shot, ...(overrides.shot || {}) },
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
  finalTurn: { ...defaults.finalTurn, ...(overrides.finalTurn || {}) },
  heartbeat: { ...defaults.heartbeat, ...(overrides.heartbeat || {}) },
  flourish: {
    reachIn: { ...defaults.flourish.reachIn, ...(overrides.flourish?.reachIn || {}) },
    pumpFake: { ...defaults.flourish.pumpFake, ...(overrides.flourish?.pumpFake || {}) },
    rattle: { ...defaults.flourish.rattle, ...(overrides.flourish?.rattle || {}) },
    gather: { ...defaults.flourish.gather, ...(overrides.flourish?.gather || {}) },
    fumble: { ...defaults.flourish.fumble, ...(overrides.flourish?.fumble || {}) },
    idleWander: { ...defaults.flourish.idleWander, ...(overrides.flourish?.idleWander || {}) },
  },
  dunk: { ...defaults.dunk, ...(overrides.dunk || {}) },
  possession: {
    msPerTick: overrides.possession?.msPerTick ?? defaults.possession.msPerTick,
    minFrameDurationMs:
      overrides.possession?.minFrameDurationMs ??
      overrides.possession?.minDurationMs ??
      defaults.possession.minFrameDurationMs,
    minPassDurationMs:
      overrides.possession?.minPassDurationMs ??
      overrides.possession?.minFrameDurationMs ??
      overrides.possession?.minDurationMs ??
      defaults.possession.minPassDurationMs,
  },
};

animationConfig.outletSetup = {
  playerMoveMs:
    overrides.outletSetup?.playerMoveMs ?? defaults.outletSetup.playerMoveMs,
  passMs:
    overrides.outletSetup?.passMs ?? defaults.outletSetup.passMs,
  easing:
    overrides.outletSetup?.easing ?? animationConfig.pass.easing,
};

export default animationConfig;
