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
