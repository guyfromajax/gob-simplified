import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js";

/**
 * createBallTrail(scene, ballSprite, durationMs, opts?)
 *
 * Spawns a self-cleaning Phaser 3.60 particle trail that follows ballSprite
 * for `durationMs`, then destroys itself. No leaks, no persistent listeners.
 *
 * Currently fired by `renderBallTransition` in `animationPlayback.js` when the
 * outlet pass step on a Covert Release fast break has a high outlet score
 * (sharp pass). Designed so it can be reused for any ball-tween that wants a
 * visual emphasis effect (e.g., dimes, alley-oops, etc.) in the future.
 *
 * Tuning notes — pass `opts` to adjust:
 *   - `color` / `coreColor`: outer trail tint vs. hot core (defaults orange/cream).
 *   - `length`: fraction of step duration each particle lives (default 0.4,
 *     clamped 140–600ms internally).
 *   - `intensity`: emission rate + alpha multiplier (higher = denser, brighter).
 *   - `size`: scale factor on the particles.
 *   - `spread`: pixel radius of the random emit zone (0 = perfect line).
 *   - `blendMode`: Phaser blend mode, default `'ADD'` for glow feel.
 *   - `depthOffset`: depth relative to ballSprite (default -1 = behind ball).
 */
export function createBallTrail(scene, ballSprite, durationMs, opts = {}) {
  const {
    color       = 0xff5a00,   // deep orange
    coreColor   = 0xfff1d6,
    length      = 0.4,
    intensity   = 1.6,
    size        = 1.6,
    spread      = 3,
    blendMode   = "ADD",
    depthOffset = -1,
  } = opts;

  const TEX_KEY = "__ballTrailDot";
  if (!scene.textures.exists(TEX_KEY)) {
    const r = 16;
    const c = scene.add.graphics({ x: 0, y: 0, add: false });
    const stops = [
      [r * 1.00, 0xffffff, 0.00],
      [r * 0.85, 0xffffff, 0.06],
      [r * 0.60, 0xffffff, 0.22],
      [r * 0.35, 0xffffff, 0.55],
      [r * 0.00, 0xffffff, 1.00],
    ];
    for (const [rad, col, alpha] of stops) {
      c.fillStyle(col, alpha);
      c.fillCircle(r, r, rad > 0 ? rad : 1.5);
    }
    c.generateTexture(TEX_KEY, r * 2, r * 2);
    c.destroy();
  }

  const particleLife = Math.max(140, Math.min(durationMs * length, 600));
  const frequency    = Math.max(6, 18 / intensity);

  const emitter = scene.add.particles(0, 0, TEX_KEY, {
    lifespan: particleLife,
    frequency,
    quantity: 1,
    speed: 0,
    scale: { start: 0.55 * size, end: 0.05 * size, ease: "Quad.easeOut" },
    alpha: { start: 0.85 * intensity, end: 0, ease: "Quad.easeOut" },
    tint:  [coreColor, color, color],
    rotate: { min: 0, max: 360 },
    blendMode,
    emitZone: spread > 0
      ? { type: "random", source: new Phaser.Geom.Circle(0, 0, spread) }
      : undefined,
  });

  emitter.setDepth((ballSprite.depth || 0) + depthOffset);
  emitter.startFollow(ballSprite, 0, 0, true);

  scene.time.delayedCall(durationMs, () => {
    emitter.stop();
    scene.time.delayedCall(particleLife + 50, () => {
      if (emitter && emitter.scene) emitter.destroy();
    });
  });

  return emitter;
}
