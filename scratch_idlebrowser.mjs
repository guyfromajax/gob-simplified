/**
 * PRIMARY QUESTION: the backend stamps ~2,300 idle_wander flourishes per played game and a
 * human sees none of them. Find the stage where it dies.
 *
 * Measures, on a REAL played game in a REAL browser (the arm the human looks at):
 *   1. PAYLOAD   - how many idle_wander stamps actually arrive at the client.
 *   2. TWEEN     - how many wander tweens applyIdleWander creates, and how they end
 *                  (completed vs stopped early by killTweensOf / the step-end snap).
 *   3. DURATION  - each wander's duration against the 60ms perceptibility floor
 *                  (deadAirLedger.js:87).
 *   4. PIXELS    - PEAK PIXEL EXCURSION on screen. This is the number that matters.
 *
 * Why the pixel measurement is trustworthy AND settles the two-writer hypothesis:
 * the idle channel is the sprite's LOCAL render offset. A container child's local x/y does
 * not change when the player genuinely moves (the container moves instead), so the child's
 * excursion is pure render-space idle. If the always-on 1.4px heartbeat were stomping the
 * wander on a shared displayOrigin channel, peak excursion would sit near ~1.4px. If the
 * wander renders, it should reach ~15px (radiusGrid 1.0 x ~15.3 px/grid at 1440x810).
 *
 *   node scratch_idlebrowser.mjs [seconds]
 */
import { chromium } from "playwright";

const BASE = "http://localhost:8000";
const RUN_SECONDS = Number(process.argv[2] || 150);

const INSTRUMENT = () => {
  const P = (window.__IDLE = {
    armed: false, frames: 0,
    payloadTurns: 0, payloadIdle: 0, kinds: {},
    counters: 0, durs: [], complete: 0, early: 0, earlyEx: null,
    minmax: {}, modes: {}, wanderPeak: 0, wanderSamples: 0,
  });

  // (1) PAYLOAD
  const of = window.fetch;
  window.fetch = async function () {
    const r = await of.apply(this, arguments);
    try {
      const ct = (r.headers && r.headers.get("content-type")) || "";
      if (ct.indexOf("json") >= 0) {
        r.clone().json().then((j) => {
          const scan = (t) => {
            const steps = t && t.animation_steps;
            if (!Array.isArray(steps)) return;
            P.payloadTurns++;
            for (const st of steps) {
              const fl = st && st.start && st.start.flourish;
              if (!fl) continue;
              for (const k of Object.keys(fl)) {
                const kind = (fl[k] || {}).kind;
                P.kinds[kind] = (P.kinds[kind] || 0) + 1;
                if (kind === "idle_wander") P.payloadIdle++;
              }
            }
          };
          if (Array.isArray(j)) j.forEach(scan);
          else if (j && typeof j === "object") {
            scan(j);
            if (Array.isArray(j.turns)) j.turns.forEach(scan);
            if (j.turn) scan(j.turn);
          }
        }).catch(() => {});
      }
    } catch (e) {}
    return r;
  };

  // (3)/(4) the idle channel for one sprite
  const chan = (sp) => {
    if (Array.isArray(sp && sp.list) && sp.list.length) {
      const c = sp.list[0];
      if (c && Number.isFinite(c.x)) return { mode: "child_local", x: c.x, y: c.y };
    }
    if (sp && Number.isFinite(sp.displayOriginX)) {
      return { mode: "origin", x: sp.displayOriginX, y: sp.displayOriginY };
    }
    return null;
  };

  const arm = () => {
    const S = window.currentGameScene;
    if (!S || !S.tweens || !S.events || P.armed) return;
    P.armed = true;

    // (2) applyIdleWander is the addCounter caller carrying both onUpdate and onComplete.
    const tw = S.tweens;
    const origCounter = tw.addCounter.bind(tw);
    tw.addCounter = function (cfg) {
      const isW = cfg && typeof cfg.onUpdate === "function"
        && typeof cfg.onComplete === "function" && cfg.duration > 0;
      if (!isW) return origCounter(cfg);
      P.counters++;
      P.durs.push(cfg.duration);
      let done = false, lastEl = 0;
      const ou = cfg.onUpdate, oc = cfg.onComplete;
      const t = origCounter(Object.assign({}, cfg, {
        onUpdate: function (tn) {
          lastEl = (tn && tn.elapsed) || lastEl;
          const out = ou.apply(this, arguments);
          // Peak excursion sampled DURING a known wander, so it cannot be confused
          // with heartbeat-only motion.
          try {
            const S2 = window.currentGameScene, sp = (S2 && S2.playerSprites) || {};
            for (const pid of Object.keys(sp)) {
              const v = chan(sp[pid]);
              if (!v) continue;
              const m = P.minmax[pid];
              if (!m) continue;
              const d = Math.max(Math.abs(v.x - m.x0), Math.abs(v.y - m.y0));
              P.wanderSamples++;
              if (d > P.wanderPeak) P.wanderPeak = d;
            }
          } catch (e) {}
          return out;
        },
        onComplete: function () { done = true; P.complete++; return oc.apply(this, arguments); },
      }));
      setTimeout(() => {
        if (!done) { P.early++; P.earlyEx = { duration: cfg.duration, lastElapsed: lastEl }; }
      }, (cfg.duration || 0) + 600);
      return t;
    };

    S.events.on("postupdate", () => {
      P.frames++;
      const sprites = S.playerSprites || {};
      for (const pid of Object.keys(sprites)) {
        const v = chan(sprites[pid]);
        if (!v) continue;
        P.modes[pid] = v.mode;
        const m = P.minmax[pid] || (P.minmax[pid] = { x0: v.x, y0: v.y, xn: v.x, xx: v.x, yn: v.y, yx: v.y });
        if (v.x < m.xn) m.xn = v.x;
        if (v.x > m.xx) m.xx = v.x;
        if (v.y < m.yn) m.yn = v.y;
        if (v.y > m.yx) m.yx = v.y;
      }
    });
  };
  setInterval(arm, 100);

  window.dumpIdle = () => {
    const S = window.currentGameScene;
    const d = P.durs.slice().sort((a, b) => a - b);
    const exc = Object.keys(P.minmax).map((pid) => {
      const m = P.minmax[pid];
      return { pid: pid.slice(0, 8), dx: +(m.xx - m.xn).toFixed(2), dy: +(m.yx - m.yn).toFixed(2) };
    });
    const peak = exc.length ? Math.max(...exc.map((e) => Math.max(e.dx, e.dy))) : 0;
    return {
      armed: P.armed,
      PAYLOAD_idle_wander: P.payloadIdle,
      PAYLOAD_turns_with_steps: P.payloadTurns,
      PAYLOAD_all_kinds: P.kinds,
      WANDER_tweens_created: P.counters,
      WANDER_completed: P.complete,
      WANDER_stopped_early: P.early,
      WANDER_early_example: P.earlyEx,
      DURATION_min: d.length ? d[0] : null,
      DURATION_median: d.length ? d[d.length >> 1] : null,
      DURATION_max: d.length ? d[d.length - 1] : null,
      DURATION_under_60ms: d.filter((x) => x < 60).length,
      PEAK_PX_during_wander: +P.wanderPeak.toFixed(2),
      PEAK_PX_session_peak_to_peak: peak,
      per_player_excursion_px: exc,
      channel_modes: Object.keys(P.modes).reduce((a, k) => { a[P.modes[k]] = (a[P.modes[k]] || 0) + 1; return a; }, {}),
      frames_sampled: P.frames,
      pxPerGrid: S ? (S.game.config.width / 100 + S.game.config.height / 50) / 2 : null,
      canvas: S ? { w: S.game.config.width, h: S.game.config.height } : null,
    };
  };
};

const gameId = await fetch(`${BASE}/api/init-game`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    home_team: "Lancaster", away_team: "Bentley-Truman",
    mode: "single", user_team_side: "home",
  }),
}).then((r) => r.json()).then((j) => j.game_id);
console.log("game_id:", gameId);

const browser = await chromium.launch({
  headless: process.env.HEADED !== "1",
  args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const notable = [];
page.on("console", (m) => {
  const t = m.text();
  if (/error|fail|idle|wander|flourish|PLAYBACK|exception/i.test(t)) notable.push(m.type() + ": " + t.slice(0, 220));
});
page.on("pageerror", (e) => notable.push("PAGEERROR: " + String(e.message).slice(0, 220)));

await page.addInitScript(INSTRUMENT);
await page.goto(`${BASE}/static/court.html?game_id=${gameId}&my_team=home&mode=single`, {
  waitUntil: "domcontentloaded", timeout: 60000,
});

await page.waitForSelector(".play-button", { state: "attached", timeout: 60000 });
await page.waitForTimeout(3000);
// Click through JS: the button can be laid out off-panel in a headless viewport, which
// blocks Playwright's visibility check but not the handler.
const clicked = await page.evaluate(() => {
  const b = document.querySelector(".play-button");
  if (!b) return "no button";
  b.click();
  return "clicked";
});
console.log("play button:", clicked);
console.log("clicked Play Quarter; recording for", RUN_SECONDS, "s");

let lastDump = null;
for (let i = 0; i < RUN_SECONDS / 10; i += 1) {
  await page.waitForTimeout(10000);
  lastDump = await page.evaluate(() => (typeof window.dumpIdle === "function" ? window.dumpIdle() : null));
  const c = await page.evaluate(() => document.querySelectorAll("canvas").length);
  console.log(`  t=${(i + 1) * 10}s canvas=${c} armed=${lastDump && lastDump.armed} payloadIdle=${lastDump && lastDump.PAYLOAD_idle_wander} tweens=${lastDump && lastDump.WANDER_tweens_created} peakPx=${lastDump && lastDump.PEAK_PX_during_wander}`);
  if (lastDump && lastDump.WANDER_tweens_created > 60) break;
}

console.log("\n================ FINAL ================");
console.log(JSON.stringify(lastDump, null, 1));
console.log("\n---- notable console lines (first 25) ----");
console.log(notable.slice(0, 25).join("\n") || "(none)");

await page.screenshot({ path: "/tmp/idle_court.png" });
await browser.close();
