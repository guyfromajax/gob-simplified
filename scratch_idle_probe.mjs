/**
 * PART 1 / PART 3 harness — drive the real applyIdleWander in node with a stub Phaser scene.
 *
 * Proves two things without a browser:
 *   1. RENDER PATH LIVES. applyIdleWander actually produces render-space offsets when handed a
 *      backend idle_wander payload. (Part 1: distinguishes "stamp never fires" from "nothing
 *      renders it".)
 *   2. DETERMINISM. Same seed => byte-identical offset series; different seed => different.
 *      Also exercises the always-on heartbeat, which is where the Math.random() defect lives.
 *
 * Nothing is stubbed inside arrivalHeartbeat.js itself — only Phaser's tween manager, whose
 * configs we capture and step manually.
 *
 * node scratch_idle_probe.mjs
 */
const MOD = "./FrontEnd/static/js/phaser/animation/arrivalHeartbeat.js";

function makeScene() {
  const counters = [];
  const tweens = [];
  return {
    __counters: counters,
    __tweens: tweens,
    game: { config: { width: 1440, height: 810 } },
    tweens: {
      add(cfg) {
        const t = { cfg, __kind: "add", isPlaying: () => true, stop() {}, remove() {} };
        tweens.push(t);
        return t;
      },
      addCounter(cfg) {
        const t = { cfg, __kind: "counter", elapsed: 0, isPlaying: () => true, stop() {}, remove() {} };
        counters.push(t);
        return t;
      },
      killTweensOf() {},
      getTweensOf: () => [],
    },
  };
}

function makeSprite(playerId) {
  return {
    playerId,
    active: true,
    destroyed: false,
    displayOriginX: 20,
    displayOriginY: 40,
    scaleX: 1,
    scaleY: 1,
    attributes: { NG: 0.5 },
  };
}

/** Run one wander and sample the render-space offsets it applies over the beat. */
function sampleWander(applyIdleWander, { seed, style, radiusGrid, durationMs = 900, samples = 12 }) {
  const scene = makeScene();
  const sprite = makeSprite("p-abc-123");
  const base = { x: sprite.displayOriginX, y: sprite.displayOriginY };

  applyIdleWander(scene, sprite, { seed, style, radiusGrid, durationMs, dirX: 1, dirY: 0 });

  const counter = scene.__counters[0];
  if (!counter) return null;

  const out = [];
  for (let i = 1; i <= samples; i += 1) {
    counter.elapsed = (durationMs * i) / samples;
    counter.cfg.onUpdate(counter);
    out.push([
      +(sprite.displayOriginX - base.x).toFixed(4),
      +(sprite.displayOriginY - base.y).toFixed(4),
    ]);
  }
  // Clean exit: onComplete must restore exactly to base.
  counter.cfg.onComplete(counter);
  const residual = [
    +(sprite.displayOriginX - base.x).toFixed(6),
    +(sprite.displayOriginY - base.y).toFixed(6),
  ];
  return { offsets: out, residual };
}

const { applyIdleWander, ensureConsistentHeartbeat } = await import(MOD);

console.log("=".repeat(78));
console.log("PART 1 — DOES THE RENDER PATH ACTUALLY PRODUCE MOTION?");
console.log("=".repeat(78));

const r = sampleWander(applyIdleWander, { seed: 12345, style: "survey_rock", radiusGrid: 1.0 });
if (!r) {
  console.log("  FAIL — applyIdleWander created no counter tween. Render path is DEAD.");
} else {
  const maxAbs = Math.max(...r.offsets.flat().map(Math.abs));
  console.log(`  applyIdleWander produced ${r.offsets.length} sampled offsets.`);
  console.log(`  peak |offset| = ${maxAbs.toFixed(2)} px   (radiusGrid 1.0 at 1440x810)`);
  console.log(`  first 5: ${JSON.stringify(r.offsets.slice(0, 5))}`);
  console.log(`  residual after onComplete (must be [0,0]): ${JSON.stringify(r.residual)}`);
  console.log(`  VERDICT: render path ${maxAbs > 0.5 ? "LIVES" : "produced no visible motion"}`);
}

console.log();
console.log("  amplitude at candidate radii (peak px offset):");
for (const rg of [1.0, 0.5, 0.35, 0.25, 0.15]) {
  const s = sampleWander(applyIdleWander, { seed: 999, style: "survey_rock", radiusGrid: rg });
  const m = s ? Math.max(...s.offsets.flat().map(Math.abs)) : 0;
  console.log(`    radiusGrid ${rg.toFixed(2)}  ->  ${m.toFixed(2)} px peak`);
}

console.log();
console.log("  per-style shape at radiusGrid 0.35 (peak px):");
for (const st of ["survey_rock", "shuffle", "jockey", "jab"]) {
  const s = sampleWander(applyIdleWander, { seed: 4242, style: st, radiusGrid: 0.35 });
  const m = s ? Math.max(...s.offsets.flat().map(Math.abs)) : 0;
  console.log(`    ${st.padEnd(13)} -> ${m.toFixed(2)} px peak`);
}

console.log();
console.log("=".repeat(78));
console.log("DETERMINISM");
console.log("=".repeat(78));
const a1 = sampleWander(applyIdleWander, { seed: 777, style: "shuffle", radiusGrid: 0.35 });
const a2 = sampleWander(applyIdleWander, { seed: 777, style: "shuffle", radiusGrid: 0.35 });
const b1 = sampleWander(applyIdleWander, { seed: 778, style: "shuffle", radiusGrid: 0.35 });
const same = JSON.stringify(a1.offsets) === JSON.stringify(a2.offsets);
const diff = JSON.stringify(a1.offsets) !== JSON.stringify(b1.offsets);
console.log(`  applyIdleWander seed 777 twice  -> identical: ${same}`);
console.log(`  applyIdleWander seed 777 vs 778 -> different: ${diff}`);

// Heartbeat: capture the tween target amplitude twice; Math.random() jitter should make it move.
function heartbeatAmplitude() {
  const scene = makeScene();
  const sprite = makeSprite("p-abc-123");
  ensureConsistentHeartbeat(scene, { "p-abc-123": sprite });
  const t = scene.__tweens[0];
  if (!t) return null;
  return t.cfg.displayOriginY;
}
const h = [];
for (let i = 0; i < 6; i += 1) h.push(heartbeatAmplitude());
const hUnique = new Set(h.map((v) => (v == null ? "null" : v.toFixed(6))));
console.log(`  heartbeat target displayOriginY over 6 identical runs: ${h.map((v) => (v == null ? "null" : v.toFixed(3))).join(", ")}`);
console.log(`  distinct values: ${hUnique.size}  -> ${hUnique.size > 1 ? "NON-DETERMINISTIC (the Math.random defect)" : "deterministic"}`);
