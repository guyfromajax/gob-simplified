/**
 * FRAME TIME for the idle-wander render path, at cap 0 / 3 / 6 / 10.
 *
 * WHY THIS SHAPE. Frame cost is driven by CONCURRENT tweens, not by the per-game stamp count.
 * There are only ten sprites, so the number of things updating on any one frame is bounded by
 * ten however many stamps the game emits. Stamps rising 1,204 -> 5,633 per game means more STEPS
 * carry a wander, not more simultaneous work. This harness measures the actual per-frame cost at
 * each cap and reports the concurrent tween counts that explain it.
 *
 * It also checks the claim the density argument rests on: applyIdleWander takes OWNERSHIP of the
 * sprite's idle offset channel from the heartbeat rather than stacking on top of it, so a
 * wandering player costs one tween, not two.
 *
 * Measures the real arrivalHeartbeat.js update path. Phaser's tween manager is stubbed — its
 * scheduling is not what changed — so this is the CPU cost of the idle machinery per frame, not
 * an end-to-end GPU frame time. Stated plainly in the output.
 *
 * node scratch_frametime.mjs
 */
const MOD = "./FrontEnd/static/js/phaser/animation/arrivalHeartbeat.js";
const { applyIdleWander, ensureConsistentHeartbeat } = await import(MOD);

function makeScene() {
  const live = [];
  return {
    __live: live,
    game: { config: { width: 1440, height: 810 } },
    tweens: {
      add(cfg) {
        const t = {
          cfg, kind: "heartbeat", elapsed: 0, dead: false,
          isPlaying() { return !this.dead; },
          stop() { this.dead = true; },
          remove() { this.dead = true; },
        };
        live.push(t);
        return t;
      },
      addCounter(cfg) {
        const t = {
          cfg, kind: "wander", elapsed: 0, dead: false,
          isPlaying() { return !this.dead; },
          stop() { this.dead = true; },
          remove() { this.dead = true; },
        };
        live.push(t);
        return t;
      },
      killTweensOf(target) {
        for (const t of live) if (t.cfg && t.cfg.targets === target) t.dead = true;
      },
      getTweensOf: () => [],
    },
  };
}

function makeSprites(n) {
  const map = {};
  for (let i = 0; i < n; i += 1) {
    const pid = `player-${i}-0123456789abcdef`;
    map[pid] = {
      playerId: pid, active: true, destroyed: false,
      displayOriginX: 20, displayOriginY: 40, scaleX: 1, scaleY: 1,
      x: 100 + i * 30, y: 200, attributes: { NG: 0.5 },
    };
  }
  return map;
}

const STYLES = ["survey_rock", "jockey", "shuffle", "jab"];
const FRAMES = 20000;      // ~5.5 min of 60fps play per configuration
const STEP_MS = 1000;      // typical HCO beat; wanders span the step

function measure(cap, nSprites = 10) {
  const scene = makeScene();
  const sprites = makeSprites(nSprites);
  const ids = Object.keys(sprites);

  ensureConsistentHeartbeat(scene, sprites);
  const heartbeatsBefore = scene.__live.filter((t) => !t.dead && t.kind === "heartbeat").length;

  for (let i = 0; i < cap; i += 1) {
    applyIdleWander(scene, sprites[ids[i]], {
      seed: 1000 + i, style: STYLES[i % STYLES.length],
      radiusGrid: 0.6 * 0.6, durationMs: STEP_MS, dirX: 1, dirY: 0,
    });
  }

  const alive = scene.__live.filter((t) => !t.dead);
  const heartbeats = alive.filter((t) => t.kind === "heartbeat").length;
  const wanders = alive.filter((t) => t.kind === "wander").length;
  // Not every tween drives an onUpdate: the heartbeat is a property tween Phaser interpolates
  // itself. Reported so a near-zero baseline is not mistaken for a broken measurement.
  const withOnUpdate = alive.filter((t) => typeof t.cfg.onUpdate === "function").length;

  const runFrames = (n) => {
    for (let f = 0; f < n; f += 1) {
      for (const t of alive) {
        t.elapsed = (f * 16.67) % STEP_MS;
        if (t.cfg.onUpdate) t.cfg.onUpdate(t);
      }
    }
  };

  runFrames(5000);                       // JIT warm-up
  const trials = [];
  for (let i = 0; i < 7; i += 1) {
    const t0 = process.hrtime.bigint();
    runFrames(FRAMES);
    const t1 = process.hrtime.bigint();
    trials.push(Number(t1 - t0) / 1e6 / FRAMES);
  }
  trials.sort((a, b) => a - b);
  const median = trials[Math.floor(trials.length / 2)];

  return {
    cap, heartbeatsBefore, heartbeats, wanders, withOnUpdate,
    concurrent: alive.length,
    usPerFrame: median * 1000,
    usMin: trials[0] * 1000,
    usMax: trials[trials.length - 1] * 1000,
    pctOf60fpsBudget: (median / 16.67) * 100,
  };
}

const pad = (v, w) => String(v).padStart(w);
console.log("=".repeat(100));
console.log("IDLE-WANDER FRAME TIME — cost of the idle update path per frame, 10 sprites on court");
console.log(`${FRAMES} frames x 7 trials per configuration, median reported, after 5,000 warm-up frames`);
console.log("=".repeat(100));
console.log(
  `  ${"cap".padEnd(5)}${pad("heartbeats", 12)}${pad("wanders", 9)}${pad("concurrent", 12)}` +
  `${pad("w/ onUpdate", 13)}${pad("us/frame", 11)}${pad("[min-max]", 18)}${pad("% of 16.67ms", 14)}`,
);

const rows = [0, 3, 6, 10].map((c) => measure(c));
for (const r of rows) {
  console.log(
    `  ${String(r.cap).padEnd(5)}${pad(r.heartbeats, 12)}${pad(r.wanders, 9)}${pad(r.concurrent, 12)}` +
    `${pad(r.withOnUpdate, 13)}${pad(r.usPerFrame.toFixed(3), 11)}` +
    `${pad(`[${r.usMin.toFixed(3)}-${r.usMax.toFixed(3)}]`, 18)}${pad(r.pctOf60fpsBudget.toFixed(4) + "%", 14)}`,
  );
}

const base = rows[0];
console.log();
console.log("  DELTA vs cap 0 — the pre-change baseline, heartbeat only, no wander:");
for (const r of rows.slice(1)) {
  const d = r.usPerFrame - base.usPerFrame;
  console.log(
    `    cap ${String(r.cap).padEnd(3)} ${(d >= 0 ? "+" : "") + d.toFixed(3)} us/frame` +
    ` (${(d >= 0 ? "+" : "") + ((d / 1000 / 16.67) * 100).toFixed(5)}% of a 60fps budget),` +
    ` concurrent tweens ${base.concurrent} -> ${r.concurrent}`,
  );
}

console.log();
console.log("  OWNERSHIP — does a wander REPLACE the heartbeat, or stack on top of it?");
for (const r of rows) {
  const stacked = r.concurrent > base.concurrent;
  console.log(
    `    cap ${String(r.cap).padEnd(3)} ${pad(r.heartbeats, 2)} heartbeats + ${pad(r.wanders, 2)} wanders` +
    ` = ${pad(r.concurrent, 2)} concurrent   ${stacked ? "STACKED — cost would scale" : "REPLACED — cost stays flat"}`,
  );
}
console.log();
console.log("  This is the CPU cost of the idle update path, which is the part the change affects.");
console.log("  It is not an end-to-end GPU frame time and cannot resolve compositing or draw-call");
console.log("  cost. What it does establish is the shape of the curve: concurrent tween count is");
console.log("  bounded by the ten sprites on court, so the 4.7x rise in per-game stamps does not");
console.log("  multiply per-frame work — it means more STEPS carry a wander instead of a heartbeat.");
