/**
 * Canonical RT color buckets — pair with /css/rt-buckets.css (.rt-low / .rt-mid / .rt-high / .rt-elite).
 *
 * Player RT (set-lineup, roster, team-roster-view): getRtBucketClass
 *   0–40  red, 41–60 yellow, 61–80 green, 81+ blue
 *
 * Recruit RT (recruiting surfaces): getRecruitRtBucketClass
 *   0–29  red, 30–39 yellow, 40–49 green, 50+ blue
 *   Applies to JH recruits only — FR/SO/JR recruits use the player scale
 *   (getRecruitRtBucketClassForYear handles the year switch).
 *
 * Loaded as a classic script (no module export) for ES modules and IIFE pages.
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

  function getRecruitRtBucketClass(rt) {
    var v = Number(rt);
    if (!isFinite(v)) return 'rt-unknown';
    if (v <= 29) return 'rt-low';
    if (v <= 39) return 'rt-mid';
    if (v <= 49) return 'rt-high';
    return 'rt-elite';
  }

  function getRecruitRtBucketClassForYear(rt, year) {
    var normalized = String(year || 'JH').trim().toUpperCase();
    if (normalized === 'JH') return getRecruitRtBucketClass(rt);
    return getRtBucketClass(rt);
  }

  global.getRtBucketClass = getRtBucketClass;
  global.getRecruitRtBucketClass = getRecruitRtBucketClass;
  global.getRecruitRtBucketClassForYear = getRecruitRtBucketClassForYear;
})(typeof window !== 'undefined' ? window : this);
