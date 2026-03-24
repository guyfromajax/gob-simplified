/**
 * Fast Break System Constants
 * 
 * These constants define movement ranges, offsets, and coordinate ranges used throughout
 * the Fast Break system (DREB → Fast Break, Steal → Fast Break).
 * 
 * All coordinates are in HOME orientation (basket at x=91 for home, x=9 for away).
 */

/**
 * When false, skips the **"Fast Break!"** entry banners (turn start / FAST_BREAK context).
 * Makes, misses, rebounds, fouls, "Fast Break Score!", "Great Stop!", etc. are unchanged.
 * Set to `true` after tuning to restore entry announcements.
 */
export const ENABLE_FAST_BREAK_ENTRY_ANNOUNCEMENTS = false;

// Ball Handler Movement (Defensive Stop / Shot Attempt)
export const BALL_HANDLER_MOVE_X_MIN = 5;
export const BALL_HANDLER_MOVE_X_MAX = 10;
export const BALL_HANDLER_MOVE_Y_RANGE = 3; // ±3 y-coords

// Stopper Positioning (Defensive Stop)
export const STOPPER_OFFSET_MIN = 1;
export const STOPPER_OFFSET_MAX = 3;

// Defender Positioning (Shot Attempt)
export const DEFENDER_X_OFFSET = 6; // Defender positioned 6 x-coords behind ball handler

// Rebounder Positioning
export const REBOUNDER_X_MIN = 40;
export const REBOUNDER_X_MAX = 60;
export const REBOUNDER_Y_RANGE = 6; // ±6 y-coords from starting position (defensive stop)

// Shot Attempt Rebounder Positioning
export const SHOT_ATTEMPT_REBOUNDER_Y_RANGE = 10; // ±10 y-coords from rim (shot attempt)

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
