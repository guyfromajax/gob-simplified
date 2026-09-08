export const ANNOUNCEMENT_FREEZE_HOLD_MS = 300;

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
    makeAnnouncementHoldMs: ANNOUNCEMENT_FREEZE_HOLD_MS,
    // Made shot rim hold in ballManager path (announcement hold)
    madeRimHoldMs: ANNOUNCEMENT_FREEZE_HOLD_MS,
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
    // FT result announcement hold; intentionally 2x the standard gameplay freeze.
    resultAnnouncementHoldMs: ANNOUNCEMENT_FREEZE_HOLD_MS * 2,
    // Made FT rim hold (non-final); announcement hold
    makeRimHoldMs: ANNOUNCEMENT_FREEZE_HOLD_MS * 2,
    // Missed FT "No Good" hold before rebound or next attempt
    missAnnouncementHoldMs: ANNOUNCEMENT_FREEZE_HOLD_MS * 2,
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
    makeAnnouncementHoldMs: ANNOUNCEMENT_FREEZE_HOLD_MS,
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
  heartbeat: {
    enabled: true,
    amplitudePx: 1.4, // Render-space drift in pixels (does not touch gameplay x/y)
    jitterPx: 0.2,
    // BPM mapping:
    // NG=1.00 -> minBpm, NG=0.01 -> maxBpm
    minBpm: 75,
    maxBpm: 750,
  },
  // Continuity-aware movement curves (defect 1). The backend stamps an INTENT per player per
  // step — ease_in / ease_out / ease_in_out — in step.start.movement_curve, and this table is
  // the only place those names become Phaser curves. A player with no entry renders linear,
  // which is deliberate: mid-journey steps MUST stay linear or a multi-step crossing pulses
  // once per step, which is worse than the constant velocity we have now.
  //
  // FOR JAMIE — three knobs, and the point is to see the extremes in one sitting:
  //   1. departureEasing false vs true. False is the doc's "arrival only" rule: players snap
  //      to full speed from a dead stop but decelerate into their destination. True also eases
  //      them up from rest. 23.1% of moving steps are departures, so this is a visible amount
  //      of the game, not a detail.
  //   2. strength. 'subtle' / 'standard' / 'assertive' below. Standard ships. Look at all
  //      three — this codebase's repeated failure has been TOO SUBTLE (the 1-inch heartbeat
  //      was invisible), so if standard reads as nothing the answer is assertive, not "easing
  //      does not work".
  //   3. enabled false restores linear everywhere for an A/B against today's build.
  movementCurve: {
    enabled: true,
    // false => option (a) in the brief: ease_in becomes linear and ease_in_out becomes a pure
    // arrival curve, so only decelerations are eased.
    departureEasing: true,
    strength: 'standard',
    strengths: {
      // Sine is the gentlest curve that is still a curve.
      subtle: { ease_in: 'Sine.easeIn', ease_out: 'Sine.easeOut', ease_in_out: 'Sine.easeInOut' },
      // Quad reads as a person starting and stopping rather than a sprite being interpolated.
      standard: { ease_in: 'Quad.easeIn', ease_out: 'Quad.easeOut', ease_in_out: 'Quad.easeInOut' },
      // Cubic is a hard plant. Likely too much for a drift, possibly right for a sprint.
      assertive: { ease_in: 'Cubic.easeIn', ease_out: 'Cubic.easeOut', ease_in_out: 'Cubic.easeInOut' },
    },
    linear: 'Linear',
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
    hack: {
      magInsidePx: 16,
      magOutsidePx: 8,
      chops: 2,
      foulRattleMult: 1.5,
      strikeFraction: 0.35,
    },
    idleWander: {
      radiusGrid: 1.0, // Max render-space drift radius (grid units); no gameplay coord change
      durationMs: 900, // Fallback when the backend omits a per-beat duration
      // PER-FAMILY IDLE KNOBS. The backend stamps a `family` on every idle_wander flourish and
      // the raw per-style amplitude; these dial it by eye without a backend round-trip.
      //
      // One grid unit is almost exactly one foot (the 100x50 grid maps to a 94ft x 50ft court),
      // so amplitudes are readable as real distances. Raw style amplitudes are jockey 0.6ft,
      // shuffle 1.0ft, jab 1.2ft, survey_rock 0.5ft — sized for players already travelling.
      //
      //   amplitudeScale  multiplies the backend amplitude. 0.6 = the -40% ship default for
      //                   still players, 1.0 = no reduction, 0.3 = -70%. Worth looking at all
      //                   three: the always-on heartbeat is ~1 inch and is invisible, so TOO
      //                   SUBTLE is the failure mode this codebase already has. If -40% reads
      //                   as nothing on screen the answer is to go up, not to conclude the
      //                   mechanism is broken.
      //   style           forces a style; null keeps the backend's pick (geography-aware on
      //                   HCO, a family default elsewhere). One of jockey | jab | shuffle |
      //                   survey_rock.
      byFamily: {
        // Half-court offense between beats. Keeps the geography-aware style the resolver
        // rolled — an inside player jockeys, a perimeter defender shuffles.
        // Half-court offense between beats, and DEAD BALL — those steps resolve through the
        // same emitter, so they arrive under this family. Keeps the geography-aware style the
        // resolver rolled: an inside player jockeys (~4in), a perimeter defender shuffles
        // (~7in), a perimeter off-ball player jabs (~9in).
        hco_still: { amplitudeScale: 0.6, style: null },
        // Free throw, the worst family at 82.1% still and the one the viewer stares at
        // hardest. survey_rock is a gentle lateral weight shift — ~3.5in here. Ten men on the
        // lane should look like they are waiting, which is small and slow, not restless.
        free_throw: { amplitudeScale: 0.6, style: 'survey_rock' },
        // Inbound, 66.7% still on the side and 60.0% on the baseline. Bodies jostling for
        // position off the ball, so jockey — a grounded lean at ~4in. The passer gets none.
        inbound: { amplitudeScale: 0.6, style: 'jockey' },
        // The zero-clock beat after a bucket. Players reset and breathe rather than jostle,
        // so survey_rock at ~3.5in.
        make_hold: { amplitudeScale: 0.6, style: 'survey_rock' },
        // Offensive rebound, 62.0% still. This is the one family where the men are LEANING ON
        // EACH OTHER — boxing out is a legs-and-hips contest, not a wait — so it gets the
        // widest amplitude of the set: jockey at scale 1.0, a full ~7in grounded lean rather
        // than the -40% still-player reduction. Anything smaller reads as ten men politely
        // watching a rebound. The putback shooter and the second rebounder are excluded in the
        // backend; the rattle hold is excluded by the 60ms floor.
        oreb: { amplitudeScale: 1.0, style: 'jockey' },
        // Full-court press break, 48.2% still. Off-ball men are shifting their feet waiting to
        // receive against pressure — live but stationary, so shuffle at the -40% default
        // (~7in raw, ~4in here). Smaller than OREB: nobody is leaning on anybody yet.
        fcp: { amplitudeScale: 0.6, style: 'shuffle' },
        // Half-court trap, 44.9% still. Same motion as the press break but in a tighter space,
        // so the same style one notch smaller — a trapped possession should not look busier
        // than a rebound.
        hct: { amplitudeScale: 0.5, style: 'shuffle' },
      },
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
  movementCurve: {
    ...defaults.movementCurve,
    ...(overrides.movementCurve || {}),
    strengths: {
      ...defaults.movementCurve.strengths,
      ...(overrides.movementCurve?.strengths || {}),
    },
  },
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
    hack: { ...defaults.flourish.hack, ...(overrides.flourish?.hack || {}) },
    idleWander: {
      ...defaults.flourish.idleWander,
      ...(overrides.flourish?.idleWander || {}),
      // Merged per family, so overriding one family's amplitudeScale doesn't drop the rest.
      byFamily: Object.fromEntries(
        Object.entries(defaults.flourish.idleWander.byFamily).map(([family, famDefaults]) => [
          family,
          { ...famDefaults, ...(overrides.flourish?.idleWander?.byFamily?.[family] || {}) },
        ]),
      ),
    },
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

/**
 * Map a backend movement-curve INTENT to a Phaser easing string.
 *
 * The backend stamps only the three eased cases; anything else — mid-journey, standing still,
 * an unrecognised name from a future backend — resolves to linear. Defaulting to linear rather
 * than to a curve is the safe direction: an unstamped mid-journey step that accidentally eased
 * would reintroduce the per-step pulsing this whole mechanism exists to avoid.
 *
 * @param {string|null|undefined} intent 'ease_in' | 'ease_out' | 'ease_in_out'
 * @returns {string} a Phaser ease name
 */
export function resolveMovementCurve(intent) {
  const cfg = animationConfig.movementCurve || {};
  const linear = cfg.linear || 'Linear';
  if (!cfg.enabled || !intent) return linear;
  const table = (cfg.strengths || {})[cfg.strength] || {};
  if (cfg.departureEasing === false) {
    // Option (a): decelerations only. A pure departure has nothing to ease, and a one-step
    // journey keeps its arrival half.
    if (intent === 'ease_in') return linear;
    if (intent === 'ease_in_out') return table.ease_out || linear;
  }
  return table[intent] || linear;
}

export default animationConfig;
