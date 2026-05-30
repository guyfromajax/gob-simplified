/**
 * FTE v2 tutorial — set-lineup intro + post-lineup feedback modals.
 *
 * Centered Functional-modal chrome (.gob-modal-*) + team-linked Sammy
 * portrait overlapping the top edge. Matches the visual language of the
 * Username modal (the canonical Functional + portrait pattern), simplified
 * to body-only (no input field) since these modals exist to deliver a
 * single message.
 *
 * Two exports:
 *   showLineupIntroModal({ teamName, onDismiss }) — fires once on first
 *     load of set-lineup in tutorial mode, before the user has touched
 *     the slots.
 *   showLineupFeedbackModal({ teamName, message, onConfirm }) — fires
 *     when the user clicks Return To Game with a complete lineup; shows
 *     the algorithm-chosen feedback message and a single CTA to navigate.
 *
 * The lineup-feedback algorithm itself (Talent + 19 qualifiers, random
 * pick from the pool, Unconventional when none qualify) lives in
 * pickLineupFeedbackMessage() below so the modal layer stays UI-only.
 */

import { getTeamSammyImage } from '/js/shared/teamCoachAsset.js';

const STYLESHEETS = [
  '/resource-pages.css',         // canonical .gob-modal-* classes
  '/css/gob-buttons.css',
  '/css/tutorial-lineup-modal.css',
];

function ensureStylesheets() {
  STYLESHEETS.forEach((href) => {
    if (document.querySelector(`link[href="${href}"]`)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    document.head.appendChild(link);
  });
}

function buildModal({ teamName, message, ctaLabel, ctaVariant, onConfirm }) {
  ensureStylesheets();

  const sammySrc = getTeamSammyImage(teamName);
  // Per styleguide: --action (orange) for non-gating (intro Got It),
  // --gate (green) for gating (feedback modal Return To Game IS the
  // actual navigation trigger, so it advances game state).
  const variantClass = ctaVariant === 'gate' ? 'gob-btn--gate' : 'gob-btn--action';

  const overlay = document.createElement('div');
  overlay.className = 'gob-modal-overlay';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.innerHTML = `
    <div class="gob-modal-backdrop"></div>
    <div class="gob-modal-box tutorial-lineup-modal-box">
      <div class="tutorial-lineup-modal-portrait-wrap" aria-hidden="true">
        <img class="tutorial-lineup-modal-portrait" src="${sammySrc}" alt="">
      </div>
      <div class="gob-modal-accent"></div>
      <div class="gob-modal-body tutorial-lineup-modal-body">
        <p class="tutorial-lineup-modal-message">${message}</p>
      </div>
      <div class="gob-modal-actions tutorial-lineup-modal-actions">
        <button type="button" class="gob-btn ${variantClass} tutorial-lineup-modal-cta">${ctaLabel}</button>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);
  // Force reflow so the .is-visible transition runs (matches Functional modal precedent).
  // eslint-disable-next-line no-unused-expressions
  overlay.offsetHeight;
  overlay.classList.add('is-visible');

  const ctaBtn = overlay.querySelector('.tutorial-lineup-modal-cta');

  function close() {
    if (!overlay.parentNode) return;
    overlay.classList.remove('is-visible');
    setTimeout(() => {
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }, 180);
  }

  ctaBtn.addEventListener('click', () => {
    try {
      if (typeof onConfirm === 'function') onConfirm();
    } finally {
      close();
    }
  });

  return { close, element: overlay };
}

export function showLineupIntroModal({ teamName, onDismiss }) {
  return buildModal({
    teamName,
    message: "Here's your moment, Coach. Set your lineup for crunch time.",
    ctaLabel: 'GOT IT',
    ctaVariant: 'action', // non-gating acknowledgement
    onConfirm: onDismiss,
  });
}

export function showLineupFeedbackModal({ teamName, message, onConfirm }) {
  return buildModal({
    teamName,
    message,
    ctaLabel: 'RETURN TO GAME',
    ctaVariant: 'gate', // gating — confirms the lineup and navigates to gameplay
    onConfirm,
  });
}


// =============================================================================
// Lineup-feedback algorithm
// =============================================================================
//
// Documented in fte_system.md §Set-Lineup Algorithm. Source of truth lives
// here; doc mirrors it. If you change the messages or qualifiers, update
// both places.

const ATTRS_IN_PLAY = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ'];

const TALENT_MESSAGE = "You're putting your five best players on the court. Smart.";
const UNCONVENTIONAL_MESSAGE = "A very unconventional lineup, Coach. You're going to keep our opponent very off-balance.";

// Qualifier matchers: each takes the set of "top-2 attribute IDs" (a Set<string>)
// and returns true if it qualifies. If qualified, the paired message is
// added to the candidate pool.
const QUALIFIERS = [
  {
    test: (t) => t.has('SC') && t.has('SH'),
    message: "You're leading with your best scorers, good luck, Coach.",
  },
  {
    test: (t) => t.has('ID') && t.has('OD'),
    message: "You're leading with your best defenders, good luck, Coach.",
  },
  {
    test: (t) => (t.has('SC') || t.has('SH')) && (t.has('ID') || t.has('OD')),
    message: "You're balancing offense and defense, good luck, Coach.",
  },
  {
    test: (t) => t.has('RB') && t.has('ST'),
    message: "You're leading with your strong rebounders. Let's see how well they clean the boards.",
  },
  {
    test: (t) => (t.has('ID') || t.has('OD')) && t.has('ST'),
    message: "You're leading with muscle and defense. You're an intimidator, Coach.",
  },
  {
    test: (t) => (t.has('SH') || t.has('SC')) && t.has('AG'),
    message: "You're leading with your athletic scorers. I like it, Coach.",
  },
  {
    test: (t) => t.has('PS') && t.has('BH'),
    message: "You're leading with fundamentals. I like the discipline, Coach.",
  },
  {
    test: (t) => t.has('ND') && t.has('AG'),
    message: "This lineup is fast and athletic. Our opponent will have a difficult time keeping up with us.",
  },
  {
    test: (t) => (t.has('SC') || t.has('SH')) && t.has('IQ'),
    message: 'This is a smart offensive lineup.',
  },
  {
    test: (t) => (t.has('ID') || t.has('OD')) && t.has('IQ'),
    message: 'This is a smart defensive lineup.',
  },
  {
    // "two of (ST, AG, ND)"
    test: (t) => ['ST', 'AG', 'ND'].filter((k) => t.has(k)).length >= 2,
    message: 'Leading with pure athleticism. I like it, Coach.',
  },
  {
    test: (t) => (t.has('PS') || t.has('BH')) && t.has('IQ'),
    message: 'A very cerebral and disciplined lineup. Good luck, Coach.',
  },
  {
    test: (t) => (t.has('SC') || t.has('SH')) && (t.has('ST') || t.has('AG') || t.has('ND')),
    message: 'This is an athletically focused offensive lineup. Good luck, Coach.',
  },
  {
    test: (t) => (t.has('ID') || t.has('OD')) && (t.has('ST') || t.has('AG') || t.has('ND')),
    message: 'This is an athletically focused defensive lineup. Good luck, Coach.',
  },
  {
    test: (t) => (t.has('SC') || t.has('SH')) && (t.has('BH') || t.has('PS')),
    message: 'This is a technically focused offensive lineup. Good luck, Coach.',
  },
  {
    test: (t) => (t.has('ID') || t.has('OD')) && (t.has('BH') || t.has('PS')),
    message: 'This is a technically focused defensive lineup. Good luck, Coach.',
  },
  {
    test: (t) => (t.has('SC') || t.has('SH')) && t.has('RB'),
    message: 'This is a rebounding focused offensive lineup. Good luck, Coach.',
  },
  {
    test: (t) => (t.has('ID') || t.has('OD')) && t.has('RB'),
    message: 'This is a rebounding focused defensive lineup. Good luck, Coach.',
  },
];

/**
 * Compute the "top 2" set of attribute IDs (by total across the 5 starters).
 * Includes all ties at the #1 OR #2 rank, per the spec — so if 3 attributes
 * share the top spot, all 3 are included; if SC is #1 alone and SH/IQ/ST
 * are tied at #2, all 4 are included.
 *
 * @param {Array<{attributes:object}>} starters — 5 player objects with
 *   anchor_<attr> or <attr> fields on player.attributes
 * @returns {Set<string>}
 */
function computeTopTwoAttributes(starters) {
  const totals = {};
  for (const attr of ATTRS_IN_PLAY) {
    let sum = 0;
    for (const p of starters) {
      const a = p.attributes || {};
      const raw = a[`anchor_${attr}`] ?? a[attr] ?? 0;
      sum += Number(raw) || 0;
    }
    totals[attr] = sum;
  }
  // Sort attribute totals descending. Identify the cutoff value at rank 2
  // (or rank 1 if there's only one distinct value). Include all attributes
  // with totals >= the cutoff.
  const sortedDescUnique = Array.from(new Set(Object.values(totals))).sort((a, b) => b - a);
  const cutoff = sortedDescUnique[1] ?? sortedDescUnique[0] ?? 0;
  const top = new Set();
  for (const attr of ATTRS_IN_PLAY) {
    if (totals[attr] >= cutoff) top.add(attr);
  }
  return top;
}

/**
 * Returns true iff the 5 chosen starters are the top 5 players on the roster
 * by their highest position rating (RT). Ties at the 5th spot: include all
 * ties — the user qualifies for Talent as long as the chosen 5 are among
 * the top-RT-tier players.
 *
 * @param {Array<object>} starters — 5 player objects with position_ratings
 * @param {Array<object>} fullRoster — the full team roster
 */
function isTopFiveRtLineup(starters, fullRoster) {
  if (!Array.isArray(starters) || !Array.isArray(fullRoster)) return false;
  if (starters.length !== 5) return false;
  if (fullRoster.length < 5) return false;
  const rt = (p) => {
    const r = Object.values(p.position_ratings || {});
    return r.length ? Math.max(...r) : -Infinity;
  };
  const sortedRoster = [...fullRoster].sort((a, b) => rt(b) - rt(a));
  const fifthRt = rt(sortedRoster[4]);
  // Top-RT tier = every player whose highest RT >= the 5th-best player's RT.
  // (Captures ties at the cutoff so a 6th player tied with the 5th doesn't
  // make Talent silently impossible.)
  const eligibleIds = new Set(
    sortedRoster.filter((p) => rt(p) >= fifthRt).map((p) => p._id)
  );
  return starters.every((p) => eligibleIds.has(p._id));
}

/**
 * Pick a single lineup-feedback message per the spec:
 *   - Talent qualifies if all 5 chosen starters are top-5-RT.
 *   - Each of the 18 skill-based qualifiers checks against the top-2 attrs.
 *   - Talent + all qualifying skill messages form the candidate pool.
 *   - Pool size 1 → use it. Pool size 2+ → random pick. Pool size 0 → Unconventional.
 *
 * @param {Array<object>} starters — the user's chosen 5 starters
 * @param {Array<object>} fullRoster — the user team's full roster (for Talent check)
 * @returns {string}
 */
export function pickLineupFeedbackMessage(starters, fullRoster) {
  const pool = [];
  if (isTopFiveRtLineup(starters, fullRoster)) pool.push(TALENT_MESSAGE);

  const topTwo = computeTopTwoAttributes(starters);
  for (const q of QUALIFIERS) {
    if (q.test(topTwo)) pool.push(q.message);
  }

  // Debug log so we can verify which qualifiers matched and what the pool
  // looked like before the random pick. Useful for staging walks; cheap
  // to leave in production since this fires once per Return To Game click.
  const picked = pool.length === 0
    ? UNCONVENTIONAL_MESSAGE
    : pool.length === 1
      ? pool[0]
      : pool[Math.floor(Math.random() * pool.length)];
  try {
    console.log('[tutorial][lineup-feedback]', {
      topTwoAttrs: Array.from(topTwo),
      poolSize: pool.length,
      pool,
      picked,
    });
  } catch (_) { /* non-fatal */ }
  return picked;
}
