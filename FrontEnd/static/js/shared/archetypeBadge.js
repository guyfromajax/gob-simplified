/**
 * Shared coaching-archetype badge.
 *
 * One resolver used everywhere a coach badge appears (account modal, leaderboards,
 * reveal modal, explainer). Always resolves `archetypeKey -> svg/<key>.svg`; never
 * hardcodes icon markup. Callers pass `user.lead_archetype`.
 *
 * Exposes `window.GOBArchetype`:
 *   - badgeHtml(key, size)   -> HTML string (for innerHTML-based renderers)
 *   - createBadge(key, size) -> HTMLImageElement | null (for DOM renderers)
 *   - svgUrl(key)            -> the SVG path
 *   - nameFor(key)           -> archetype display name (manifest, with humanized fallback)
 *   - ensureManifest()       -> Promise<manifest|null>
 *
 * Empty/falsy key -> renders nothing. Unknown key -> the <img> hides itself on
 * load error (no broken-image icon).
 */
(function () {
  'use strict';

  var BASE = '/images/archetype_icons';
  var DEFAULT_SIZE = 22;
  var manifestPromise = null;
  var nameByKey = {};

  function humanize(key) {
    return String(key || '')
      .split('_')
      .map(function (w) { return w ? w.charAt(0).toUpperCase() + w.slice(1) : w; })
      .join(' ');
  }

  function ensureManifest() {
    if (!manifestPromise) {
      manifestPromise = fetch(BASE + '/archetypes.json')
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (m) {
          if (m && Array.isArray(m.archetypes)) {
            m.archetypes.forEach(function (a) { if (a && a.id) nameByKey[a.id] = a.name; });
            window.__gobArchetypeManifest = m;
          }
          return m;
        })
        .catch(function () { return null; });
    }
    return manifestPromise;
  }

  function nameFor(key) { return nameByKey[key] || humanize(key); }
  function svgUrl(key) { return BASE + '/svg/' + encodeURIComponent(String(key)) + '.svg'; }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function styleFor(size) {
    return 'width:' + size + 'px;height:' + size + 'px;object-fit:contain;display:inline-block;vertical-align:middle;flex:0 0 auto;';
  }

  function badgeHtml(key, size) {
    if (!key) return '';
    size = size || DEFAULT_SIZE;
    var nm = nameFor(key);
    return '<img class="archetype-badge" src="' + svgUrl(key) + '" alt="' + escapeHtml(nm) + '"'
      + ' width="' + size + '" height="' + size + '"'
      + ' style="' + styleFor(size) + '" data-archetype="' + escapeHtml(key) + '"'
      + ' loading="lazy" onerror="this.style.display=\'none\'">';
  }

  function createBadge(key, size) {
    if (!key) {
      if (window.console && console.warn) console.warn('[ArchetypeBadge] empty/missing archetypeKey — nothing rendered');
      return null;
    }
    size = size || DEFAULT_SIZE;
    var img = document.createElement('img');
    img.className = 'archetype-badge';
    img.src = svgUrl(key);
    img.width = size;
    img.height = size;
    img.style.cssText = styleFor(size);
    img.setAttribute('data-archetype', key);
    img.setAttribute('loading', 'lazy');
    var nm = nameFor(key);
    img.alt = nm;
    img.setAttribute('aria-label', nm);
    img.addEventListener('error', function () { img.style.display = 'none'; });
    // Refine accessible name once the manifest is available.
    ensureManifest().then(function () {
      if (nameByKey[key]) { img.alt = nameByKey[key]; img.setAttribute('aria-label', nameByKey[key]); }
    });
    return img;
  }

  /**
   * Resolve the badge key for a user object (e.g. /api/auth/me or a leaderboard row).
   * Prefers the denormalized `lead_archetype`; falls back to the highest count in
   * `archetypes` for older docs; "" (no badge) when there are no games.
   */
  function leadFrom(user) {
    if (!user) return '';
    if (user.lead_archetype) return String(user.lead_archetype);
    var arche = user.archetypes;
    if (!arche || typeof arche !== 'object') return '';
    var best = '', bestN = 0;
    Object.keys(arche).forEach(function (k) {
      if (k === 'total') return;
      var n = Number(arche[k]) || 0;
      if (n > bestN) { bestN = n; best = k; }
    });
    return bestN > 0 ? best : '';
  }

  ensureManifest(); // warm the cache early

  window.GOBArchetype = {
    ensureManifest: ensureManifest,
    badgeHtml: badgeHtml,
    createBadge: createBadge,
    svgUrl: svgUrl,
    nameFor: nameFor,
    leadFrom: leadFrom,
  };
})();
