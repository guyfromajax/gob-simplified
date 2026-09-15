/**
 * HCO step-movement strict mode and step-pass clock-overrun policy.
 *
 * Kept out of turnAnimation.js so the debug reporter and unit tests can
 * read the same resolver the playback path uses.
 */

export function resolveHcoStepStrictMode(scope) {
  const raw = scope?.HCO_STEP_MOVEMENT_STRICT_CONTRACT;
  if (raw === "throw") return "throw";
  if (raw === "off" || raw === false) return "off";
  return "throw";
}

/**
 * Step-pass elapsed is raw wall (`Date.now() - stepStartMs`).
 * `real_time_elapsed_ms` is turn-level only — there is no per-step contract
 * to feed Option A (`getGuardedTurnElapsedMs`). Capping a step against the
 * whole-turn budget either fails to stop a tab-hide (turn > step hard-fail)
 * or hides a real step overrun (turn < step hard-fail).
 *
 * HCO hard-fail is therefore warn-only. Aborting the turn after a stall
 * makes the playback worse than letting it finish ugly.
 */
export function evaluateStepPassClockOverrun({
  elapsedGameSeconds,
  hardFailThresholdSeconds,
  isPressureSkeletonTurn = false,
  pressureStepStrictMode = "warn",
} = {}) {
  if (
    !Number.isFinite(Number(elapsedGameSeconds)) ||
    !Number.isFinite(Number(hardFailThresholdSeconds)) ||
    Number(elapsedGameSeconds) <= Number(hardFailThresholdSeconds)
  ) {
    return "ok";
  }
  if (isPressureSkeletonTurn && pressureStepStrictMode === "throw") {
    return "throw";
  }
  return "warn";
}
