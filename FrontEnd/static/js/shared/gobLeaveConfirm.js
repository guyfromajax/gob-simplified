/**
 * In-app confirm for leaving a view with unsaved edits. Uses the existing
 * gob-modal markup (resource-pages.css). The browser's own beforeunload prompt
 * is only for reloads and closes.
 *
 *   GOBLeaveConfirm.open({
 *     title, copy, saveLabel,
 *     onSave: () => Promise<boolean>,   // true when the save landed
 *     onDiscard: () => void,
 *     proceed: () => void,              // runs after a save or a discard
 *   });
 *
 * Keep Editing, Escape, and the backdrop close it without leaving.
 */
(function (global) {
  'use strict';

  var open = null;

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function openConfirm(opts) {
    opts = opts || {};
    if (open) open.close();
    var returnFocus = document.activeElement;
    var overlay = document.createElement('div');
    overlay.className = 'gob-modal-overlay gob-leave-confirm is-visible';
    overlay.innerHTML = ''
      + '<div class="gob-modal-backdrop"></div>'
      + '<div class="gob-modal-box" role="alertdialog" aria-modal="true" aria-labelledby="gob-leave-title" aria-describedby="gob-leave-copy">'
      + '<div class="gob-modal-body">'
      + '<h3 id="gob-leave-title" class="gob-modal-title">' + esc(opts.title || 'Unsaved changes') + '</h3>'
      + '<p id="gob-leave-copy" class="gob-modal-subtitle">' + esc(opts.copy || '') + '</p>'
      + '</div>'
      + '<div class="gob-modal-actions">'
      + '<button type="button" class="gob-modal-btn-dismiss" data-leave="stay" data-sfx="SFX_SELECT">Keep Editing</button>'
      + '<button type="button" class="gob-modal-btn-secondary" data-leave="discard" data-sfx="SFX_SELECT">Discard</button>'
      + '<button type="button" class="gob-modal-btn-primary" data-leave="save" data-sfx="SFX_COMMIT">' + esc(opts.saveLabel || 'Save') + '</button>'
      + '</div></div>';

    var busy = false;
    function close() {
      document.removeEventListener('keydown', onKey, true);
      overlay.remove();
      if (open === api) open = null;
      if (returnFocus && typeof returnFocus.focus === 'function' && returnFocus.isConnected) {
        try { returnFocus.focus({ preventScroll: true }); } catch (err) {}
      }
    }
    function onKey(event) {
      if (event.key === 'Escape' && !busy) {
        event.preventDefault();
        close();
      }
    }
    overlay.addEventListener('click', function (event) {
      if (busy) return;
      if (event.target.classList.contains('gob-modal-backdrop')) {
        close();
        return;
      }
      var btn = event.target.closest('[data-leave]');
      if (!btn) return;
      var action = btn.getAttribute('data-leave');
      if (action === 'stay') {
        close();
        return;
      }
      if (action === 'discard') {
        close();
        if (typeof opts.onDiscard === 'function') opts.onDiscard();
        if (typeof opts.proceed === 'function') opts.proceed();
        return;
      }
      if (action === 'save') {
        busy = true;
        btn.disabled = true;
        Promise.resolve(typeof opts.onSave === 'function' ? opts.onSave() : false).then(function (ok) {
          busy = false;
          btn.disabled = false;
          close();
          if (ok && typeof opts.proceed === 'function') opts.proceed();
        }, function () {
          busy = false;
          btn.disabled = false;
          close();
        });
      }
    });
    document.addEventListener('keydown', onKey, true);
    document.body.appendChild(overlay);
    var stay = overlay.querySelector('[data-leave="stay"]');
    if (stay) stay.focus();
    var api = { close: close, el: overlay };
    open = api;
    return api;
  }

  global.GOBLeaveConfirm = {
    open: openConfirm,
    isOpen: function () { return !!open; }
  };
})(typeof window !== 'undefined' ? window : this);
