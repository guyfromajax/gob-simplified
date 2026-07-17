/**
 * Shared court-entry classification for MGR / live quarter boot.
 *
 * Single authority for bootGame.js and loadGameStats.js so probe/publish of
 * resume-state and Resume Game modal eligibility cannot diverge.
 *
 * Contract: Mid_Game_Resume_System.md → Court Boot Classifier.
 */

export const COURT_BOOT_MODES = Object.freeze({
  LIVE_QUARTER_ENTRY: 'live_quarter_entry',
  COLD_RESUME_ENTRY: 'cold_resume_entry',
  ANCHOR_RESTORE_ENTRY: 'anchor_restore_entry',
  TIMEOUT_DIRECT_ENTRY: 'timeout_direct_entry',
  NORMAL_ENTRY: 'normal_entry',
});

/**
 * @param {URLSearchParams|Object} params
 * @returns {string} one of COURT_BOOT_MODES
 */
export function classifyCourtBootMode(params) {
  const get = (key) =>
    typeof params.get === 'function' ? params.get(key) : params[key];

  const quarterBreakFrom = get('quarter_break_from');
  const liveQuarterMarker =
    quarterBreakFrom === 'play_quarter' || quarterBreakFrom === 'sim_quarter';
  if (liveQuarterMarker) return COURT_BOOT_MODES.LIVE_QUARTER_ENTRY;

  // Cold / restore flags outrank lineup_checkpoint (MGR Set Lineup returns
  // also set lineup_checkpoint=true).
  if (get('active_resume') === 'true') return COURT_BOOT_MODES.COLD_RESUME_ENTRY;
  if (get('resume_from_anchor') === 'true' || get('consume_resume_anchor') === 'true') {
    return COURT_BOOT_MODES.ANCHOR_RESTORE_ENTRY;
  }
  if (get('resume_from_timeout') === 'true') {
    return COURT_BOOT_MODES.TIMEOUT_DIRECT_ENTRY;
  }

  // In-session Set Lineup → court return (live quarter break). Durable
  // resume_anchor may exist from the stoppage just left; do not treat as MGR.
  // quarter_break_from may have been dropped by a side hop; lineup_checkpoint
  // is the explicit "just left set-lineup" signal (consumed after quarter start).
  if (
    get('lineup_checkpoint') === 'true' &&
    quarterBreakFrom !== 'mid_game_resume'
  ) {
    return COURT_BOOT_MODES.LIVE_QUARTER_ENTRY;
  }

  return COURT_BOOT_MODES.NORMAL_ENTRY;
}

/**
 * Whether court boot / stats hydration may probe or publish /resume-state
 * for the Resume Game modal.
 *
 * @param {string} bootMode
 * @param {URLSearchParams|Object} params
 * @returns {boolean}
 */
export function shouldProbeResumeStateForBoot(bootMode, params) {
  const get = (key) =>
    typeof params.get === 'function' ? params.get(key) : params[key];

  if (bootMode === COURT_BOOT_MODES.LIVE_QUARTER_ENTRY) return false;
  if (bootMode === COURT_BOOT_MODES.TIMEOUT_DIRECT_ENTRY) return false;
  if (get('consume_resume_anchor') === 'true') return false;

  return (
    bootMode === COURT_BOOT_MODES.COLD_RESUME_ENTRY ||
    bootMode === COURT_BOOT_MODES.ANCHOR_RESTORE_ENTRY ||
    bootMode === COURT_BOOT_MODES.NORMAL_ENTRY
  );
}

export function isLiveQuarterBootMode(bootMode) {
  return bootMode === COURT_BOOT_MODES.LIVE_QUARTER_ENTRY;
}
