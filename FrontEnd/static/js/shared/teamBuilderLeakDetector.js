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
      'color:#fff',
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
      'background:#fff;color:#8b1a1a;border:0;padding:4px 10px;font:inherit;cursor:pointer;';
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

  function report(hits, replacedName) {
    if (!hits.length) {
      clearBanner();
      return;
    }
    for (var i = 0; i < hits.length; i++) {
      var h = hits[i];
      console.error(
        '[TB-LEAK] DOM contains replaced_name=' + JSON.stringify(replacedName) +
          ' in <' + h.tag + ' id=' + h.id + ' class=' + h.className + '>: ' + h.text,
        h.element
      );
    }
    paintBanner(hits, replacedName);
  }

  /**
   * Scan after paint. Returns hit list (also logs + banner).
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
    clearBanner: clearBanner,
    ALLOWLISTED_SELECTORS: ALLOWLISTED_SELECTORS,
  };

  autoArm();
})(typeof window !== 'undefined' ? window : this);
