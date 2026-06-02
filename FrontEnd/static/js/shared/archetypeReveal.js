/**
 * First coaching-archetype reveal — one-time celebratory Moment modal.
 *
 * Fires on the Franchise Command Center the first time a coach has earned an
 * archetype: `lead_archetype` is set (>= 1 real, non-tutorial game) AND
 * `archetype_reveal_seen === false`. On show we PATCH the seen flag so it never
 * appears again on any device/session. Tutorial games never set lead_archetype,
 * so they can't trigger it.
 *
 * Moment-modal styling per Styleguide §Moment Modals.
 */
(function () {
  'use strict';

  var shown = false;

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

  function injectStyles() {
    if (document.getElementById('arch-reveal-styles')) return;
    var css = [
      '.arch-reveal-overlay{position:fixed;inset:0;z-index:10050;display:none;align-items:center;justify-content:center;}',
      '.arch-reveal-overlay.is-visible{display:flex;}',
      '.arch-reveal-backdrop{position:absolute;inset:0;background:rgba(0,0,0,0.72);backdrop-filter:blur(3px);}',
      '.arch-reveal-box{position:relative;z-index:1;width:min(560px,calc(100% - 40px));background:rgba(13,17,36,0.97);',
      'border:1px solid rgba(255,255,255,0.12);border-radius:16px;padding:34px 30px 26px;text-align:center;',
      'box-shadow:0 24px 60px rgba(0,0,0,0.55),inset 0 1px 0 rgba(255,255,255,0.05);',
      'transform:scale(0.96);opacity:0;transition:transform 200ms ease,opacity 200ms ease;}',
      '.arch-reveal-overlay.is-entered .arch-reveal-box{transform:scale(1);opacity:1;}',
      '.arch-reveal-close{position:absolute;top:12px;right:12px;width:30px;height:30px;border:none;border-radius:8px;',
      'background:transparent;color:rgba(255,255,255,0.35);font-size:18px;cursor:pointer;line-height:1;}',
      '.arch-reveal-close:hover{color:#fff;background:rgba(255,255,255,0.06);}',
      '.arch-reveal-badge{width:108px;height:108px;margin:6px auto 16px;display:flex;align-items:center;justify-content:center;',
      'border-radius:999px;background:radial-gradient(circle at 50% 45%,rgba(247,148,32,0.28),rgba(247,148,32,0) 68%);',
      'filter:drop-shadow(0 0 18px rgba(247,148,32,0.35));}',
      '.arch-reveal-headline{font-family:\'Bebas Neue Pro\',\'Bebas Neue\',sans-serif;font-weight:700;font-size:34px;',
      'letter-spacing:0.04em;color:#fff;margin:0 0 12px;}',
      '.arch-reveal-body{font-family:\'Inter\',sans-serif;font-size:14px;line-height:1.55;color:rgba(255,255,255,0.62);',
      'margin:0 auto 22px;max-width:420px;}',
      '.arch-reveal-body strong{color:#fff;font-weight:700;}',
      '.arch-reveal-actions{display:flex;gap:12px;}',
      '.arch-reveal-btn-primary,.arch-reveal-btn-secondary{appearance:none;height:46px;border-radius:10px;',
      'font-family:\'Bebas Neue Pro\',\'Bebas Neue\',sans-serif;font-size:17px;letter-spacing:0.04em;cursor:pointer;',
      'display:inline-flex;align-items:center;justify-content:center;text-decoration:none;transition:filter .14s ease,background .14s ease;}',
      '.arch-reveal-btn-primary{flex:2;background:#F79420;border:1px solid rgba(247,148,32,0.45);color:#15181f;}',
      '.arch-reveal-btn-primary:hover{filter:brightness(1.06);}',
      '.arch-reveal-btn-secondary{flex:1;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.14);color:rgba(255,255,255,0.85);}',
      '.arch-reveal-btn-secondary:hover{background:rgba(255,255,255,0.1);color:#fff;}',
    ].join('');
    var style = document.createElement('style');
    style.id = 'arch-reveal-styles';
    style.textContent = css;
    document.head.appendChild(style);
  }

  function markSeen() {
    try {
      if (window.__gobAuthMeData) window.__gobAuthMeData.archetype_reveal_seen = true;
      if (typeof API_CONFIG === 'undefined' || !API_CONFIG.buildUrl || !API_CONFIG.getAuthHeaders) return;
      fetch(API_CONFIG.buildUrl('/api/auth/archetype-reveal-seen'), {
        method: 'PATCH',
        headers: Object.assign({ 'Content-Type': 'application/json' }, API_CONFIG.getAuthHeaders()),
      }).catch(function () {});
    } catch (e) {}
  }

  function buildModal(meta, leadKey) {
    injectStyles();
    var overlay = document.createElement('div');
    overlay.className = 'arch-reveal-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', (meta && meta.name) || 'Coaching archetype');

    var revealName = (meta && meta.reveal_name) || (meta && meta.name) || 'Unconventional';
    var headline = (meta && meta.name) || 'Your Archetype';

    overlay.innerHTML = [
      '<div class="arch-reveal-backdrop" data-dismiss></div>',
      '<div class="arch-reveal-box">',
      '  <button type="button" class="arch-reveal-close" data-dismiss aria-label="Close">&times;</button>',
      '  <div class="arch-reveal-badge" id="arch-reveal-badge"></div>',
      '  <h2 class="arch-reveal-headline"></h2>',
      '  <p class="arch-reveal-body">Based on your coaching style, you\'re now known as the <strong></strong> coaching archetype. Note this archetype handle will evolve as you develop your program\'s identity.</p>',
      '  <div class="arch-reveal-actions">',
      '    <a class="arch-reveal-btn-primary" href="/coaching-archetypes.html">Explore Coaching Archetypes</a>',
      '    <button type="button" class="arch-reveal-btn-secondary" data-dismiss>Go to Locker Room</button>',
      '  </div>',
      '</div>'
    ].join('');

    overlay.querySelector('.arch-reveal-headline').textContent = headline;
    overlay.querySelector('.arch-reveal-body strong').textContent = revealName;

    var badgeHost = overlay.querySelector('#arch-reveal-badge');
    var badge = window.GOBArchetype && window.GOBArchetype.createBadge(leadKey, 88);
    if (badge) badgeHost.appendChild(badge);

    function close() {
      overlay.classList.remove('is-entered');
      setTimeout(function () { if (overlay.parentNode) overlay.parentNode.removeChild(overlay); }, 200);
    }
    overlay.addEventListener('click', function (e) {
      if (e.target && e.target.hasAttribute('data-dismiss')) {
        // Primary link navigates on its own; secondary/close/backdrop just close.
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
    // Entrance: reflow then add the entered class so the scale animates.
    overlay.classList.add('is-visible');
    void overlay.offsetWidth;
    overlay.classList.add('is-entered');
  }

  function maybeShow(me) {
    if (shown || !me) return;
    if (me.archetype_reveal_seen) return;
    ensureBadgeScript().then(function () {
      if (!window.GOBArchetype) return;
      var leadKey = window.GOBArchetype.leadFrom(me);
      if (!leadKey) return; // no real game yet → no reveal
      if (shown) return;
      shown = true;
      markSeen(); // persist immediately, regardless of how it's dismissed
      window.GOBArchetype.ensureManifest().then(function (m) {
        var meta = null;
        if (m && Array.isArray(m.archetypes)) {
          meta = m.archetypes.filter(function (a) { return a.id === leadKey; })[0] || null;
        }
        buildModal(meta, leadKey);
      });
    });
  }

  // Only on the Franchise Command Center.
  if ((window.location.pathname || '').indexOf('franchise-command-center') === -1) return;

  if (window.__gobAuthMeData) maybeShow(window.__gobAuthMeData);
  window.addEventListener('gob:auth-me-loaded', function (e) {
    maybeShow((e && e.detail) || window.__gobAuthMeData);
  });
})();
