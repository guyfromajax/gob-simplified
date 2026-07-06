/**
 * Pipeline B — pure DOM region capture (staging only).
 */
(function () {
  'use strict';

  var lastCaptureError = '';

  function utils() {
    return window.GOBCaptureUtils;
  }

  function isCrossOriginUrl(url) {
    if (!url) return false;
    try {
      return new URL(url, window.location.href).origin !== window.location.origin;
    } catch (e) {
      return false;
    }
  }

  function shouldIgnoreCaptureNode(node) {
    if (!node || !node.id) return false;
    return node.id === 'page-load-overlay'
      || node.id === 'gob-capture-rec'
      || node.id === 'cc-loading-overlay'
      || node.id === 'feedback-modal-backdrop';
  }

  function isHiddenCommandCenterTab(node) {
    return !!(node.classList
      && node.classList.contains('tab-content')
      && !node.classList.contains('active'));
  }

  function shouldIgnoreCaptureImage(node) {
    if (!node || node.tagName !== 'IMG') return false;
    var src = node.currentSrc || node.getAttribute('src') || node.src || '';
    return isCrossOriginUrl(src);
  }

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
      '#franchise-container',
      '#tournament-container',
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

  function resolveCaptureDetail() {
    var activeTab = document.querySelector(
      '#franchise-container .tab-content.active, #tournament-container .tab-content.active'
    );
    if (activeTab && activeTab.id) {
      return activeTab.id.replace(/-tab$/, '');
    }
    return 'manual';
  }

  function sanitizeClone(doc, removeAllImages) {
    doc.querySelectorAll('.tab-content').forEach(function (tab) {
      if (!tab.classList.contains('active')) {
        tab.remove();
      }
    });
    doc.querySelectorAll('img').forEach(function (img) {
      if (removeAllImages) {
        img.remove();
        return;
      }
      var src = img.currentSrc || img.getAttribute('src') || img.src || '';
      if (!src || isCrossOriginUrl(src)) {
        img.remove();
      }
    });
  }

  function buildIgnoreElements(strictImages) {
    return function (node) {
      if (shouldIgnoreCaptureNode(node)) return true;
      if (isHiddenCommandCenterTab(node)) return true;
      if (strictImages && shouldIgnoreCaptureImage(node)) return true;
      return false;
    };
  }

  function runHtml2Canvas(el, config) {
    return html2canvas(el, {
      scale: config.scale,
      backgroundColor: config.backgroundColor,
      logging: false,
      useCORS: !!config.useCORS,
      allowTaint: !!config.allowTaint,
      ignoreElements: buildIgnoreElements(!!config.stripExternalImages),
      onclone: config.sanitizeClone
        ? function (_doc, clone) {
          sanitizeClone(clone, !!config.removeAllImages);
        }
        : undefined,
    });
  }

  function attemptCapture(el, config) {
    return runHtml2Canvas(el, config).then(function (canvas) {
      return utils().saveCapture(
        canvas.toDataURL('image/png'),
        utils().buildFilename(config.tag, config.detail)
      );
    });
  }

  function captureWithFallbacks(el, options) {
    var scale = options.scale == null ? 2 : options.scale;
    var backgroundColor = options.backgroundColor || '#08080f';
    var base = {
      scale: scale,
      backgroundColor: backgroundColor,
      tag: options.tag,
      detail: options.detail,
    };

    var attempts = [
      Object.assign({}, base, {
        label: 'same-origin',
        useCORS: false,
        allowTaint: false,
        sanitizeClone: true,
        stripExternalImages: false,
      }),
      Object.assign({}, base, {
        label: 'cors',
        useCORS: true,
        allowTaint: false,
        sanitizeClone: true,
        stripExternalImages: true,
      }),
      Object.assign({}, base, {
        label: 'no-images',
        useCORS: false,
        allowTaint: true,
        sanitizeClone: true,
        stripExternalImages: true,
        removeAllImages: true,
      }),
    ];

    function tryNext(index) {
      if (index >= attempts.length) {
        return Promise.resolve(false);
      }
      var attempt = attempts[index];
      return attemptCapture(el, attempt).catch(function (err) {
        lastCaptureError = '[' + attempt.label + '] ' + (err && err.message ? err.message : String(err));
        console.warn('[GOBCapture] DOM capture attempt failed:', lastCaptureError);
        return tryNext(index + 1);
      });
    }

    return tryNext(0);
  }

  function captureDomRegion(selector, options) {
    options = options || {};
    var tag = options.tag || 'screen';
    var detail = options.detail || resolveCaptureDetail();
    var u = utils();
    if (!u || typeof html2canvas !== 'function') {
      lastCaptureError = 'html2canvas unavailable';
      return Promise.resolve(false);
    }

    lastCaptureError = '';

    return Promise.resolve().then(function () {
      if (document.fonts && document.fonts.ready) {
        return document.fonts.ready;
      }
    }).then(function () {
      u.hideRecIndicator();
      var el = selector ? document.querySelector(selector) : resolveCaptureRoot();
      if (!el) {
        lastCaptureError = 'capture root not found';
        u.restoreRecIndicator();
        return false;
      }
      return captureWithFallbacks(el, {
        scale: options.scale,
        backgroundColor: options.backgroundColor,
        tag: tag,
        detail: detail,
      }).then(function (ok) {
        u.restoreRecIndicator();
        if (!ok && !lastCaptureError) {
          lastCaptureError = 'all capture attempts failed';
        }
        return ok;
      });
    });
  }

  function captureCurrentScreen(options) {
    options = options || {};
    if (!options.tag) options.tag = 'screen';
    if (!options.detail) options.detail = resolveCaptureDetail();
    return captureDomRegion(null, options);
  }

  function getLastCaptureError() {
    return lastCaptureError;
  }

  window.GOBCaptureDom = {
    resolveCaptureRoot: resolveCaptureRoot,
    resolveCaptureDetail: resolveCaptureDetail,
    captureDomRegion: captureDomRegion,
    captureCurrentScreen: captureCurrentScreen,
    getLastCaptureError: getLastCaptureError,
  };
})();
