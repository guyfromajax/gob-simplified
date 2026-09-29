/**
 * One save confirmation for the franchise shell: a short line that fades after
 * SHOW_MS. Fixed-position, so it never moves the page. Styles: css/gob-toast.css.
 *
 *   GOBToast.show('Playbooks saved');
 */
(function (global) {
  'use strict';

  var SHOW_MS = 1500;
  var host = null;
  var timer = null;

  function ensureHost() {
    if (host && host.isConnected) return host;
    host = document.createElement('div');
    host.className = 'gob-save-toast';
    host.setAttribute('role', 'status');
    host.setAttribute('aria-live', 'polite');
    host.setAttribute('aria-atomic', 'true');
    document.body.appendChild(host);
    return host;
  }

  function hide() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    if (host) host.classList.remove('is-on');
  }

  function show(message) {
    var el = ensureHost();
    hide();
    el.textContent = String(message || '');
    // Force a style flush so a repeat save replays the fade-in.
    void el.offsetWidth;
    el.classList.add('is-on');
    timer = setTimeout(hide, SHOW_MS);
  }

  function ready() {
    ensureHost();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready);
  else ready();

  global.GOBToast = { show: show, hide: hide, SHOW_MS: SHOW_MS };
})(typeof window !== 'undefined' ? window : this);
