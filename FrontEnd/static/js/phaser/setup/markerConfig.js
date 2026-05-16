// Flip to false to revert to the original circle + position + jersey marker.
// Every behavior change introduced with the headshot marker is gated on this flag.
export const USE_HEADSHOT_MARKER = true;

// Ball position offset from the player container's origin (= headshot center).
// When USE_HEADSHOT_MARKER is false this MUST be { x: 0, y: 0 } so ball behavior
// is byte-identical to the pre-headshot codebase.
export const BALL_ATTACH_OFFSET = USE_HEADSHOT_MARKER
  ? { x: 28, y: 16 }
  : { x: 0, y: 0 };

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
