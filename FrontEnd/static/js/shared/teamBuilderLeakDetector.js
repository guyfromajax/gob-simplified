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
 * Source of replaced_name (first hit wins):
 *   1. options.replacedName
 *   2. getActiveTeamBuilderVisual().replaced_name
 *   3. FranchiseLS.getTeamBuilderVisual().replaced_name
 *   4. data-tb-replaced-name on <body>
 */
(function (global) {
  'use strict';

  var ALLOWLISTED_SELECTORS = ['#tb-orientation'];
  var ORIENTATION_RE = /replacing\s+.+\s+in\s+this\s+franchise/i;

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

  function scanDom(replacedName, root) {
    var needle = String(replacedName || '').trim();
    if (!needle) return [];
    var doc = root || (global.document && global.document.body);
    if (!doc) return [];
    var hits = [];
    var needleLower = needle.toLowerCase();
    var walker = global.document.createTreeWalker(doc, NodeFilter.SHOW_TEXT, null);
    var node;
    while ((node = walker.nextNode())) {
      var text = node.nodeValue || '';
      if (!text || text.toLowerCase().indexOf(needleLower) === -1) continue;
      if (ORIENTATION_RE.test(text)) continue;
      var el = node.parentElement;
      if (isAllowlistedElement(el)) continue;
      hits.push({
        text: text.trim().slice(0, 160),
        element: el,
        tag: el ? el.tagName : null,
        id: el && el.id ? el.id : null,
        className: el && el.className ? String(el.className).slice(0, 80) : null,
      });
    }
    return hits;
  }

  function report(hits, replacedName) {
    if (!hits.length) return;
    for (var i = 0; i < hits.length; i++) {
      var h = hits[i];
      console.error(
        '[TB-LEAK] DOM contains replaced_name=' + JSON.stringify(replacedName) +
          ' in <' + h.tag + ' id=' + h.id + ' class=' + h.className + '>: ' + h.text,
        h.element
      );
    }
  }

  /**
   * Scan after paint. Returns hit list (also logs).
   * @param {{replacedName?: string, root?: Element, throwOnHit?: boolean}} [options]
   */
  function runTeamBuilderLeakScan(options) {
    options = options || {};
    if (!envEnabled()) return [];
    var replaced = resolveReplacedName(options);
    if (!replaced) return [];
    var hits = scanDom(replaced, options.root);
    report(hits, replaced);
    if (hits.length && options.throwOnHit) {
      throw new Error(
        '[TB-LEAK] DOM leak of ' + JSON.stringify(replaced) + ' (' + hits.length + ' hit(s))'
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

  // Auto-run on franchise-scoped pages after load.
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
  }

  global.TeamBuilderLeakDetector = {
    run: runTeamBuilderLeakScan,
    schedule: scheduleScan,
    scanDom: scanDom,
    ALLOWLISTED_SELECTORS: ALLOWLISTED_SELECTORS,
  };

  autoArm();
})(typeof window !== 'undefined' ? window : this);
