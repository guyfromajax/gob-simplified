/**
 * Coaching-archetype EVOLUTION modal — "Hey Coach, you have evolved…".
 *
 * Fires on the Franchise Command Center when a coach's lead archetype *changed*
 * from a prior one (the very first archetype is handled by archetypeReveal.js).
 * The change is detected server-side in save_result and surfaced as
 * `me.archetype_evolution_pending` (the new archetype key).
 *
 * Lowest priority + skip-permanently: the FCC orchestrator decides whether any
 * higher-priority modal claimed this visit and calls `run(competing)`. Either way
 * the pending flag is consumed (PATCH /api/auth/archetype-evolution-seen) so the
 * change is never announced again — shown only on a clean visit.
 *
 * Reuses the first-reveal modal's layout/styles (same `.arch-reveal-*` classes).
 */
(function () {
  'use strict';

  if ((window.location.pathname || '').indexOf('franchise-command-center') === -1) return;

  var ran = false;

  function ensureBadgeScript() {
    if (window.GOBArchetype) return Promise.resolve();
    if (window.__gobArchetypeBadgeLoading) return window.__gobArchetypeBadgeLoading;
    window.__gobArchetypeBadgeLoading = new Promise(function (resolve) {
      var s = document.createElement('script');
      s.src = '/js/shared/archetypeBadge.js';
      s.onload = resolve; s.onerror = resolve;
      document.head.appendChild(s);
    });
    return window.__gobArchetypeBadgeLoading;
  }

  function clearPending(me) {
    try {
      if (me) me.archetype_evolution_pending = '';
      if (window.__gobAuthMeData) window.__gobAuthMeData.archetype_evolution_pending = '';
      if (typeof API_CONFIG === 'undefined' || !API_CONFIG.buildUrl || !API_CONFIG.getAuthHeaders) return;
      fetch(API_CONFIG.buildUrl('/api/auth/archetype-evolution-seen'), {
        method: 'PATCH',
        headers: Object.assign({ 'Content-Type': 'application/json' }, API_CONFIG.getAuthHeaders()),
      }).catch(function () {});
    } catch (e) {}
  }

  function buildModal(meta, leadKey) {
    if (typeof window.GOBArchRevealInjectStyles === 'function') window.GOBArchRevealInjectStyles();

    var name = (meta && meta.name) || 'a new archetype';
    var overlay = document.createElement('div');
    overlay.className = 'arch-reveal-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', name);

    overlay.innerHTML = [
      '<div class="arch-reveal-backdrop" data-dismiss></div>',
      '<div class="arch-reveal-box">',
      '  <button type="button" class="arch-reveal-close" data-dismiss aria-label="Close">&times;</button>',
      '  <div class="arch-reveal-badge" id="arch-evo-badge"></div>',
      '  <h2 class="arch-reveal-headline"></h2>',
      '  <p class="arch-reveal-body">Hey Coach, you have evolved your coaching archetype to <strong></strong>.</p>',
      '  <div class="arch-reveal-actions">',
      '    <a class="arch-reveal-btn-primary" href="/coaching-archetypes.html">Explore Coaching Archetypes</a>',
      '    <button type="button" class="arch-reveal-btn-secondary" data-dismiss>Go to Locker Room</button>',
      '  </div>',
      '</div>'
    ].join('');

    overlay.querySelector('.arch-reveal-headline').textContent = name;
    overlay.querySelector('.arch-reveal-body strong').textContent = name;

    var badgeHost = overlay.querySelector('#arch-evo-badge');
    var badge = window.GOBArchetype && window.GOBArchetype.createBadge(leadKey, 88);
    if (badge) badgeHost.appendChild(badge);

    function close() {
      overlay.classList.remove('is-entered');
      setTimeout(function () { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); }, 200);
    }
    overlay.addEventListener('click', function (e) {
      if (e.target && e.target.hasAttribute('data-dismiss')) {
        if (e.target.classList.contains('arch-reveal-btn-secondary')
            || e.target.classList.contains('arch-reveal-close')
            || e.target.classList.contains('arch-reveal-backdrop')) {
          e.preventDefault();
          close();
        }
      }
    });
    document.addEventListener('keydown', function onEsc(e) {
      if (e.key === 'Escape') { document.removeEventListener('keydown', onEsc); close(); }
    });

    document.body.appendChild(overlay);
    overlay.classList.add('is-visible');
    void overlay.offsetWidth;
    overlay.classList.add('is-entered');
  }

  function present(leadKey) {
    ensureBadgeScript().then(function () {
      if (!window.GOBArchetype) return;
      window.GOBArchetype.ensureManifest().then(function (m) {
        var meta = null;
        if (m && Array.isArray(m.archetypes)) {
          meta = m.archetypes.filter(function (a) { return a.id === leadKey; })[0] || null;
        }
        buildModal(meta, leadKey);
      });
    });
  }

  function withMe(cb) {
    if (window.__gobAuthMeData) { cb(window.__gobAuthMeData); return; }
    window.addEventListener('gob:auth-me-loaded', function once(e) {
      window.removeEventListener('gob:auth-me-loaded', once);
      cb((e && e.detail) || window.__gobAuthMeData);
    });
  }

  // Called once by the FCC orchestrator after the modal sequence settles.
  // `competing` = a higher-priority modal claimed this visit.
  function run(competing) {
    if (ran) return;
    ran = true;
    withMe(function (me) {
      var key = me && me.archetype_evolution_pending;
      if (!key) return;          // nothing pending
      clearPending(me);          // consume regardless of shown/skipped (skip-permanently)
      if (competing) return;     // a higher-priority modal owns this visit → skip
      present(key);
    });
  }

  window.ArchetypeEvolutionModal = { run: run };
})();
