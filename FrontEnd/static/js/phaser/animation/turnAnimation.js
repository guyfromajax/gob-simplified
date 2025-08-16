/**
 * Legacy wrapper for turn animation.
 *
 * Some pages still load this file as a classic script which cannot parse
 * ES module syntax like `export`.  The actual implementation lives in
 * `playTurnAnimation.js` which uses ES modules.
 *
 * This stub dynamically imports the modern module and exposes
 * `playTurnAnimation` on the global `window` object for any legacy callers.
 */
(async () => {
  try {
    const module = await import('./playTurnAnimation.js');
    // Expose for legacy consumers expecting a global function
    if (typeof window !== 'undefined') {
      window.playTurnAnimation = module.playTurnAnimation;
    }
  } catch (err) {
    console.error('Failed to load playTurnAnimation module', err);
  }
})();
