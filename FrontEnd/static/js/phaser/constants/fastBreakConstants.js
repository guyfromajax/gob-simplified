/**
 * Fast Break System Constants
 * 
 * These constants define movement ranges, offsets, and coordinate ranges used throughout
 * the Fast Break system (DREB → Fast Break, Steal → Fast Break).
 * 
 * All coordinates are in HOME orientation (basket at x=91 for home, x=9 for away).
 */
import { CLAMP_BOUNDS } from "../animation/courtClamp.js";

/**
 * When false, skips the **"Fast Break!"** entry banners (turn start / FAST_BREAK context).
 * Makes, misses, rebounds, fouls, "Fast Break Score!", "Great Stop!", etc. are unchanged.
 * Runtime override:
 *   window.ENABLE_FAST_BREAK_ENTRY_ANNOUNCEMENTS = false // disable
 *   window.ENABLE_FAST_BREAK_ENTRY_ANNOUNCEMENTS = true  // enable
 */
export const ENABLE_FAST_BREAK_ENTRY_ANNOUNCEMENTS = true;

export function isFastBreakEntryAnnouncementsEnabled() {
  if (typeof window !== "undefined" && typeof window.ENABLE_FAST_BREAK_ENTRY_ANNOUNCEMENTS !== "undefined") {
    return Boolean(window.ENABLE_FAST_BREAK_ENTRY_ANNOUNCEMENTS);
  }
  return ENABLE_FAST_BREAK_ENTRY_ANNOUNCEMENTS;
}

// Ball Handler Movement (Defensive Stop / Shot Attempt)
export const BALL_HANDLER_MOVE_X_MIN = 5;
export const BALL_HANDLER_MOVE_X_MAX = 10;
export const BALL_HANDLER_MOVE_Y_RANGE = 3; // ±3 y-coords

// Stopper Positioning (Defensive Stop)
export const STOPPER_OFFSET_MIN = 1;
export const STOPPER_OFFSET_MAX = 3;

/** FB shot contest: two x-spots behind shooter relative to offense basket, ±Y — matches Python. */
export const SHOT_DEFENDER_X_OFFSET = 2;
export const SHOT_DEFENDER_Y_RANGE = 2;
export const SECONDARY_SHOT_DEFENDER_Y_OFFSET = 3;

/**
 * @param {number} bhX shooter final grid x (HOME)
 * @param {number} bhY shooter final grid y
 * @param {boolean} isHomeOffense
 */
export function fastBreakShotDefenderGridVsShooter(bhX, bhY, isHomeOffense) {
  const xDelta = isHomeOffense ? -SHOT_DEFENDER_X_OFFSET : SHOT_DEFENDER_X_OFFSET;
  let x = bhX + xDelta;
  x = Math.max(CLAMP_BOUNDS.minX, Math.min(CLAMP_BOUNDS.maxX, x));
  const yOff =
    -SHOT_DEFENDER_Y_RANGE +
    Math.floor(Math.random() * (2 * SHOT_DEFENDER_Y_RANGE + 1));
  let y = Math.max(CLAMP_BOUNDS.minY, Math.min(CLAMP_BOUNDS.maxY, bhY + yOff));
  return { x, y };
}

/**
 * @param {number} primaryX primary defender grid x
 * @param {number} primaryY primary defender grid y
 * @param {number} sourceY secondary defender current grid y
 */
export function fastBreakSecondaryShotDefenderGrid(primaryX, primaryY, sourceY) {
  const x = Math.max(CLAMP_BOUNDS.minX, Math.min(CLAMP_BOUNDS.maxX, primaryX));
  const yDelta =
    sourceY > primaryY
      ? SECONDARY_SHOT_DEFENDER_Y_OFFSET
      : -SECONDARY_SHOT_DEFENDER_Y_OFFSET;
  const y = Math.max(CLAMP_BOUNDS.minY, Math.min(CLAMP_BOUNDS.maxY, primaryY + yDelta));
  return { x, y };
}

/** @deprecated Use fastBreakShotDefenderGridVsShooter — kept for any external imports */
export const DEFENDER_X_OFFSET = 6;

// Rebounder Positioning
export const REBOUNDER_X_MIN = 40;
export const REBOUNDER_X_MAX = 60;
export const REBOUNDER_Y_RANGE = 6; // ±6 y-coords from starting position (defensive stop)

// Shot Attempt Rebounder Positioning
export const SHOT_ATTEMPT_REBOUNDER_Y_RANGE = 10; // ±10 y-coords from rim (shot attempt)

/**
 * Minimum grid-x distance from the offense's attacking basket that any
 * non-shooter offense player and any non-shot-defender defense player must
 * keep on Fast Breaks. Applied as a one-sided clamp toward midcourt:
 *   - Home offense (basket at x≈91): target x must be ≤ basket.x − 6 (so ≤ 85).
 *   - Away offense (basket at x≈9):  target x must be ≥ basket.x + 6 (so ≥ 15).
 *
 * Keeps the shot-area visually uncluttered: only the shooter and the primary
 * shot defender(s) (stopper / shot defender) can encroach inside the keep-out
 * zone. Get-back defenders, rebounder-band offense, outlet passer, etc. are
 * all held outside this radius.
 */
export const NON_SHOT_PARTICIPANT_BASKET_KEEPOUT = 6;

// Outlet Passer Movement
export const OUTLET_PASSER_MOVE_X = 7; // Moves forward 7 x-coords toward basket (+7 for home, -7 for away)

// Defensive Stop Determination
export const DEFENSIVE_STOP_Y_RANGE = 6; // Defender must be within ±6 y-coords of outlet receiver to force stop

// Steal Entry Movement (Steal → Fast Break)
export const STEAL_ENTRY_MOVE_X_MIN = 5; // Minimum x movement toward basket
export const STEAL_ENTRY_MOVE_X_MAX = 10; // Maximum x movement toward basket
export const STEAL_ENTRY_MOVE_Y_RANGE = 4; // ±4 y-coords
export const STEAL_ENTRY_Y_MIN = 3; // Minimum y-coord (clamped)
export const STEAL_ENTRY_Y_MAX = 47; // Maximum y-coord (clamped)

// Steal HCO Setup Movement (Steal → HCO)
export const STEAL_HCO_SETUP_MOVE_X_MIN = 3; // Minimum x movement away from basket
export const STEAL_HCO_SETUP_MOVE_X_MAX = 7; // Maximum x movement away from basket
export const STEAL_HCO_SETUP_MOVE_Y_RANGE = 3; // ±3 y-coords
export const STEAL_HCO_SETUP_Y_MIN = 3; // Minimum y-coord (clamped)
export const STEAL_HCO_SETUP_Y_MAX = 47; // Maximum y-coord (clamped)
