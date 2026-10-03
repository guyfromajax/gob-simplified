// Flip to false to revert to the original circle + position + jersey marker.
// Every behavior change introduced with the headshot marker is gated on this flag.
export const USE_HEADSHOT_MARKER = true;

// Gates the v2 additions (vignette, name strip, stamina ring, rating-tiered
// border, height-linked radius). Only meaningful when USE_HEADSHOT_MARKER=true.
// Flip to false to render the v1 headshot marker exactly.
export const USE_MARKER_V2_FEATURES = true;

// Ball position offset from the player container's origin (= headshot center
// in headshot mode, sprite center in legacy mode). Currently {0,0} in both
// modes — the ball attaches to the sprite center, matching pre-headshot
// behavior. The composition wiring is kept in place so a future setting can
// re-introduce a hip anchor without touching every call site.
export const BALL_ATTACH_OFFSET = { x: 0, y: 0 };

// Resolve a ball position anchored to a player sprite, optionally composed with
// an additional per-call offset (preserves existing arc/lift offsets like y - 10).
export function playerBallPos(sprite, extra) {
  const ex = extra && typeof extra.x === "number" ? extra.x : 0;
  const ey = extra && typeof extra.y === "number" ? extra.y : 0;
  return {
    x: sprite.x + BALL_ATTACH_OFFSET.x + ex,
    y: sprite.y + BALL_ATTACH_OFFSET.y + ey,
  };
}

// ── Player sprite depth ordering ────────────────────────────────────────────
// Every player container is created at depth 1 and never changed, so a merged pair's draw
// order falls back to scene insertion order — arbitrary. Flipping this to true orders players
// by grid y (nearest the viewer on top) so an overlapping pair reads as one player in front of
// another. It does NOT remove overlap. DEFAULT FALSE.
export const USE_DEPTH_ORDERING = false;

// Live A/B override, read at CALL time so Jamie can toggle during an eye test without a
// rebuild:  window.__GOB_DEPTH_ORDERING = true   (or false to force off)
// Unset, the build-time flag above decides. Nothing else reads the constant directly.
export function depthOrderingEnabled() {
  if (typeof window !== "undefined" && window.__GOB_DEPTH_ORDERING !== undefined
      && window.__GOB_DEPTH_ORDERING !== null) {
    const v = window.__GOB_DEPTH_ORDERING;
    return v === true || v === 1 || v === "1" || v === "true";
  }
  return USE_DEPTH_ORDERING;
}

// Which sub-mode is in force. "tie_break" (ball owner wins only a near-tie) or
// "hard_promotion" (ball owner / shooter always above every other player).
//   window.__GOB_DEPTH_MODE = "hard_promotion"
// No value is recommended here — the report puts both side by side and Jamie picks.
export const DEPTH_ORDERING_MODE = "tie_break";

export function depthOrderingMode() {
  if (typeof window !== "undefined" && typeof window.__GOB_DEPTH_MODE === "string"
      && window.__GOB_DEPTH_MODE) {
    return window.__GOB_DEPTH_MODE;
  }
  return DEPTH_ORDERING_MODE;
}
