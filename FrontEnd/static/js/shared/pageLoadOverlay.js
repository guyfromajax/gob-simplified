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

  function ensureOverlayStructure(overlay) {
    if (!overlay) return overlay;

    overlay.style.cssText =
      'position:fixed;inset:0;z-index:' + Z_INDEX + ';' +
      'background:rgba(0,0,0,0.92);' +
      'display:flex;align-items:center;justify-content:center;' +
      'margin:0;padding:0;';

    var content = overlay.querySelector('.page-load-overlay-content');
    if (!content) {
      content = document.createElement('div');
      content.className = 'page-load-overlay-content';
      content.style.cssText = 'display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;text-align:center;';

      while (overlay.firstChild) {
        content.appendChild(overlay.firstChild);
      }
      overlay.appendChild(content);
    }

    var img = content.querySelector('img');
    if (!img) {
      img = document.createElement('img');
      img.alt = 'Loading…';
      content.appendChild(img);
    }
    img.src = LOADER_IMG_PATH;
    img.style.cssText = 'width:240px;height:auto;max-width:90vw;';

    var message = content.querySelector('.page-load-overlay-message');
    if (!message) {
      message = document.createElement('div');
      message.className = 'page-load-overlay-message';
      message.style.cssText = 'color:#ffffff;font-weight:700;font-size:24px;line-height:1.2;';
      content.appendChild(message);
    }

    return overlay;
  }

  function getOrCreateOverlay() {
    var existing = document.getElementById(OVERLAY_ID);
    if (existing) return ensureOverlayStructure(existing);

    var overlay = document.createElement('div');
    overlay.id = OVERLAY_ID;
    overlay.setAttribute('aria-hidden', 'false');
    overlay.setAttribute('aria-busy', 'true');
    overlay.setAttribute('role', 'status');
    overlay.setAttribute('aria-live', 'polite');

    ensureOverlayStructure(overlay);
    document.body.appendChild(overlay);
    return overlay;
  }

  function show(messageText) {
    if (typeof document === 'undefined' || !document.body) {
      if (typeof document !== 'undefined' && document.addEventListener) {
        document.addEventListener('DOMContentLoaded', function onReady() {
          document.removeEventListener('DOMContentLoaded', onReady);
          var readyOverlay = getOrCreateOverlay();
          var readyMessage = readyOverlay.querySelector('.page-load-overlay-message');
          if (readyMessage) readyMessage.textContent = messageText || '';
          readyOverlay.style.display = 'flex';
        });
      }
      return;
    }
    var overlay = getOrCreateOverlay();
    var message = overlay.querySelector('.page-load-overlay-message');
    if (message) message.textContent = messageText || '';
    overlay.style.display = 'flex';
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
