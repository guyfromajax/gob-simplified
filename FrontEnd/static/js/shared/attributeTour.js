/**
 * FTE v2 — Attribute Tour Mechanic.
 *
 * First-run guided discovery for the Set Lineup roster attributes table.
 * Runs in tutorial mode only, after the "Here's your moment, Coach"
 * intro modal dismisses.
 *
 * Stacking approach: we DIM the surrounding siblings directly instead of
 * laying a full-screen scrim over everything. <thead> z-index is
 * notoriously unreliable against a full-screen overlay (early build of
 * this mechanic had the gold ring + headers rendering UNDER the scrim).
 * Dimming siblings keeps the header row at its natural position — fully
 * lit, ring visible, no stacking-order fragility.
 *
 * What it does:
 *   1. Adds .attribute-tour-dim to caller-specified surrounding elements
 *      (banner, score bar, toggle, tbody, footnote, right panel). Each
 *      drops to opacity 0.30 + pointer-events: none.
 *   2. Adds a shimmer underline cue to each tooltipped header.
 *   3. Mounts a compact Sammy coach-mark just below the header row,
 *      pointing up at it, with a live "X of N explored" counter and a
 *      ghost GOT IT dismiss button.
 *   4. Hovering a header tints it orange and reveals THAT header's existing
 *      tooltip (we don't add new tooltip content — attributeTooltips.js
 *      remains the source of truth). Once hovered, the header tints green
 *      and its shimmer stops.
 *   5. Touch fallback: tap on a header opens its tooltip too. Scoped to
 *      the tour run — no global helper changes.
 *
 * Persistence: sessionStorage flag keyed by tutorial game_id (per-tab,
 * per-tutorial-game). Matches the intro modal's pattern — one mental
 * model for "tutorial UI nudge guards". Within-tutorial nav (set-lineup
 * → game-plan → back) doesn't re-fire (same game_id); a fresh tutorial
 * game wipes the slate. Real users only play one tutorial (server-gated)
 * so they still see the tour exactly once.
 *
 *   import { showAttributeTour } from '/js/shared/attributeTour.js';
 *
 *   showAttributeTour({
 *     headerRow:    <tr|thead element>,                                 // required — the row to spotlight
 *     teamName:     'Bentley-Truman',                                   // for the team-linked Sammy
 *     dimSelectors: ['.lineup-banner-strip', ...],                      // caller-owned list of siblings to dim
 *     persistKey:   `fteV2TutorialAttrTourShown_${gameId}`,             // pass per game_id; default shown below
 *     onDismiss:    () => { ... },                                      // optional callback after dismiss
 *   });
 */

import { getTeamSammyImage } from '/js/shared/teamCoachAsset.js';

const STYLESHEET_HREF = '/css/attribute-tour.css';
const DEFAULT_PERSIST_KEY = 'fteV2TutorialAttrTourShown';

// Same set the canonical attributeTooltips.js helper recognizes — used to
// decide which header cells get the shimmer cue and count toward the
// X of N counter. We import the registry from the helper rather than
// duplicating it; if attributeTooltips.js isn't loaded, we fall back to
// the spec's broad attribute list.
const FALLBACK_ATTR_KEYS = new Set([
  'SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'FT', 'ND', 'IQ',
  'HT', 'WT', 'NG', 'RT',
]);

function ensureStylesheet() {
  if (document.querySelector(`link[href="${STYLESHEET_HREF}"]`)) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = STYLESHEET_HREF;
  document.head.appendChild(link);
}

function alreadySeen(persistKey) {
  try { return sessionStorage.getItem(persistKey) === '1'; }
  catch (_) { return false; }
}

function markSeen(persistKey) {
  try { sessionStorage.setItem(persistKey, '1'); }
  catch (_) { /* private mode etc. — non-fatal */ }
}

function getCellAttrKey(th) {
  // Only match cells whose ENTIRE text content is a known attribute key.
  // This deliberately excludes the Player Name column (which has an
  // inline RT label inside a span) — the tour treats it as a name column,
  // not an attribute column. The user's existing RT tooltip still fires
  // on that label as usual, it just doesn't count toward "X of N explored".
  const direct = (th.textContent || '').trim().toUpperCase();
  if (FALLBACK_ATTR_KEYS.has(direct)) return direct;
  return null;
}

export function showAttributeTour(opts = {}) {
  const headerRow = opts.headerRow;
  if (!headerRow) {
    console.warn('[attribute-tour] headerRow is required');
    return { close: () => {} };
  }
  const persistKey = opts.persistKey || DEFAULT_PERSIST_KEY;
  const onDismiss = typeof opts.onDismiss === 'function' ? opts.onDismiss : null;
  if (alreadySeen(persistKey)) return { close: () => {}, skipped: true };

  ensureStylesheet();

  // Identify the tooltipped header cells in source order. Lift ALL header
  // cells (so the row reads as a single lit band), but only attach the
  // shimmer cue + hover bookkeeping to ones that have known tooltips.
  const thCells = Array.from(headerRow.querySelectorAll('th'));
  if (thCells.length === 0) {
    console.warn('[attribute-tour] no <th> cells found in headerRow');
    return { close: () => {} };
  }
  const cuedCells = []; // [{ th, attrKey }]
  thCells.forEach((th, idx) => {
    th.classList.add('attribute-tour__lifted');
    if (idx === 0) th.classList.add('is-first');
    if (idx === thCells.length - 1) th.classList.add('is-last');
    const attrKey = getCellAttrKey(th);
    if (attrKey) {
      th.classList.add('is-cued');
      cuedCells.push({ th, attrKey });
    }
  });
  // Also lift the parent <thead> if we can find it — keeps the gold band
  // behaving as a single stacking context above the scrim.
  const thead = headerRow.tagName === 'THEAD' ? headerRow : headerRow.closest('thead');
  if (thead) thead.classList.add('attribute-tour__lifted');

  document.body.classList.add('attribute-tour-active');

  // Dim siblings. Caller passes a list of CSS selectors for the elements
  // that should fade back during the tour (banner, score bar, table body,
  // right-hand panel, etc.). Each matched element gets .attribute-tour-dim
  // applied — opacity drops + pointer-events disable so the user can't
  // accidentally click into game-plan/etc. mid-tour. The header row is
  // intentionally NOT in this list; it stays at its natural position with
  // full opacity and the gold ring/glow.
  const dimSelectors = Array.isArray(opts.dimSelectors) ? opts.dimSelectors : [];
  const dimmedEls = [];
  dimSelectors.forEach((sel) => {
    document.querySelectorAll(sel).forEach((el) => {
      el.classList.add('attribute-tour-dim');
      dimmedEls.push(el);
    });
  });

  // Sammy coach-mark.
  const sammyImg = getTeamSammyImage(opts.teamName);
  const total = cuedCells.length;
  const sammy = document.createElement('div');
  sammy.className = 'attribute-tour__sammy';
  sammy.setAttribute('role', 'dialog');
  sammy.setAttribute('aria-live', 'polite');
  sammy.innerHTML = `
    <img class="attribute-tour__sammy-portrait" src="${sammyImg}" alt="">
    <div class="attribute-tour__sammy-body">
      <div class="attribute-tour__sammy-eyebrow">QUICK TOUR</div>
      <p class="attribute-tour__sammy-text">These are your player attributes. <strong>Hover any column header</strong> to see what it tracks.</p>
    </div>
    <div class="attribute-tour__sammy-foot">
      <span class="attribute-tour__sammy-count" id="attribute-tour-count">0 of ${total} explored</span>
      <button type="button" class="attribute-tour__sammy-dismiss" id="attribute-tour-dismiss">GOT IT</button>
    </div>
  `;
  document.body.appendChild(sammy);

  const countEl = sammy.querySelector('#attribute-tour-count');
  const dismissBtn = sammy.querySelector('#attribute-tour-dismiss');

  // Position Sammy just below the header row. Re-anchor on resize/scroll
  // so the bubble tracks if the page layout shifts.
  function positionSammy() {
    const rect = headerRow.getBoundingClientRect();
    const sammyRect = sammy.getBoundingClientRect();
    const margin = 16;
    const left = Math.max(
      12,
      Math.min(
        rect.left + rect.width / 2 - sammyRect.width / 2,
        window.innerWidth - sammyRect.width - 12
      )
    );
    const top = rect.bottom + margin;
    sammy.style.left = `${left}px`;
    sammy.style.top = `${top}px`;
    // Arrow anchored under the header row's center, relative to bubble.
    const arrowX = rect.left + rect.width / 2 - left;
    sammy.style.setProperty('--sammy-arrow-x', `${Math.max(20, Math.min(arrowX, sammyRect.width - 20))}px`);
  }

  // Reveal sammy on next frame so the entrance transition runs.
  requestAnimationFrame(() => {
    sammy.classList.add('is-visible');
    // Position after the first paint so getBoundingClientRect is accurate.
    requestAnimationFrame(positionSammy);
  });

  const reposition = () => positionSammy();
  window.addEventListener('resize', reposition);
  window.addEventListener('scroll', reposition, true);

  // Explored tracking.
  const explored = new Set();
  function markExplored(attrKey, th) {
    if (explored.has(attrKey)) return;
    explored.add(attrKey);
    th.classList.add('is-explored');
    const n = explored.size;
    countEl.textContent = `${n} of ${total} explored`;
    if (n >= total) {
      countEl.classList.add('is-complete');
      dismissBtn.classList.add('is-emphasized');
    }
  }

  // Hover + touch handlers. The existing attributeTooltips.js already
  // attaches mouseenter/mouseleave handlers that show the tooltip — we
  // only need to also mark explored. For touch: simulate a hover on tap
  // (mouseenter event so the existing helper opens its tooltip).
  const cleanupFns = [];
  cuedCells.forEach(({ th, attrKey }) => {
    const onEnter = () => markExplored(attrKey, th);
    th.addEventListener('mouseenter', onEnter);
    cleanupFns.push(() => th.removeEventListener('mouseenter', onEnter));

    // Touch: tap to open tooltip (via synthesized mouseenter) + mark explored.
    let touched = false;
    const onTouch = (e) => {
      touched = true;
      markExplored(attrKey, th);
      try {
        const enter = new MouseEvent('mouseenter', { bubbles: false, cancelable: true });
        th.dispatchEvent(enter);
      } catch (_) { /* IE-edge — ignore */ }
      // Auto-dismiss the tooltip ~3s later (mouseleave) so taps elsewhere
      // don't leave a stuck bubble.
      setTimeout(() => {
        if (!touched) return;
        try {
          const leave = new MouseEvent('mouseleave', { bubbles: false, cancelable: true });
          th.dispatchEvent(leave);
        } catch (_) {}
        touched = false;
      }, 3000);
    };
    th.addEventListener('touchstart', onTouch, { passive: true });
    cleanupFns.push(() => th.removeEventListener('touchstart', onTouch));
  });

  function close() {
    markSeen(persistKey);
    sammy.classList.remove('is-visible');
    // Lift the dim immediately so the page comes back into focus while
    // the Sammy bubble fades — feels more responsive than waiting for
    // both to fade together.
    dimmedEls.forEach((el) => el.classList.remove('attribute-tour-dim'));
    window.removeEventListener('resize', reposition);
    window.removeEventListener('scroll', reposition, true);
    cleanupFns.forEach((fn) => fn());
    setTimeout(() => {
      if (sammy.parentNode) sammy.parentNode.removeChild(sammy);
      // Restore the table — strip every class we added.
      thCells.forEach((th) => {
        th.classList.remove('attribute-tour__lifted', 'is-cued', 'is-explored', 'is-first', 'is-last');
      });
      if (thead) thead.classList.remove('attribute-tour__lifted');
      document.body.classList.remove('attribute-tour-active');
      if (onDismiss) onDismiss();
    }, 240);
  }

  dismissBtn.addEventListener('click', close);

  return { close, element: sammy };
}
