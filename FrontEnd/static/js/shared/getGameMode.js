/**
 * Single source of truth for resolving the game mode in the court / EOG paths.
 *
 * Background: the value was previously derived inline at four callsites of
 * showGameCompletionPopup with three different patterns. The 'tutorial' branch
 * was only added to one of them, which let the tutorial Box Score / Locker Room
 * routing regress whenever the "no-animate" Play-Quarter path completed a game.
 * Read mode from one place, here, so the next caller can't drift.
 *
 * Precedence:
 *   1. scene.mode (already set on GameScene from sceneData.mode in init())
 *   2. urlParams.get('mode')  — canonical for fresh page loads
 *   3. tournamentId/franchiseId fallback for legacy callers without scene/URL
 */
export function getGameMode({ scene, urlParams, tournamentId, franchiseId } = {}) {
  const sceneMode = scene && typeof scene === 'object' ? scene.mode : null;
  if (sceneMode) return sceneMode;

  let urlMode = null;
  if (urlParams && typeof urlParams.get === 'function') {
    urlMode = urlParams.get('mode');
  } else if (typeof window !== 'undefined' && window.location?.search) {
    urlMode = new URLSearchParams(window.location.search).get('mode');
  }
  if (urlMode) return urlMode;

  if (tournamentId) return 'tournament';
  if (franchiseId) return 'franchise';
  return 'single';
}
