/**
 * Pipeline B — pure DOM region capture (staging only).
 */
(function () {
  'use strict';

  var utils = function () {
    return window.GOBCaptureUtils;
  };

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

  function prepareImagesForCapture(root) {
    var restores = [];
    var reloads = [];
    var imgs = root.querySelectorAll('img');

    imgs.forEach(function (img) {
      if (!img.getAttribute('src') && !img.src) return;
      var prevCross = img.crossOrigin;
      restores.push({ el: img, crossOrigin: prevCross });
      if (prevCross === 'anonymous') return;

      img.crossOrigin = 'anonymous';
      var src = img.currentSrc || img.src;
      if (!src) return;

      reloads.push(new Promise(function (resolve) {
        function done() {
          img.removeEventListener('load', done);
          img.removeEventListener('error', done);
          resolve();
        }
        img.addEventListener('load', done);
        img.addEventListener('error', done);
        if (img.complete) {
          img.src = '';
          img.src = src;
        }
      }));
    });

    return Promise.all(reloads).then(function () {
      return function restoreImages() {
        restores.forEach(function (entry) {
          entry.el.crossOrigin = entry.crossOrigin;
        });
      };
    });
  }

  function captureDomRegion(selector, options) {
    options = options || {};
    var scale = options.scale == null ? 2 : options.scale;
    var tag = options.tag || 'screen';
    var detail = options.detail || resolveCaptureDetail();
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
      return prepareImagesForCapture(el).then(function (restoreImages) {
        return html2canvas(el, {
          scale: scale,
          backgroundColor: options.backgroundColor || '#08080f',
          logging: false,
          useCORS: true,
          allowTaint: false,
          ignoreElements: function (node) {
            if (shouldIgnoreCaptureNode(node)) return true;
            if (isHiddenCommandCenterTab(node)) return true;
            return false;
          },
        }).then(function (canvas) {
          restoreImages();
          u.restoreRecIndicator();
          return u.saveCapture(
            canvas.toDataURL('image/png'),
            u.buildFilename(tag, detail)
          );
        }).catch(function (err) {
          restoreImages();
          u.restoreRecIndicator();
          console.warn('[GOBCapture] DOM capture failed:', err);
          return false;
        });
      });
    });
  }

  function captureCurrentScreen(options) {
    options = options || {};
    if (!options.tag) options.tag = 'screen';
    if (!options.detail) options.detail = resolveCaptureDetail();
    return captureDomRegion(null, options);
  }

  window.GOBCaptureDom = {
    resolveCaptureRoot: resolveCaptureRoot,
    resolveCaptureDetail: resolveCaptureDetail,
    captureDomRegion: captureDomRegion,
    captureCurrentScreen: captureCurrentScreen,
  };
})();
