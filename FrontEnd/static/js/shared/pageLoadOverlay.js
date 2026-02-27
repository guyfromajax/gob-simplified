/**
 * Page Load Overlay – shared full-page loader for court, FCC, TCC, set-lineup
 *
 * Prevents stale data from being visible on initial load. Show overlay as soon as
 * the destination page runs; hide when the page is "ready" (data loaded, UI rendered).
 *
 * Usage:
 *   PageLoadOverlay.show();   // at start of page init
 *   PageLoadOverlay.hide();   // when data is loaded and UI is ready
 *
 * Load early (e.g. in <head>) so overlay can be shown before body content paints.
 */
(function (global) {
  'use strict';

  var OVERLAY_ID = 'page-load-overlay';
  var LOADER_IMG_PATH = '/images/loader1.gif';
  var Z_INDEX = 999999;

  function getOrCreateOverlay() {
    var existing = document.getElementById(OVERLAY_ID);
    if (existing) return existing;

    var overlay = document.createElement('div');
    overlay.id = OVERLAY_ID;
    overlay.setAttribute('aria-hidden', 'false');
    overlay.setAttribute('aria-busy', 'true');
    overlay.setAttribute('role', 'status');
    overlay.setAttribute('aria-live', 'polite');

    // Full viewport, opaque dark so user cannot see stale content behind it
    overlay.style.cssText =
      'position:fixed;inset:0;z-index:' + Z_INDEX + ';' +
      'background:rgba(0,0,0,0.92);' +
      'display:flex;align-items:center;justify-content:center;' +
      'margin:0;padding:0;';

    var img = document.createElement('img');
    img.src = LOADER_IMG_PATH;
    img.alt = 'Loading…';
    img.style.cssText = 'width:240px;height:auto;max-width:90vw;';
    overlay.appendChild(img);

    document.body.appendChild(overlay);
    return overlay;
  }

  function show() {
    if (typeof document === 'undefined' || !document.body) {
      if (typeof document !== 'undefined' && document.addEventListener) {
        document.addEventListener('DOMContentLoaded', function onReady() {
          document.removeEventListener('DOMContentLoaded', onReady);
          getOrCreateOverlay().style.display = 'flex';
        });
      }
      return;
    }
    getOrCreateOverlay().style.display = 'flex';
  }

  function hide() {
    if (typeof document === 'undefined') return;
    var el = document.getElementById(OVERLAY_ID);
    if (el) {
      el.setAttribute('aria-hidden', 'true');
      el.setAttribute('aria-busy', 'false');
      el.style.display = 'none';
    }
  }

  var api = { show: show, hide: hide };
  global.PageLoadOverlay = api;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})(typeof window !== 'undefined' ? window : this);
