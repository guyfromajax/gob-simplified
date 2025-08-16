// Compatibility wrapper for legacy script imports.
// Dynamically loads playTurnAnimation and exposes it on `window`.
(async () => {
  const module = await import('./playTurnAnimation.js');
  if (typeof window !== 'undefined') {
    window.playTurnAnimation = module.playTurnAnimation;
  }
})();
