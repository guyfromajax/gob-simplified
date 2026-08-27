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
 *
 * Both are wall-clock cost with no motion on screen. The distinction matters
 * because they have different fixes: (1) is a backend authoring bug, (2) is a
 * presentation policy choice.
 *
 * Usage: play a quarter, then `dumpDeadAir()` in the console.
 * Silence with `window.DEAD_AIR_LEDGER = false`.
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

  if (!entry.ballMoved) {
    console.log(
      `[DEAD-AIR] frozen ${entry.ms}ms  turn=${entry.turnIndex} `
      + `${entry.currentTurn || entry.resultType || "?"}`
      + `${entry.fastBreakPlay ? `/${entry.fastBreakPlay}` : ""}  `
      + `kind=${entry.kind || entry.reason || entry.trigger || "?"}`,
    );
  }
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
  console.log(`[DEAD-AIR] announce-freeze ${entry.ms}ms  "${entry.text}"`);
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

  console.log(
    `\n=== DEAD AIR TOTAL: ${((frozenTotal + announceTotal) / 1000).toFixed(1)}s `
    + `(${(frozenTotal / 1000).toFixed(1)}s frozen steps + ${(announceTotal / 1000).toFixed(1)}s announcement freezes)`,
  );
  console.log(`    excluded as legitimate ball motion: ${(ballTotal / 1000).toFixed(1)}s\n`);

  return { frozenTotal, announceTotal, ballTotal, ledger };
}

export function resetDeadAir() {
  ledger.frozenSteps.length = 0;
  ledger.announcementFreezes.length = 0;
  console.log("[DEAD-AIR] ledger reset");
}

if (globalScope) {
  globalScope.dumpDeadAir = dumpDeadAir;
  globalScope.resetDeadAir = resetDeadAir;
}
