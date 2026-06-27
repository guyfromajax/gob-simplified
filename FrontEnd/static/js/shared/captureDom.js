/**
 * Pipeline B — pure DOM region capture (staging only).
 */
(function () {
  'use strict';

  var utils = function () {
    return window.GOBCaptureUtils;
  };

  function resolveCaptureRoot() {
    var custom = document.querySelector('[data-capture-root]');
    if (custom) {
      var selector = custom.getAttribute('data-capture-root');
      if (selector) {
        var targeted = document.querySelector(selector);
        if (targeted) return targeted;
      }
      return custom;
    }

    var candidates = [
      'main',
      '.resource-page-container',
      '.fcc-brand-page-shell',
      '.set-lineup-shell',
      '.mode-select-page',
      'body',
    ];
    for (var i = 0; i < candidates.length; i++) {
      var el = document.querySelector(candidates[i]);
      if (el) return el;
    }
    return document.body;
  }

  function captureDomRegion(selector, options) {
    options = options || {};
    var scale = options.scale == null ? 2 : options.scale;
    var tag = options.tag || 'screen';
    var detail = options.detail || '';
    var u = utils();
    if (!u || typeof html2canvas !== 'function') {
      return Promise.resolve(false);
    }

    return Promise.resolve().then(function () {
      if (document.fonts && document.fonts.ready) {
        return document.fonts.ready;
      }
    }).then(function () {
      u.hideRecIndicator();
      var el = selector ? document.querySelector(selector) : resolveCaptureRoot();
      if (!el) {
        u.restoreRecIndicator();
        return false;
      }
      return html2canvas(el, {
        scale: scale,
        backgroundColor: options.backgroundColor || '#08080f',
        logging: false,
        useCORS: true,
        ignoreElements: function (node) {
          if (!node || !node.id) return false;
          return node.id === 'page-load-overlay' || node.id === 'gob-capture-rec';
        },
      }).then(function (canvas) {
        u.restoreRecIndicator();
        return u.saveCapture(
          canvas.toDataURL('image/png'),
          u.buildFilename(tag, detail)
        );
      }).catch(function (err) {
        u.restoreRecIndicator();
        console.warn('[GOBCapture] DOM capture failed:', err);
        return false;
      });
    });
  }

  function captureCurrentScreen(options) {
    options = options || {};
    if (!options.tag) options.tag = 'screen';
    if (!options.detail) options.detail = 'manual';
    return captureDomRegion(null, options);
  }

  window.GOBCaptureDom = {
    resolveCaptureRoot: resolveCaptureRoot,
    captureDomRegion: captureDomRegion,
    captureCurrentScreen: captureCurrentScreen,
  };
})();
