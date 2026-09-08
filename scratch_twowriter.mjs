/**
 * LEADING HYPOTHESIS TEST: do the always-on 1.4px heartbeat and the idle wander fight over one
 * render channel, with the heartbeat stomping the wander?
 *
 * Driven against the REAL arrivalHeartbeat.js module, with a sprite shaped like the production
 * headshot marker: a container with `list` children carrying `__restX/__restY` (the anchors
 * createHeadshotMarkerV2 stamps and that resolveWanderTargets/resolveHeartbeatTarget look for).
 * Only Phaser's tween manager is stubbed, and its configs are stepped manually so both writers
 * are exercised in the same frame.
 *
 * Sequence mirrors production order: heartbeat is established first (AnimationEngine calls
 * ensureConsistentHeartbeat every step), THEN a step arrives carrying an idle_wander flourish.
 *
 * node scratch_twowriter.mjs
 */
const MOD = "./FrontEnd/static/js/phaser/animation/arrivalHeartbeat.js";
const { applyIdleWander, ensureConsistentHeartbeat } = await import(MOD);

const W = 1440, H = 810;
const PX_PER_GRID = (W / 100 + H / 50) / 2;

function makeScene() {
  const counters = [], tweens = [];
  return {
    __counters: counters,
    __tweens: tweens,
    game: { config: { width: W, height: H } },
    tweens: {
      add(cfg) {
        const t = {
          cfg, __kind: "add", __stopped: false,
          isPlaying() { return !this.__stopped; },
          stop() { this.__stopped = true; },
          remove() { this.__stopped = true; },
        };
        tweens.push(t);
        return t;
      },
      addCounter(cfg) {
        const t = {
          cfg, __kind: "counter", elapsed: 0, __stopped: false,
          isPlaying() { return !this.__stopped; },
          stop() { this.__stopped = true; },
          remove() { this.__stopped = true; },
        };
        counters.push(t);
        return t;
      },
      killTweensOf() {},
      getTweensOf: () => [],
    },
  };
}

/** Production-shaped headshot marker: a container whose children hold the rest anchors. */
function makeMarker(playerId) {
  const child = (name, x, y) => ({ name, x, y, __restX: x, __restY: y });
  return {
    playerId,
    active: true,
    destroyed: false,
    attributes: { NG: 0.5 },
    // No displayOriginX/Y — a Phaser Container does not have them, which is what forces
    // resolveWanderTargets down its child_local branch.
    list: [child("headshot", 100, 200), child("ring", 100, 200), child("label", 100, 226)],
  };
}

function childOffsets(sprite) {
  return sprite.list.map((c) => ({
    name: c.name,
    dx: +(c.x - c.__restX).toFixed(3),
    dy: +(c.y - c.__restY).toFixed(3),
  }));
}

/** Advance every live tween/counter to `t` ms and apply its writes, heartbeat first. */
function stepTo(scene, tMs, halfCycleGuess = 500) {
  for (const tw of scene.__tweens) {
    if (tw.__stopped) continue;
    const c = tw.cfg;
    const dur = c.duration || halfCycleGuess;
    const phase = (tMs % (dur * 2)) / dur;
    const k = phase <= 1 ? phase : 2 - phase; // yoyo
    for (const [prop, target] of Object.entries(c)) {
      if (["targets", "duration", "ease", "yoyo", "repeat", "onUpdate", "onComplete", "delay", "hold", "repeatDelay"].includes(prop)) continue;
      if (typeof target !== "number") continue;
      const tgt = c.targets;
      if (!tgt || typeof tgt !== "object") continue;
      const base = tgt["__base_" + prop] ?? (tgt["__base_" + prop] = tgt[prop]);
      tgt[prop] = base + (target - base) * k;
    }
  }
  for (const ct of scene.__counters) {
    if (ct.__stopped) continue;
    ct.elapsed = Math.min(tMs, ct.cfg.duration);
    if (typeof ct.cfg.onUpdate === "function") ct.cfg.onUpdate(ct);
  }
}

console.log("=".repeat(84));
console.log("TWO-WRITER TEST — heartbeat established first, then an idle_wander arrives");
console.log("=".repeat(84));
console.log(`canvas ${W}x${H}  ->  pxPerGrid = ${PX_PER_GRID.toFixed(2)}`);

// --- ARM A: heartbeat only (this is what Jamie says he sees) ------------------------------
{
  const scene = makeScene();
  const sp = makeMarker("p-heartbeat-only");
  ensureConsistentHeartbeat(scene, { "p-heartbeat-only": sp });
  let peak = 0;
  for (let t = 20; t <= 2000; t += 20) {
    stepTo(scene, t);
    for (const o of childOffsets(sp)) peak = Math.max(peak, Math.abs(o.dx), Math.abs(o.dy));
  }
  console.log(`\nARM A  heartbeat alone            peak child offset = ${peak.toFixed(2)} px`);
  console.log(`       tweens=${scene.__tweens.length} counters=${scene.__counters.length}`);
}

// --- ARM B: heartbeat, then wander (production order) ------------------------------------
for (const [style, amp] of [["survey_rock", 0.5], ["shuffle", 1.0], ["jockey", 0.6], ["jab", 1.2]]) {
  const scene = makeScene();
  const pid = "p-" + style;
  const sp = makeMarker(pid);

  ensureConsistentHeartbeat(scene, { [pid]: sp });
  const hbTween = scene.__tweens[0];

  applyIdleWander(scene, sp, {
    seed: 123456, style, radiusGrid: amp, dirX: 1, dirY: 0, durationMs: 2400,
  });

  const counter = scene.__counters[0];
  const hbStoppedByWander = !!hbTween && hbTween.__stopped;

  let peak = 0;
  for (let t = 20; t <= 2400; t += 20) {
    stepTo(scene, t);
    for (const o of childOffsets(sp)) peak = Math.max(peak, Math.abs(o.dx), Math.abs(o.dy));
  }
  if (counter && typeof counter.cfg.onComplete === "function") counter.cfg.onComplete(counter);
  const residual = Math.max(...childOffsets(sp).map((o) => Math.max(Math.abs(o.dx), Math.abs(o.dy))));

  console.log(`\nARM B  ${style.padEnd(12)} amp=${amp}`);
  console.log(`       wander tween created:            ${!!counter}`);
  console.log(`       heartbeat stopped by the wander: ${hbStoppedByWander}  (single-owner store)`);
  console.log(`       PEAK CHILD OFFSET:               ${peak.toFixed(2)} px`);
  console.log(`       residual after onComplete:       ${residual.toFixed(3)} px  (want 0)`);
}

console.log("\n" + "=".repeat(84));
console.log("READ: if ARM B peaks land near ARM A (~1.4px) the heartbeat is winning the channel.");
console.log("      If ARM B peaks are many times larger, the two writers are NOT fighting and");
console.log("      the wander is rendering at full amplitude in render space.");
console.log("=".repeat(84));
