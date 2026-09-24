/**
 * Player sprite depth ordering — PURE policy, no Phaser dependency.
 *
 * WHY THIS EXISTS
 * ---------------
 * Every player container is created at depth 1 and never changed
 * (createHeadshotMarkerV2.js:150, createPhaserPlayer.js:58/:166; nothing calls bringToTop or
 * sortChildren). All ten players therefore share one depth, so when two sprites merge, which
 * one draws on top falls back to scene insertion order — arbitrary, and unrelated to the play.
 * That is why a merged pair reads as mush instead of as one player standing in front of another.
 *
 * This does NOT remove overlap. Overlap is often correct basketball and stays. It makes an
 * overlapping pair legible.
 *
 * ORIENTATION IS DERIVED, NOT ASSUMED
 * -----------------------------------
 * utils/gridToPixels.js: `pixelY = ((50 - y) / 50) * height`. So grid y=0 maps to the BOTTOM of
 * the canvas (nearest the viewer) and y=50 to the top. **Lower grid y must draw ON TOP**, which
 * is why the y term is `(COURT_MAX_Y - gridY)`. Verified against a captured frame — see
 * reports/depth-ordering.md.
 *
 * NO NEW GAME STATE. Everything here is read from the backend payload that already exists:
 * `hasBallAtStep` (authored in BackEnd/models/animator.py) and the per-step `action`. UESS is
 * preserved because draw order is rendering, not logic.
 */

/** Court height in grid units. Mirrors gridToPixels' constant. */
export const COURT_MAX_Y = 50;

/** Floor for every player depth. Chosen above the court//background layers and far below the
 *  ball (BALL_DEPTH = 1000), so the whole player band sits between them. */
export const DEPTH_BASE = 100;

/** Grid-y weight. THE DOMINANT TERM — this is what makes the picture read as depth rather than
 *  as arbitrary layering. One grid unit nearer the viewer outranks every tie-break combined. */
export const DEPTH_PER_GRID_Y = 10;

/** Tie-break: offence over defence when two players are on effectively the same line. */
export const DEPTH_OFFENCE_BIAS = 3;

/** Tie-break: the step's ball owner over everyone else on effectively the same line. */
export const DEPTH_BALL_OWNER_BIAS = 5;

/** The highest depth any UNPROMOTED player can reach:
 *  DEPTH_BASE + COURT_MAX_Y * DEPTH_PER_GRID_Y + both biases = 100 + 500 + 3 + 5 = 608. */
export const DEPTH_BAND_MAX = DEPTH_BASE + COURT_MAX_Y * DEPTH_PER_GRID_Y
  + DEPTH_OFFENCE_BIAS + DEPTH_BALL_OWNER_BIAS;

/** Sub-mode (ii) only. Promoted players get their OWN band, strictly above every unpromoted
 *  player (DEPTH_BAND_MAX = 608) and strictly below the ball (BALL_DEPTH = 1000).
 *
 *  It is a separate band rather than a large additive bonus on purpose: an additive +1000 put
 *  the ball owner at 1508, i.e. ABOVE the ball, so the carrier occluded the ball he was
 *  holding. Measured during the build, not reasoned about after.
 *
 *  Promoted players stay y-ordered among themselves via the shallow slope, so two promoted
 *  players (owner + shooter) still read correctly against each other. */
export const DEPTH_PROMOTED_BASE = 650;
export const DEPTH_PROMOTED_PER_GRID_Y = 0.5;

/** Mirror of BALL_DEPTH in ballAnimationSimple.js:183 / ballTween.js:29. Named here so the
 *  invariant "every player depth < ball depth" is assertable in a unit test. */
export const BALL_DEPTH = 1000;

/** The two sub-modes the brief asks to be reported side by side. No default is recommended. */
export const DEPTH_MODE = Object.freeze({
  TIE_BREAK: "tie_break",
  HARD_PROMOTION: "hard_promotion",
});

/** Ball-owning actions. Identical set to `collision_separation.BALL_ACTIONS` on the backend and
 *  to the fallback inside the (previously dead) `turnAnimation.getStepBallHandlerId`. */
export const BALL_ACTIONS = Object.freeze([
  "handle_ball", "receive", "pass", "shoot", "drive",
]);

/**
 * The step's ball owner. SINGLE SOURCE — `turnAnimation.getStepBallHandlerId` now delegates here
 * instead of carrying a second copy (it was defined and never called).
 * `hasBallAtStep` first, then the action set.
 */
export function resolveStepBallOwnerId(animations, stepIndex) {
  if (!Array.isArray(animations)) return null;
  for (const anim of animations) {
    if (anim?.hasBallAtStep?.[stepIndex]) return anim.playerId;
  }
  for (const anim of animations) {
    const action = anim?.movement?.[stepIndex]?.action;
    if (BALL_ACTIONS.includes(action)) return anim.playerId;
  }
  return null;
}

/** The step's shooter, if the payload names one at this step. Read, never inferred. */
export function resolveStepShooterId(animations, stepIndex) {
  if (!Array.isArray(animations)) return null;
  for (const anim of animations) {
    if (anim?.movement?.[stepIndex]?.action === "shoot") return anim.playerId;
  }
  return null;
}

function depthFor({ gridY, isOffence, isBallOwner, isShooter, mode }) {
  if (mode === DEPTH_MODE.HARD_PROMOTION && (isBallOwner || isShooter)) {
    return DEPTH_PROMOTED_BASE + (COURT_MAX_Y - gridY) * DEPTH_PROMOTED_PER_GRID_Y;
  }
  let depth = DEPTH_BASE + (COURT_MAX_Y - gridY) * DEPTH_PER_GRID_Y;
  if (isOffence) depth += DEPTH_OFFENCE_BIAS;
  if (isBallOwner) depth += DEPTH_BALL_OWNER_BIAS;
  return depth;
}

/**
 * `Map<playerId, depth>` for one step.
 *
 * @param {object[]} animations   backend per-player animation entries
 * @param {number}   stepIndex    the step being drawn
 * @param {string}   offenseTeamId
 * @param {object}   playersById  `{ [playerId]: { team_id } }` — for the offence tie-break
 * @param {Map|object} [gridYById] OPTIONAL live grid-y override, keyed by player id. The
 *        per-frame applier passes the sprite's actual position so ordering is never stale
 *        mid-tween; omitted, the authored step coordinate is used.
 * @param {string}   [mode]       DEPTH_MODE.TIE_BREAK (default) or HARD_PROMOTION
 */
export function resolvePlayerDepths({
  animations,
  stepIndex = 0,
  offenseTeamId = null,
  playersById = {},
  gridYById = null,
  mode = DEPTH_MODE.TIE_BREAK,
} = {}) {
  const out = new Map();
  if (!Array.isArray(animations)) return out;

  const ballOwnerId = resolveStepBallOwnerId(animations, stepIndex);
  const shooterId = resolveStepShooterId(animations, stepIndex);
  const readOverride = (pid) => {
    if (!gridYById) return undefined;
    return gridYById instanceof Map ? gridYById.get(pid) : gridYById[pid];
  };

  for (const anim of animations) {
    const pid = anim?.playerId;
    if (pid === undefined || pid === null) continue;

    const override = readOverride(pid);
    const authored = anim?.movement?.[stepIndex]?.coords?.y;
    const gridY = Number.isFinite(override) ? override : authored;
    // NEVER INVENT A COORDINATE. A player with no usable y is left out of the map entirely and
    // the applier leaves his container alone, rather than being assigned a stand-in depth that
    // would silently order him against everyone else.
    if (!Number.isFinite(gridY)) continue;

    const teamId = playersById?.[pid]?.team_id;
    const isOffence = offenseTeamId != null && teamId != null && teamId === offenseTeamId;

    out.set(pid, depthFor({
      gridY,
      isOffence,
      isBallOwner: pid === ballOwnerId,
      isShooter: pid === shooterId,
      mode,
    }));
  }
  return out;
}
