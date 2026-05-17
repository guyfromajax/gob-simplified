// Stamina ring helpers used by v2 marker.
// Extracted from createHeadshotMarkerV2 so syncPlayerSpriteAttributes.js can
// import without pulling in the marker builder (avoids circular import).
// Pulse below 20% is intentionally NOT wired up — the constant is kept for a
// future "low stamina pulse" setting toggle.

// Nonlinear stamina → visual-fill curve.
// 90–100 stamina = top 25% of ring · 80–89 = next 25% · 70–79 = next 25% · 0–69 = final 25%.
function staminaToVisualFill(s) {
  if (s >= 0.90) return 0.75 + (s - 0.90) * 2.5;
  if (s >= 0.80) return 0.50 + (s - 0.80) * 2.5;
  if (s >= 0.70) return 0.25 + (s - 0.70) * 2.5;
  return s * (0.25 / 0.70);
}

function staminaColor(s) {
  if (s > 0.89) return 0x34EC27;   // green
  if (s >= 0.80) return 0xFFD700;  // yellow
  if (s >= 0.70) return 0xF79420;  // orange
  return 0xff4444;                 // red
}

const DEG_TO_RAD = Math.PI / 180;

export function drawStaminaArc(gfx, headR, stamina) {
  gfx.clear();
  if (stamina == null) return;
  const r = headR + 9;
  const s = Math.max(0, Math.min(1, stamina));
  const visualFill = staminaToVisualFill(s);
  const color = staminaColor(s);

  const startDeg = -100;
  const totalSweep = 340; // 20° gap at 12 o'clock
  const startRad = startDeg * DEG_TO_RAD;
  const trackEnd = (startDeg + totalSweep) * DEG_TO_RAD;
  const fillEnd = (startDeg + totalSweep * visualFill) * DEG_TO_RAD;

  // Background track (full sweep, dim)
  gfx.lineStyle(2, 0x000000, 0.35);
  gfx.beginPath();
  gfx.arc(0, 0, r, startRad, trackEnd, false);
  gfx.strokePath();

  // Foreground stamina fill
  if (visualFill > 0.005) {
    gfx.lineStyle(2, color, 0.9);
    gfx.beginPath();
    gfx.arc(0, 0, r, startRad, fillEnd, false);
    gfx.strokePath();
  }
}
