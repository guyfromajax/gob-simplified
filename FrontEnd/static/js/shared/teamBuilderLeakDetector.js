/**
 * Team Builder replaced-name DOM leak detector (dev / staging).
 *
 * Invariant: the replaced program's core name must not appear in rendered DOM
 * except the allowlisted FCC orientation line (#tb-orientation).
 *
 * Enable: localhost / staging hosts (API_CONFIG.isCaptureEnv), or
 *   localStorage.TB_LEAK_DETECTOR = '1'
 * Disable: localStorage.TB_LEAK_DETECTOR = '0'
 *
 * On hit: paints a fixed on-screen banner listing offending elements (console
 * alone is invisible during play).
 */
(function (global) {
  'use strict';

  var ALLOWLISTED_SELECTORS = ['#tb-orientation', '#tb-leak-banner'];
  var ORIENTATION_RE = /replacing\s+.+\s+in\s+this\s+franchise/i;
  var BANNER_ID = 'tb-leak-banner';
  // Escape hatch only — prefer tightening match rules over growing this set.
  var ALLOWLISTED_DERIVED_NEEDLES = {};
  var TOKEN_SPLIT_RE = /[^A-Za-z0-9]+/;
  // Session dedupe: one report per (node identity + needle) so mutation re-scans
  // and transient event cards don't spam the same leak as many banners.
  var reportedLeakKeys = Object.create(null);

  function envEnabled() {
    try {
      var flag = global.localStorage && global.localStorage.getItem('TB_LEAK_DETECTOR');
      if (flag === '0' || flag === 'false') return false;
      if (flag === '1' || flag === 'true') return true;
    } catch (e) { /* ignore */ }
    if (global.API_CONFIG && typeof global.API_CONFIG.isCaptureEnv === 'function') {
      return !!global.API_CONFIG.isCaptureEnv();
    }
    var host = (global.location && global.location.hostname) || '';
    return host === 'localhost' || host === '127.0.0.1';
  }

  function resolveReplacedName(options) {
    options = options || {};
    if (options.replacedName) return String(options.replacedName).trim();
    try {
      if (typeof global.getActiveTeamBuilderVisual === 'function') {
        var v = global.getActiveTeamBuilderVisual();
        if (v && v.replaced_name) return String(v.replaced_name).trim();
      }
    } catch (e1) { /* ignore */ }
    try {
      if (global.FranchiseLS && typeof global.FranchiseLS.getTeamBuilderVisual === 'function') {
        var cached = global.FranchiseLS.getTeamBuilderVisual();
        if (cached && cached.replaced_name) return String(cached.replaced_name).trim();
      }
    } catch (e2) { /* ignore */ }
    try {
      var attr = global.document && global.document.body &&
        global.document.body.getAttribute('data-tb-replaced-name');
      if (attr) return String(attr).trim();
    } catch (e3) { /* ignore */ }
    return '';
  }

  function isAllowlistedElement(el) {
    if (!el || !el.closest) return false;
    for (var i = 0; i < ALLOWLISTED_SELECTORS.length; i++) {
      if (el.closest(ALLOWLISTED_SELECTORS[i])) return true;
    }
    return false;
  }

  function shortDerivedNeedlesForReplacedName(replacedName) {
    // 3-char abbr + multi-word initials — whole-token, case-sensitive match only.
    var raw = String(replacedName || '').trim();
    var out = {};
    if (!raw) return out;
    var alnum = raw.replace(/[^A-Za-z0-9]/g, '');
    if (alnum.length >= 2) {
      var abbr = alnum.slice(0, 3).toUpperCase();
      if (!ALLOWLISTED_DERIVED_NEEDLES[abbr]) out[abbr] = true;
    }
    var words = raw.split(/[\s\-_]+/).filter(Boolean);
    if (words.length >= 2) {
      var initials = words.map(function (w) { return w.charAt(0); }).join('').toUpperCase();
      if (initials && !ALLOWLISTED_DERIVED_NEEDLES[initials]) out[initials] = true;
    }
    return out;
  }

  function leakNeedlesForReplacedName(replacedName) {
    var raw = String(replacedName || '').trim();
    if (!raw) return [];
    var needles = [raw];
    var short = shortDerivedNeedlesForReplacedName(raw);
    Object.keys(short).forEach(function (n) { needles.push(n); });
    var slug = raw.replace(/[^A-Za-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    if (slug) {
      needles.push(slug, slug.toUpperCase(), slug.toLowerCase());
    }
    var out = [];
    var seen = {};
    for (var i = 0; i < needles.length; i++) {
      var n = needles[i];
      if (!n || ALLOWLISTED_DERIVED_NEEDLES[n]) continue;
      if (seen[n]) continue;
      seen[n] = true;
      out.push(n);
    }
    return out;
  }

  function textContainsNeedle(text, needle, isShort) {
    if (!text || !needle) return false;
    if (isShort) {
      // Whole-token, case-sensitive: "CON" badge is a leak; "Conference" is not.
      var parts = String(text).split(TOKEN_SPLIT_RE);
      for (var i = 0; i < parts.length; i++) {
        if (parts[i] === needle) return true;
      }
      return false;
    }
    return String(text).toLowerCase().indexOf(String(needle).toLowerCase()) !== -1;
  }

  function textContainsAnyNeedle(text, needles, shortNeedles) {
    if (!text) return false;
    shortNeedles = shortNeedles || {};
    for (var i = 0; i < needles.length; i++) {
      var n = needles[i];
      if (!n) continue;
      if (textContainsNeedle(text, n, !!shortNeedles[n])) return true;
    }
    return false;
  }

  function normalizeHexColor(value) {
    if (value == null) return '';
    var raw = String(value).trim();
    if (!raw || raw === 'transparent' || raw === 'rgba(0, 0, 0, 0)') return '';
    var rgb = raw.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
    if (rgb) {
      return (
        '#' +
        [rgb[1], rgb[2], rgb[3]]
          .map(function (n) {
            var h = Number(n).toString(16);
            return h.length === 1 ? '0' + h : h;
          })
          .join('')
      );
    }
    if (raw.charAt(0) === '#') raw = raw.slice(1);
    if (raw.length === 3 && /^[0-9a-fA-F]{3}$/.test(raw)) {
      raw = raw[0] + raw[0] + raw[1] + raw[1] + raw[2] + raw[2];
    }
    if (raw.length !== 6 || !/^[0-9a-fA-F]{6}$/.test(raw)) return '';
    return '#' + raw.toLowerCase();
  }

  // Pure white/black are universal UI chrome. A replaced core palette that is
  // exactly #ffffff or #000000 is indistinguishable from normal text/fills —
  // exclude those two needles only (not a general achromatic rule).
  var UNIVERSAL_CHROME_COLORS = {
    '#ffffff': true,
    '#000000': true,
  };

  function coreOnlyPaletteFromVisual(visual) {
    if (!visual) return {};
    var overlaySet = {};
    [visual.primary_color, visual.secondary_color].forEach(function (c) {
      var n = normalizeHexColor(c);
      if (n) overlaySet[n] = true;
    });
    var out = {};
    [visual.replaced_primary_color, visual.replaced_secondary_color].forEach(function (c) {
      var n = normalizeHexColor(c);
      if (!n || overlaySet[n] || UNIVERSAL_CHROME_COLORS[n]) return;
      out[n] = true;
    });
    return out;
  }

  function parseCssPx(value) {
    var n = parseFloat(value);
    return isFinite(n) ? n : 0;
  }

  function isVisibleBorderEdge(style, side) {
    // getComputedStyle resolves border*Color even when nothing paints.
    // Only score a side that actually draws (width > 0, style not none/hidden).
    var width = parseCssPx(style['border' + side + 'Width']);
    if (width <= 0) return false;
    var bStyle = String(style['border' + side + 'Style'] || '').toLowerCase();
    return bStyle !== 'none' && bStyle !== 'hidden' && bStyle !== '';
  }

  function isVisibleOutline(style) {
    var width = parseCssPx(style.outlineWidth);
    if (width <= 0) return false;
    var oStyle = String(style.outlineStyle || '').toLowerCase();
    return oStyle !== 'none' && oStyle !== 'hidden' && oStyle !== '';
  }

  function scanDomColors(root) {
    var visual = null;
    try {
      if (typeof global.getActiveTeamBuilderVisual === 'function') {
        visual = global.getActiveTeamBuilderVisual();
      }
    } catch (e) { /* ignore */ }
    var coreOnly = coreOnlyPaletteFromVisual(visual);
    var keys = Object.keys(coreOnly);
    if (!keys.length) return [];
    var doc = root || (global.document && global.document.body);
    if (!doc || !global.getComputedStyle) return [];
    var hits = [];
    var els = doc.querySelectorAll('*');
    var maxScan = Math.min(els.length, 2500);
    // color / backgroundColor always score. Border/outline colors only when
    // the corresponding edge is actually drawn — otherwise computed values
    // are phantoms (currentcolor / UA defaults on borderless chrome).
    var borderSides = [
      { prop: 'borderTopColor', side: 'Top' },
      { prop: 'borderRightColor', side: 'Right' },
      { prop: 'borderBottomColor', side: 'Bottom' },
      { prop: 'borderLeftColor', side: 'Left' },
    ];
    for (var i = 0; i < maxScan; i++) {
      var el = els[i];
      if (isAllowlistedElement(el)) continue;
      var style;
      try {
        style = global.getComputedStyle(el);
      } catch (e2) {
        continue;
      }
      if (!style) continue;
      var matched = [];
      var fillProps = ['color', 'backgroundColor'];
      for (var f = 0; f < fillProps.length; f++) {
        var fillNorm = normalizeHexColor(style[fillProps[f]]);
        if (fillNorm && coreOnly[fillNorm]) matched.push(fillProps[f] + '=' + fillNorm);
      }
      for (var b = 0; b < borderSides.length; b++) {
        if (!isVisibleBorderEdge(style, borderSides[b].side)) continue;
        var bNorm = normalizeHexColor(style[borderSides[b].prop]);
        if (bNorm && coreOnly[bNorm]) matched.push(borderSides[b].prop + '=' + bNorm);
      }
      if (isVisibleOutline(style)) {
        var oNorm = normalizeHexColor(style.outlineColor);
        if (oNorm && coreOnly[oNorm]) matched.push('outlineColor=' + oNorm);
      }
      if (!matched.length) continue;
      hits.push({
        text: '[color] ' + matched.join(' '),
        element: el,
        tag: el.tagName,
        id: el.id || null,
        className: el.className ? String(el.className).slice(0, 80) : null,
        kind: 'color',
      });
      if (hits.length >= 40) break;
    }
    return hits;
  }

  function scanDom(replacedName, root) {
    var needle = String(replacedName || '').trim();
    var needles = needle ? leakNeedlesForReplacedName(needle) : [];
    var shortNeedles = needle ? shortDerivedNeedlesForReplacedName(needle) : {};
    var doc = root || (global.document && global.document.body);
    if (!doc) return [];
    var hits = [];
    if (needles.length) {
      var walker = global.document.createTreeWalker(doc, NodeFilter.SHOW_TEXT, null);
      var node;
      while ((node = walker.nextNode())) {
        var text = node.nodeValue || '';
        if (!text || !textContainsAnyNeedle(text, needles, shortNeedles)) continue;
        if (ORIENTATION_RE.test(text)) continue;
        var el = node.parentElement;
        if (isAllowlistedElement(el)) continue;
        hits.push({
          text: text.trim().slice(0, 160),
          element: el,
          tag: el ? el.tagName : null,
          id: el && el.id ? el.id : null,
          className: el && el.className ? String(el.className).slice(0, 80) : null,
          matchedNeedles: needles.filter(function (n) {
            return textContainsNeedle(text, n, !!shortNeedles[n]);
          }),
          kind: 'name',
        });
      }
    }
    hits = hits.concat(scanDomColors(root));
    return hits;
  }

  function clearBanner() {
    var existing = global.document && global.document.getElementById(BANNER_ID);
    if (existing && existing.parentNode) existing.parentNode.removeChild(existing);
  }

  function paintBanner(hits, replacedName) {
    if (!global.document || !global.document.body) return;
    clearBanner();
    if (!hits.length) return;

    var banner = global.document.createElement('div');
    banner.id = BANNER_ID;
    banner.setAttribute('role', 'alert');
    banner.style.cssText = [
      'position:fixed',
      'top:0',
      'left:0',
      'right:0',
      'z-index:2147483647',
      'background:#8b1a1a',
      'color:#ffffff',
      'font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace',
      'padding:10px 14px',
      'box-shadow:0 4px 16px rgba(0,0,0,0.45)',
      'max-height:40vh',
      'overflow:auto',
    ].join(';');

    var title = global.document.createElement('div');
    title.style.cssText = 'font-weight:700;margin-bottom:6px;';
    title.textContent =
      '[TB-LEAK] replaced_name=' + JSON.stringify(replacedName) +
      ' in ' + hits.length + ' DOM node(s) — dismiss to continue';
    banner.appendChild(title);

    var list = global.document.createElement('ul');
    list.style.cssText = 'margin:0 0 8px 18px;padding:0;';
    var max = Math.min(hits.length, 12);
    for (var i = 0; i < max; i++) {
      var h = hits[i];
      var li = global.document.createElement('li');
      li.textContent =
        '<' + (h.tag || '?') +
        (h.id ? '#' + h.id : '') +
        (h.className ? '.' + String(h.className).split(/\s+/).slice(0, 2).join('.') : '') +
        '> ' + h.text;
      list.appendChild(li);
    }
    if (hits.length > max) {
      var more = global.document.createElement('li');
      more.textContent = '… +' + (hits.length - max) + ' more (see console)';
      list.appendChild(more);
    }
    banner.appendChild(list);

    var dismiss = global.document.createElement('button');
    dismiss.type = 'button';
    dismiss.textContent = 'Dismiss';
    dismiss.style.cssText =
      'background:#ffffff;color:#8b1a1a;border:0;padding:4px 10px;font:inherit;cursor:pointer;';
    dismiss.onclick = function () { clearBanner(); };
    banner.appendChild(dismiss);

    global.document.body.appendChild(banner);

    // Highlight first few offenders briefly.
    for (var j = 0; j < Math.min(hits.length, 5); j++) {
      var el = hits[j].element;
      if (!el || !el.style) continue;
      el.style.outline = '3px solid #ff4444';
      el.style.outlineOffset = '2px';
    }
  }

  function hitDedupeKey(hit, replacedName) {
    // Stable node identity: id when present, else tag + leading classes.
    // Transient mounts (moment cards) share class signatures, so the same
    // color/name needle on remounted UI reports once per session.
    var tag = String((hit && hit.tag) || '');
    var id = String((hit && hit.id) || '');
    var cls = String((hit && hit.className) || '')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 3)
      .join('.');
    var nodeKey = id ? tag + '#' + id : tag + (cls ? '.' + cls : '');
    var needlePart = '';
    if (hit && hit.kind === 'color') {
      needlePart = String(hit.text || '').slice(0, 80);
    } else if (hit && hit.matchedNeedles && hit.matchedNeedles.length) {
      needlePart = hit.matchedNeedles.slice().sort().join('|');
    } else {
      needlePart = String(replacedName || '') + '|' + String((hit && hit.text) || '').slice(0, 40);
    }
    return nodeKey + '::' + needlePart;
  }

  function filterNewHits(hits, replacedName) {
    var fresh = [];
    for (var i = 0; i < hits.length; i++) {
      var key = hitDedupeKey(hits[i], replacedName);
      if (reportedLeakKeys[key]) continue;
      reportedLeakKeys[key] = true;
      fresh.push(hits[i]);
    }
    return fresh;
  }

  function report(hits, replacedName) {
    var fresh = filterNewHits(hits, replacedName);
    if (!fresh.length) {
      // Keep an existing banner if still relevant; do not re-paint noise.
      return;
    }
    for (var i = 0; i < fresh.length; i++) {
      var h = fresh[i];
      console.error(
        '[TB-LEAK] DOM contains replaced_name=' + JSON.stringify(replacedName) +
          ' in <' + h.tag + ' id=' + h.id + ' class=' + h.className + '>: ' + h.text,
        h.element
      );
    }
    paintBanner(fresh, replacedName);
  }

  /**
   * Scan after paint. Returns hit list (also logs + banner).
   * @param {{replacedName?: string, root?: Element, throwOnHit?: boolean}} [options]
   */
  function runTeamBuilderLeakScan(options) {
    options = options || {};
    if (!envEnabled()) return [];
    var replaced = resolveReplacedName(options);
    var visual = null;
    try {
      if (typeof global.getActiveTeamBuilderVisual === 'function') {
        visual = global.getActiveTeamBuilderVisual();
      }
    } catch (e) { /* ignore */ }
    var hasColorProbe = !!(visual && (visual.replaced_primary_color || visual.replaced_secondary_color));
    if (!replaced && !hasColorProbe) return [];
    var hits = scanDom(replaced, options.root);
    report(hits, replaced || '(color-only)');
    if (hits.length && options.throwOnHit) {
      throw new Error(
        '[TB-LEAK] DOM leak of ' + JSON.stringify(replaced || 'colors') + ' (' + hits.length + ' hit(s))'
      );
    }
    return hits;
  }

  function scheduleScan(options) {
    if (!envEnabled()) return;
    var run = function () { runTeamBuilderLeakScan(options); };
    if (global.requestAnimationFrame) {
      global.requestAnimationFrame(function () {
        setTimeout(run, 0);
      });
    } else {
      setTimeout(run, 50);
    }
  }

  function autoArm() {
    if (!envEnabled()) return;
    try {
      var params = new URLSearchParams(global.location.search || '');
      if (!params.get('franchise_id') && !(global.location.pathname || '').match(/franchise|mode-select|court|set-lineup|standings|rankings|box-score/)) {
        return;
      }
    } catch (e) { /* ignore */ }
    if (global.document && global.document.readyState === 'complete') {
      scheduleScan();
    } else if (global.addEventListener) {
      global.addEventListener('load', function () { scheduleScan(); });
    }
    // Re-scan after SPA-ish DOM updates during play.
    if (global.setInterval) {
      global.setInterval(function () {
        if (!envEnabled()) return;
        runTeamBuilderLeakScan();
      }, 8000);
    }
  }

  global.TeamBuilderLeakDetector = {
    run: runTeamBuilderLeakScan,
    schedule: scheduleScan,
    scanDom: scanDom,
    scanDomColors: scanDomColors,
    clearBanner: clearBanner,
    resetDedupe: function () { reportedLeakKeys = Object.create(null); },
    leakNeedlesForReplacedName: leakNeedlesForReplacedName,
    shortDerivedNeedlesForReplacedName: shortDerivedNeedlesForReplacedName,
    normalizeHexColor: normalizeHexColor,
    isVisibleBorderEdge: isVisibleBorderEdge,
    isVisibleOutline: isVisibleOutline,
    ALLOWLISTED_SELECTORS: ALLOWLISTED_SELECTORS,
    ALLOWLISTED_DERIVED_NEEDLES: ALLOWLISTED_DERIVED_NEEDLES,
  };

  autoArm();
})(typeof window !== 'undefined' ? window : this);
