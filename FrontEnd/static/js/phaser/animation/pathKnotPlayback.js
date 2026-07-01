/**
 * POS_O multi-knot drive playback helpers (Phase 6).
 *
 * Backend stamps ``advance_trigger.metadata.path_knots`` as
 * [start, meet, shimmy, shot_spot] and optional
 * ``path_segment_game_seconds`` [t_start→meet, t_meet→shimmy, t_shimmy→rim].
 * The gate player tweens through each segment instead of a single start→end line.
 */

/**
 * @param {import("./animationStepSchema.js").GridCoord|null|undefined} coord
 * @returns {import("./animationStepSchema.js").GridCoord|null}
 */
export function normalizeGridCoord(coord) {
  if (!coord || !Number.isFinite(Number(coord.x)) || !Number.isFinite(Number(coord.y))) {
    return null;
  }
  return { x: Number(coord.x), y: Number(coord.y) };
}

/**
 * @param {import("./animationStepSchema.js").GridCoord} a
 * @param {import("./animationStepSchema.js").GridCoord} b
 */
export function gridDistance(a, b) {
  return Math.hypot(Number(b.x) - Number(a.x), Number(b.y) - Number(a.y));
}

/**
 * Resolve sequential waypoint targets from backend path knots.
 * Anchors the path to the step's rendered start coord.
 *
 * @param {import("./animationStepSchema.js").GridCoord} startCoord
 * @param {import("./animationStepSchema.js").GridCoord[]} knots
 * @returns {import("./animationStepSchema.js").GridCoord[]|null}
 */
export function resolvePathKnotWaypoints(startCoord, knots) {
  const start = normalizeGridCoord(startCoord);
  if (!start || !Array.isArray(knots) || knots.length < 2) {
    return null;
  }
  const normalized = knots.map((k) => normalizeGridCoord(k)).filter(Boolean);
  if (normalized.length < 2) {
    return null;
  }
  // Skip knots[0] — use live step start; tween through meet → shimmy → rim.
  return normalized.slice(1);
}

/**
 * @param {import("./animationStepSchema.js").GridCoord} startCoord
 * @param {import("./animationStepSchema.js").GridCoord[]} waypoints
 * @param {number} totalDurationMs
 * @param {number[]|null|undefined} segmentGameSeconds
 * @param {number} clockSecondMs
 * @returns {number[]}
 */
export function computePathSegmentDurationsMs(
  startCoord,
  waypoints,
  totalDurationMs,
  segmentGameSeconds,
  clockSecondMs,
) {
  if (
    Array.isArray(segmentGameSeconds)
    && segmentGameSeconds.length === waypoints.length
    && segmentGameSeconds.every((s) => Number.isFinite(Number(s)) && Number(s) >= 0)
  ) {
    return segmentGameSeconds.map((s) =>
      Math.max(50, Math.round(Number(s) * clockSecondMs)),
    );
  }

  const dists = [];
  let prev = startCoord;
  for (const wp of waypoints) {
    dists.push(gridDistance(prev, wp));
    prev = wp;
  }
  const totalDist = dists.reduce((sum, d) => sum + d, 0) || 1;
  return dists.map((d) =>
    Math.max(50, Math.round(totalDurationMs * (d / totalDist))),
  );
}

/**
 * Chain linear tweens through POS_O waypoints.
 *
 * @param {Phaser.Scene} scene
 * @param {Phaser.GameObjects.Sprite} sprite
 * @param {import("./animationStepSchema.js").GridCoord} startCoord
 * @param {import("./animationStepSchema.js").GridCoord[]} waypoints
 * @param {number} totalDurationMs
 * @param {number[]|null|undefined} segmentGameSeconds
 * @param {number} width
 * @param {number} height
 * @param {number} clockSecondMs
 * @param {(scene: Phaser.Scene, sprite: Phaser.GameObjects.Sprite, endCoord: import("./animationStepSchema.js").GridCoord, durationMs: number, width: number, height: number) => Promise<void>} tweenOne
 */
export async function tweenPlayerThroughPathKnots(
  scene,
  sprite,
  startCoord,
  waypoints,
  totalDurationMs,
  segmentGameSeconds,
  width,
  height,
  clockSecondMs,
  tweenOne,
) {
  if (!scene || !sprite || !waypoints?.length) {
    return;
  }
  const durations = computePathSegmentDurationsMs(
    startCoord,
    waypoints,
    totalDurationMs,
    segmentGameSeconds,
    clockSecondMs,
  );
  for (let i = 0; i < waypoints.length; i += 1) {
    await tweenOne(scene, sprite, waypoints[i], durations[i], width, height);
    sprite.gridX = waypoints[i].x;
    sprite.gridY = waypoints[i].y;
  }
}
