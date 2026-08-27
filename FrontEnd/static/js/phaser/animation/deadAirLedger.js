/**
 * Dead-air ledger — measurement instrumentation for the animation cleanup pass.
 *
 * Records every interval where the court is visually static, so "the game feels
 * clumsy" becomes a ranked list of milliseconds instead of a vibe. Two sources:
 *
 *   1. **Frozen steps** — a step whose start/end coords are identical for every
 *      player. Nobody moves for `stepWaitMs`. Usually an under-authored step
 *      (see `continuing_targets` freeze-by-default, findings §2).
 *   2. **Announcement freezes** — a `blocking: true` announcement pausing
 *      gameClock + shotClock for `hold_ms`. Wall time that buys zero game time.
 *   3. **Player stillness** — for EVERY step, how many of the ten players are
 *      frozen, weighted by duration ("player-seconds of stillness").
 *
 * (3) is the one that matters most. Frozen *steps* turned out to be a minor
 * cost (~108ms/turn measured). The real defect signature of freeze-by-default
 * is one player moving while nine stand posed — those steps have movers > 0, so
 * categories (1) and (2) are blind to them entirely. Stillness catches them.
 *
 * Both are wall-clock cost with no motion on screen. The distinction matters
 * because they have different fixes: (1) is a backend authoring bug, (2) is a
 * presentation policy choice.
 *
 * **Silent by design.** Recording is buffer-only; nothing prints until you call
 * `dumpDeadAir()`. Per-event `console.log` was measurably destructive: a HEAVY
 * RATTLE is 8 consecutive ~50ms steps, and synchronous console writes with
 * DevTools open added enough per-step latency to make rim action visibly
 * stutter. An instrument that changes what it measures is worse than none.
 *
 * Usage: play a quarter, then `dumpDeadAir()` in the console.
 * Disable recording entirely with `window.DEAD_AIR_LEDGER = false`.
 */

const globalScope =
  (typeof window !== "undefined" && window)
  || (typeof globalThis !== "undefined" && globalThis)
  || undefined;

/** Ignore sub-frame slivers — they are not perceptible as dead air. */
const MIN_RECORDED_MS = 60;

const ledger = {
  frozenSteps: [],
  announcementFreezes: [],
  stillness: [],
};

export function isDeadAirLedgerEnabled() {
  if (!globalScope) return false;
  // Default ON during the cleanup measurement pass.
  return globalScope.DEAD_AIR_LEDGER !== false;
}

/**
 * Count players whose coords change across a step. Cheap (<= 10 entries).
 * Returns -1 when the step shape is unreadable, so callers can skip it rather
 * than mis-report it as frozen.
 */
export function countStepMovers(step) {
  const startCoords = step?.start?.coords;
  const endCoords = step?.end?.coords;
  if (!startCoords || !endCoords) return -1;
  let movers = 0;
  for (const [playerId, startCoord] of Object.entries(startCoords)) {
    const endCoord = endCoords[playerId];
    if (!startCoord || !endCoord) continue;
    if (
      Math.abs(endCoord.x - startCoord.x) >= 1e-6
      || Math.abs(endCoord.y - startCoord.y) >= 1e-6
    ) {
      movers += 1;
    }
  }
  return movers;
}

export function recordFrozenStep({
  durationMs,
  step = null,
  turnData = null,
  ballMoved = false,
}) {
  if (!isDeadAirLedgerEnabled()) return;
  if (!Number.isFinite(durationMs) || durationMs < MIN_RECORDED_MS) return;

  const entry = {
    ms: Math.round(durationMs),
    turnIndex: turnData?.index ?? null,
    resultType: turnData?.result_type ?? null,
    currentTurn: turnData?.current_turn ?? null,
    fastBreakPlay: turnData?.fast_break_play ?? null,
    stepId: step?.id ?? null,
    kind: step?.start?.advance_trigger?.metadata?.kind ?? null,
    reason: step?.start?.advance_trigger?.metadata?.reason ?? null,
    trigger: step?.start?.advance_trigger?.condition ?? null,
    // A step where players are frozen but the ball is in flight is legitimate
    // (a pass, a shot). Flagged so the summary can separate real dead air from
    // ball-motion beats.
    ballMoved: Boolean(ballMoved),
  };
  ledger.frozenSteps.push(entry);

}

/**
 * Record how much of the court was static during a step.
 *
 * `stillPlayerSeconds` = (players that never moved) x (step duration). A 368ms
 * step where 1 of 10 moves costs 3.3 player-seconds of stillness; the same step
 * with all 10 moving costs 0. Ranking by this surfaces exactly the steps that
 * read as posed — the outlet-denial / bat-OOB / frozen-defender family.
 */
export function recordStillness({ durationMs, movers, step = null, turnData = null }) {
  if (!isDeadAirLedgerEnabled()) return;
  if (!Number.isFinite(durationMs) || durationMs <= 0) return;
  if (!Number.isFinite(movers) || movers < 0) return;

  const total = Object.keys(step?.start?.coords || {}).length;
  if (!total) return;
  const still = Math.max(0, total - movers);

  ledger.stillness.push({
    ms: Math.round(durationMs),
    movers,
    total,
    stillPlayerSeconds: (still * durationMs) / 1000,
    turnIndex: turnData?.index ?? null,
    resultType: turnData?.result_type ?? null,
    currentTurn: turnData?.current_turn ?? null,
    fastBreakPlay: turnData?.fast_break_play ?? null,
    kind: step?.start?.advance_trigger?.metadata?.kind ?? null,
    reason: step?.start?.advance_trigger?.metadata?.reason ?? null,
    trigger: step?.start?.advance_trigger?.condition ?? null,
  });
}

export function recordAnnouncementFreeze({ holdMs, text = null, turnData = null }) {
  if (!isDeadAirLedgerEnabled()) return;
  if (!Number.isFinite(holdMs) || holdMs < MIN_RECORDED_MS) return;

  const entry = {
    ms: Math.round(holdMs),
    text: String(text || "").trim() || "(untitled)",
    turnIndex: turnData?.index ?? null,
    resultType: turnData?.result_type ?? null,
  };
  ledger.announcementFreezes.push(entry);
}

function summarize(rows, keyFn) {
  const groups = new Map();
  for (const row of rows) {
    const key = keyFn(row);
    const g = groups.get(key) || { key, count: 0, totalMs: 0 };
    g.count += 1;
    g.totalMs += row.ms;
    groups.set(key, g);
  }
  return [...groups.values()].sort((a, b) => b.totalMs - a.totalMs);
}

function printTable(title, rows) {
  const total = rows.reduce((sum, r) => sum + r.totalMs, 0);
  console.log(`\n=== ${title} — ${(total / 1000).toFixed(1)}s total ===`);
  for (const r of rows) {
    console.log(
      `  ${String(Math.round(r.totalMs)).padStart(7)}ms  `
      + `x${String(r.count).padStart(3)}  `
      + `(avg ${String(Math.round(r.totalMs / r.count)).padStart(4)}ms)  ${r.key}`,
    );
  }
  return total;
}

function printStillness() {
  const rows = ledger.stillness;
  if (!rows.length) return 0;

  const groups = new Map();
  for (const r of rows) {
    const key = `${r.currentTurn || r.resultType || "?"}${r.fastBreakPlay ? `/${r.fastBreakPlay}` : ""} :: ${r.kind || r.reason || r.trigger || "?"}`;
    const g = groups.get(key)
      || { key, count: 0, stillPS: 0, ms: 0, movers: 0, total: 0 };
    g.count += 1;
    g.stillPS += r.stillPlayerSeconds;
    g.ms += r.ms;
    g.movers += r.movers;
    g.total += r.total;
    groups.set(key, g);
  }
  const sorted = [...groups.values()].sort((a, b) => b.stillPS - a.stillPS);
  const totalPS = sorted.reduce((sum, g) => sum + g.stillPS, 0);

  console.log(`\n=== PLAYER STILLNESS — ${totalPS.toFixed(1)} player-seconds frozen ===`);
  console.log("    (ranked by cost; 'movers' is the average of 10 that actually moved)");
  for (const g of sorted) {
    const avgMovers = (g.movers / g.count).toFixed(1);
    const avgOf = (g.total / g.count).toFixed(0);
    console.log(
      `  ${g.stillPS.toFixed(1).padStart(7)} p-s  `
      + `x${String(g.count).padStart(3)}  `
      + `${String(Math.round(g.ms)).padStart(6)}ms  `
      + `movers ${avgMovers}/${avgOf}  ${g.key}`,
    );
  }
  return totalPS;
}

export function dumpDeadAir() {
  const realFrozen = ledger.frozenSteps.filter((r) => !r.ballMoved);
  const ballBeats = ledger.frozenSteps.filter((r) => r.ballMoved);

  const frozenTotal = printTable(
    "FROZEN STEPS (nobody moves, ball still)",
    summarize(realFrozen, (r) => `${r.currentTurn || r.resultType || "?"} :: ${r.kind || r.reason || r.trigger || "?"}`),
  );
  const announceTotal = printTable(
    "ANNOUNCEMENT FREEZES (clock-pinned)",
    summarize(ledger.announcementFreezes, (r) => r.text),
  );
  const ballTotal = printTable(
    "BALL-MOTION BEATS (players still, ball moving — legitimate)",
    summarize(ballBeats, (r) => `${r.currentTurn || r.resultType || "?"} :: ${r.kind || r.reason || r.trigger || "?"}`),
  );

  const stillPS = printStillness();

  console.log(
    `\n=== DEAD AIR TOTAL: ${((frozenTotal + announceTotal) / 1000).toFixed(1)}s `
    + `(${(frozenTotal / 1000).toFixed(1)}s frozen steps + ${(announceTotal / 1000).toFixed(1)}s announcement freezes)`,
  );
  console.log(`    excluded as legitimate ball motion: ${(ballTotal / 1000).toFixed(1)}s`);
  console.log(`=== PLAYER STILLNESS TOTAL: ${stillPS.toFixed(1)} player-seconds ===\n`);

  return { frozenTotal, announceTotal, ballTotal, stillPS, ledger };
}

export function resetDeadAir() {
  ledger.frozenSteps.length = 0;
  ledger.announcementFreezes.length = 0;
  ledger.stillness.length = 0;
  console.log("[DEAD-AIR] ledger reset");
}

if (globalScope) {
  globalScope.dumpDeadAir = dumpDeadAir;
  globalScope.resetDeadAir = resetDeadAir;
}
