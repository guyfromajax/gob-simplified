/**
 * Sim broadcast worm time domain — pure helpers (no DOM / no game imports).
 * Regulation quarters are REG_Q_SEC; OT periods are OT_Q_SEC.
 */

export const REG_Q_SEC = 480;
export const OT_Q_SEC = 240;

function num(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

/** Parse emitted clock strings like "8:00" / "0:12" → seconds remaining. */
export function clockToSeconds(clock) {
  const raw = String(clock || '').trim();
  const m = raw.match(/^(\d+):(\d{1,2})$/);
  if (!m) return 0;
  return num(m[1]) * 60 + num(m[2]);
}

/**
 * Elapsed game seconds from emitted quarter + clock.
 * Regulation Q1–Q4 are REG_Q_SEC each; OT (quarter ≥ 5) periods are OT_Q_SEC each.
 */
export function elapsedGameSeconds(quarter, clock) {
  const q = Math.max(1, num(quarter) || 1);
  const remaining = clockToSeconds(clock);
  if (q <= 4) {
    const qLen = REG_Q_SEC;
    return (q - 1) * qLen + Math.max(0, qLen - remaining);
  }
  const otIndex = q - 5;
  return 4 * REG_Q_SEC + otIndex * OT_Q_SEC + Math.max(0, OT_Q_SEC - remaining);
}

/** Full-domain seconds for worm x-axis (extends when OT is reached). */
export function wormDomainSeconds(maxQuarter) {
  const q = Math.max(1, num(maxQuarter) || 1);
  if (q <= 4) return 4 * REG_Q_SEC;
  return 4 * REG_Q_SEC + (q - 4) * OT_Q_SEC;
}
