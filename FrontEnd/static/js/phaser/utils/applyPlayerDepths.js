/**
 * Thin Phaser applier for the pure policy in ./playerDepth.js.
 *
 * COVERAGE — WHY THIS INSTALLS ON THE SCENE UPDATE LOOP
 * -----------------------------------------------------
 * There is NO single per-step funnel. Eight animation paths each run their own step loop over
 * `playerSprites` (turnAnimation, animateGameTurns, AnimationEngine, HCOAnimationSystem,
 * PassAnimationSystem, ShotAnimationSystem, ReboundAnimationSystem, FreeThrowAnimationSystem),
 * so a per-step hook would have to be added eight times and would still miss any path added
 * later — partial coverage being the most likely way this disappoints.
 *
 * `scene.events.on("update", ...)` IS a universal funnel: it runs every frame regardless of
 * which system is driving, and it is the same mechanism `createHeadshotMarkerV2.__syncMask`
 * already uses. One hook, every path, and ordering is read from the sprite's LIVE position so
 * it is never stale mid-tween (the per-step limitation the brief asked about).
 *
 * Cost is ten containers per frame: read y, compute, compare, assign. Measured in
 * reports/depth-ordering.md.
 *
 * FLAG OFF = INERT. The handler returns before touching anything, so every container stays at
 * the depth 1 it was created with.
 */
import { depthOrderingEnabled, depthOrderingMode } from "../setup/markerConfig.js";
import { pixelsToGrid } from "./gridToPixels.js";
import { resolvePlayerDepths, DEPTH_MODE } from "./playerDepth.js";

/** Depth every player container is created with. Restored when the flag goes off mid-session. */
export const DEFAULT_PLAYER_DEPTH = 1;

function normaliseMode(raw) {
  return raw === DEPTH_MODE.HARD_PROMOTION ? DEPTH_MODE.HARD_PROMOTION : DEPTH_MODE.TIE_BREAK;
}

/**
 * Apply one ordering pass. Returns the Map that was applied (empty when inert), so a test or a
 * capture harness can assert what happened instead of inspecting the scene.
 */
export function applyPlayerDepths(playerSprites, { animations, stepIndex, offenseTeamId,
                                                   canvasHeight = 768 } = {}) {
  if (!playerSprites) return new Map();
  if (!depthOrderingEnabled()) return new Map();

  // Live grid y per player, inverted from the container's actual pixel position. This is what
  // makes the ordering correct DURING a tween rather than only at step boundaries.
  const gridYById = new Map();
  const playersById = {};
  for (const key of Object.keys(playerSprites)) {
    const sprite = playerSprites[key];
    if (!sprite || typeof sprite.y !== "number") continue;
    const pid = sprite.playerId ?? key;
    gridYById.set(pid, pixelsToGrid(sprite.x ?? 0, sprite.y, 1229, canvasHeight).y);
    playersById[pid] = { team_id: sprite.team_id };
  }

  const depths = resolvePlayerDepths({
    animations,
    stepIndex,
    offenseTeamId,
    playersById,
    gridYById,
    mode: normaliseMode(depthOrderingMode()),
  });

  for (const key of Object.keys(playerSprites)) {
    const sprite = playerSprites[key];
    if (!sprite || typeof sprite.setDepth !== "function") continue;
    const pid = sprite.playerId ?? key;
    const depth = depths.get(pid);
    // A player with no resolvable depth is LEFT ALONE rather than given a stand-in.
    if (Number.isFinite(depth) && sprite.depth !== depth) sprite.setDepth(depth);
  }
  return depths;
}

/** Restore the creation-time depth on every container. Used when the flag is turned off live. */
export function resetPlayerDepths(playerSprites) {
  if (!playerSprites) return;
  for (const key of Object.keys(playerSprites)) {
    const sprite = playerSprites[key];
    if (sprite && typeof sprite.setDepth === "function" && sprite.depth !== DEFAULT_PLAYER_DEPTH) {
      sprite.setDepth(DEFAULT_PLAYER_DEPTH);
    }
  }
}

/**
 * Install the per-frame ordering pass. Idempotent.
 *
 * The caller keeps `scene.__depthContext` up to date ({ animations, stepIndex, offenseTeamId });
 * the handler reads it. It never computes game state — it reads the payload already present.
 */
export function installDepthOrdering(scene, playerSprites) {
  if (!scene?.events || scene.__depthOrderingInstalled) return;
  scene.__depthOrderingInstalled = true;
  let wasEnabled = false;

  const tick = () => {
    const on = depthOrderingEnabled();
    if (!on) {
      // Toggled off live (window override): put everything back exactly as created, once.
      if (wasEnabled) { resetPlayerDepths(playerSprites); wasEnabled = false; }
      return;
    }
    wasEnabled = true;
    const ctx = scene.__depthContext || {};
    applyPlayerDepths(playerSprites, {
      animations: ctx.animations,
      stepIndex: ctx.stepIndex ?? 0,
      offenseTeamId: ctx.offenseTeamId,
      canvasHeight: scene.scale?.height || 768,
    });
  };

  // READ-ONLY inspection hook. Installed regardless of the flag because the flag-OFF gate has
  // to be able to prove "every container is still at depth 1" rather than assert it. It writes
  // nothing and computes nothing — it reports the depths Phaser currently holds.
  if (typeof window !== "undefined") {
    window.__GOB_DEPTH_REPORT = () => {
      const rows = [];
      for (const key of Object.keys(playerSprites || {})) {
        const sp = playerSprites[key];
        if (!sp) continue;
        rows.push({
          playerId: sp.playerId ?? key,
          teamId: sp.team_id ?? null,
          depth: sp.depth,
          x: sp.x,
          y: sp.y,
        });
      }
      return {
        enabled: depthOrderingEnabled(),
        mode: depthOrderingMode(),
        players: rows,
        ballDepth: scene.ballSprite?.depth ?? null,
      };
    };
  }

  scene.events.on("update", tick);
  scene.events.once("shutdown", () => {
    scene.events.off("update", tick);
    scene.__depthOrderingInstalled = false;
  });
}
