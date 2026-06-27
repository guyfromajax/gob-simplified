/**
 * Pipeline A — court composite capture (Phaser canvas + DOM overlays).
 */
(function () {
  'use strict';

  var FIXED_OVERLAY_IDS = ['scoreboard', 'playcall-center'];

  function utils() {
    return window.GOBCaptureUtils;
  }

  function isCourtPage() {
    var path = window.location.pathname || '';
    return path.indexOf('court.html') !== -1 || /\/court\/?$/.test(path);
  }

  function anchorFixedOverlaysToGrid(grid) {
    var gridRect = grid.getBoundingClientRect();
    var restores = [];
    var prevGridPosition = grid.style.position;
    var computed = window.getComputedStyle(grid);
    if (computed.position === 'static') {
      grid.style.position = 'relative';
    }

    FIXED_OVERLAY_IDS.forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      var rect = el.getBoundingClientRect();
      restores.push({
        el: el,
        position: el.style.position,
        top: el.style.top,
        left: el.style.left,
        right: el.style.right,
        bottom: el.style.bottom,
        width: el.style.width,
      });
      el.style.position = 'absolute';
      el.style.top = (rect.top - gridRect.top) + 'px';
      el.style.left = (rect.left - gridRect.left) + 'px';
      el.style.right = 'auto';
      el.style.bottom = 'auto';
      el.style.width = rect.width + 'px';
    });

    return function restore() {
      restores.forEach(function (saved) {
        saved.el.style.position = saved.position;
        saved.el.style.top = saved.top;
        saved.el.style.left = saved.left;
        saved.el.style.right = saved.right;
        saved.el.style.bottom = saved.bottom;
        saved.el.style.width = saved.width;
      });
      grid.style.position = prevGridPosition;
    };
  }

  function captureCourtScreen(options) {
    options = options || {};
    var scale = options.scale == null ? 2 : options.scale;
    var u = utils();
    if (!u || typeof html2canvas !== 'function') {
      return Promise.resolve(false);
    }
    if (!isCourtPage()) {
      return Promise.resolve(false);
    }

    return Promise.resolve().then(function () {
      if (document.fonts && document.fonts.ready) {
        return document.fonts.ready;
      }
    }).then(function () {
      u.hideRecIndicator();
      var grid = document.getElementById('app-grid');
      var phaserCanvas = document.querySelector('#phaser-container canvas');
      if (!grid || !phaserCanvas) {
        u.restoreRecIndicator();
        return false;
      }

      var restoreFixed = anchorFixedOverlaysToGrid(grid);
      var rect = grid.getBoundingClientRect();
      var out = document.createElement('canvas');
      out.width = Math.round(rect.width * scale);
      out.height = Math.round(rect.height * scale);
      var ctx = out.getContext('2d');
      if (!ctx) {
        restoreFixed();
        u.restoreRecIndicator();
        return false;
      }

      var canvasRect = phaserCanvas.getBoundingClientRect();
      ctx.drawImage(
        phaserCanvas,
        (canvasRect.left - rect.left) * scale,
        (canvasRect.top - rect.top) * scale,
        canvasRect.width * scale,
        canvasRect.height * scale
      );

      phaserCanvas.style.visibility = 'hidden';
      return html2canvas(grid, {
        backgroundColor: null,
        scale: scale,
        logging: false,
        useCORS: true,
        ignoreElements: function (node) {
          if (!node || !node.id) return false;
          return node.id === 'page-load-overlay' || node.id === 'gob-capture-rec';
        },
      }).then(function (domShot) {
        phaserCanvas.style.visibility = '';
        restoreFixed();
        ctx.drawImage(domShot, 0, 0, out.width, out.height);
        u.restoreRecIndicator();
        var detail = options.detail || u.getEventTag() || 'manual';
        return u.saveCapture(
          out.toDataURL('image/png'),
          u.buildFilename(options.tag || 'court', detail)
        );
      }).catch(function (err) {
        phaserCanvas.style.visibility = '';
        restoreFixed();
        u.restoreRecIndicator();
        console.warn('[GOBCapture] Court capture failed:', err);
        return false;
      });
    });
  }

  window.GOBCaptureCourt = {
    isCourtPage: isCourtPage,
    captureCourtScreen: captureCourtScreen,
  };
})();
