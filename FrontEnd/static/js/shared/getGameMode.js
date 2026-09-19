function franchiseCtx() {
  return typeof window !== 'undefined' ? window.FranchiseContext : null;
}
function liveParams() {
  return franchiseCtx().toSearchParams();
}
function emptyParams() {
  return franchiseCtx().createParams();
}
function currentSearch() {
  const s = liveParams().toString();
  return s ? '?' + s : '';
}
function cloneParams(params) {
  const out = emptyParams();
  if (params && typeof params.forEach === 'function') {
    params.forEach((value, key) => out.set(key, value));
  }
  return out;
}

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
 *   3. franchiseId fallback for callers without scene/URL
 *
 * Standalone Tournament Mode is retired. A leftover mode=tournament value
 * is ignored so Franchise weeks keyed on franchise_id still resolve correctly.
 */
export function getGameMode({ scene, urlParams, franchiseId } = {}) {
  const sceneMode = scene && typeof scene === 'object' ? scene.mode : null;
  if (sceneMode && sceneMode !== 'tournament') return sceneMode;

  let urlMode = null;
  if (urlParams && typeof urlParams.get === 'function') {
    urlMode = urlParams.get('mode');
  } else if (typeof window !== 'undefined' && window.location?.search) {
    urlMode = liveParams().get('mode');
  }
  if (urlMode && urlMode !== 'tournament') return urlMode;

  if (franchiseId) return 'franchise';
  return 'single';
}
