/**
 * Canonical RT (player rating) color bucket per Styleguide §Attribute Bar Scale.
 * Apply consistently wherever a player rating is displayed as text.
 *
 *   0–40  red (#ff6d6d)       → .rt-low
 *   41–60 yellow (#FFD700)    → .rt-mid
 *   61–80 green (#34EC27)     → .rt-high
 *   81+   light blue (#4A90D9)→ .rt-elite
 *   non-numeric / null        → .rt-unknown
 *
 * Pair with /css/rt-buckets.css for the color rules. Loaded as a classic
 * script (no module export) so it works from both ES modules and IIFE
 * pages — exposes window.getRtBucketClass.
 */
(function (global) {
  function getRtBucketClass(rt) {
    var v = Number(rt);
    if (!isFinite(v)) return 'rt-unknown';
    if (v <= 40) return 'rt-low';
    if (v <= 60) return 'rt-mid';
    if (v <= 80) return 'rt-high';
    return 'rt-elite';
  }
  global.getRtBucketClass = getRtBucketClass;
})(typeof window !== 'undefined' ? window : this);
