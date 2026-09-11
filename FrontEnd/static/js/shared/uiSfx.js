/**
 * Shared UI sound effects.
 *
 * `playSound` was copy-pasted into six files (set-lineup, game-plan,
 * franchise-select-team, authBarInit, commandCenterTabs, gobTutorialNav) before
 * this module existed. The duplication is why FTE v3's new screens shipped silent:
 * there was nothing to import, so nothing got wired.
 *
 * Named constants rather than raw filenames at call sites, so "the advance sound"
 * is one edit away from changing everywhere instead of a grep for .wav strings.
 */

/** Primary CTA that moves the user forward a screen. */
export const SFX_ADVANCE = 'confirm-1-lowervol.wav';
/** Light tick for selecting within a screen (a card, a tab, a row). */
export const SFX_SELECT = 'click-tiny.wav';
/** Heavier click for committing a choice that defines the run (your program). */
export const SFX_COMMIT = 'click-beep.wav';

/**
 * Fire and forget. Never throws and never blocks navigation — autoplay policy
 * rejects `play()` until the user has interacted, and a missing file must not
 * take a screen down. A CTA that navigates should not await this.
 */
export function playSfx(filename, volume = 0.7) {
  try {
    const base = (typeof window !== 'undefined'
      && window.API_CONFIG
      && typeof window.API_CONFIG.buildStaticPath === 'function')
      ? window.API_CONFIG.buildStaticPath('/sounds/')
      : '/sounds/';
    const a = new Audio(base + encodeURIComponent(filename));
    a.volume = volume;
    a.play().catch(() => {});
  } catch (_) { /* non-fatal */ }
}

export function playAdvance() { playSfx(SFX_ADVANCE); }
export function playSelect() { playSfx(SFX_SELECT); }
export function playCommit() { playSfx(SFX_COMMIT); }
