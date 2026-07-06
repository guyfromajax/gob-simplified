/**
 * Pipeline B — pure DOM region capture (staging only).
 */
(function () {
  'use strict';

  var lastCaptureError = '';

  var CAPTURE_SAFE_CSS = [
    '.team-tooltip-host::before, .team-tooltip-host::after {',
    '  display: none !important;',
    '  content: none !important;',
    '  visibility: hidden !important;',
    '  opacity: 0 !important;',
    '}',
    '#franchise-container *, #tournament-container * {',
    '  filter: none !important;',
    '  backdrop-filter: none !important;',
    '  -webkit-backdrop-filter: none !important;',
    '}',
  ].join('\n');

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

  function getActiveCommandCenterTab() {
    return document.querySelector(
      '#franchise-container .tab-content.active, #tournament-container .tab-content.active'
    );
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
    var activeTab = getActiveCommandCenterTab();
    if (activeTab && activeTab.id) {
      return activeTab.id.replace(/-tab$/, '');
    }
    return 'manual';
  }

  function injectCaptureSafeStyles(clonedDoc) {
    if (!clonedDoc || !clonedDoc.head) return;
    var style = clonedDoc.createElement('style');
    style.setAttribute('data-gob-capture-safe', 'true');
    style.textContent = CAPTURE_SAFE_CSS;
    clonedDoc.head.appendChild(style);
  }

  function unwrapTooltipHosts(root) {
    root.querySelectorAll('.team-tooltip-host').forEach(function (host) {
      var img = host.querySelector('img');
      var parent = host.parentNode;
      if (!parent) return;
      if (img) {
        parent.replaceChild(img.cloneNode(true), host);
      } else {
        parent.removeChild(host);
      }
    });
  }

  function sanitizeClone(clonedDoc, root, options) {
    options = options || {};
    injectCaptureSafeStyles(clonedDoc);

    root.querySelectorAll('.tab-content').forEach(function (tab) {
      if (!tab.classList.contains('active')) {
        tab.remove();
      }
    });

    unwrapTooltipHosts(root);

    root.querySelectorAll('img').forEach(function (img) {
      if (options.removeAllImages) {
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
      imageTimeout: 15000,
      ignoreElements: buildIgnoreElements(!!config.stripExternalImages),
      onclone: config.sanitizeClone
        ? function (clonedDoc, clone) {
          sanitizeClone(clonedDoc, clone, {
            removeAllImages: !!config.removeAllImages,
          });
        }
        : undefined,
    });
  }

  function attemptCapture(el, config) {
    var u = utils();
    if (!u) {
      return Promise.reject(new Error('GOBCaptureUtils unavailable'));
    }
    return runHtml2Canvas(el, config).then(function (canvas) {
      if (!canvas || !canvas.width || !canvas.height) {
        throw new Error('empty canvas (' + (canvas ? canvas.width + 'x' + canvas.height : 'null') + ')');
      }
      console.info('[GOBCapture] canvas', config.label, canvas.width + 'x' + canvas.height);
      var dataUrl = canvas.toDataURL('image/png');
      if (!dataUrl || dataUrl === 'data:,') {
        throw new Error('empty image data');
      }
      var saved = u.saveCapture(dataUrl, u.buildFilename(config.tag, config.detail));
      if (!saved) {
        throw new Error('download failed');
      }
      return true;
    });
  }

  function captureWithFallbacks(el, options) {
    var backgroundColor = options.backgroundColor || '#08080f';
    var activeTab = getActiveCommandCenterTab();
    var base = {
      backgroundColor: backgroundColor,
      tag: options.tag,
      detail: options.detail,
    };

    var attempts = [
      Object.assign({}, base, {
        el: el,
        label: 'shell-1x',
        scale: 1,
        useCORS: false,
        allowTaint: false,
        sanitizeClone: true,
        stripExternalImages: false,
      }),
      Object.assign({}, base, {
        el: el,
        label: 'shell-2x',
        scale: 2,
        useCORS: false,
        allowTaint: false,
        sanitizeClone: true,
        stripExternalImages: false,
      }),
    ];

    if (activeTab && el.contains(activeTab)) {
      attempts.push(Object.assign({}, base, {
        el: activeTab,
        label: 'active-tab-1x',
        scale: 1,
        useCORS: false,
        allowTaint: false,
        sanitizeClone: true,
        stripExternalImages: false,
      }));
    }

    attempts.push(
      Object.assign({}, base, {
        el: el,
        label: 'no-images-1x',
        scale: 1,
        useCORS: false,
        allowTaint: true,
        sanitizeClone: true,
        stripExternalImages: true,
        removeAllImages: true,
      })
    );

    function tryNext(index) {
      if (index >= attempts.length) {
        return Promise.resolve(false);
      }
      var attempt = attempts[index];
      return attemptCapture(attempt.el, attempt).then(function (ok) {
        if (ok) return true;
        lastCaptureError = '[' + attempt.label + '] returned false';
        console.warn('[GOBCapture] DOM capture attempt returned false:', lastCaptureError);
        return tryNext(index + 1);
      }).catch(function (err) {
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
      console.info('[GOBCapture] capturing', el.id || el.className || el.tagName, resolveCaptureDetail());
      return captureWithFallbacks(el, {
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
