/**
 * Staging-only screen capture tool bootstrap.
 * Loads html2canvas + capture modules, then initializes keyboard controls.
 */
(function () {
  'use strict';

  if (window.GOB_CAPTURE_BOOTSTRAPPED) return;

  function isCaptureEnv() {
    if (window.API_CONFIG && typeof window.API_CONFIG.isCaptureEnv === 'function') {
      return window.API_CONFIG.isCaptureEnv();
    }
    var hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1') return true;
    if (hostname === 'staging.geekedoutbasketball.com') return true;
    if (hostname === 'gob-test.netlify.app') return true;
    if ((hostname.indexOf('.netlify.app') !== -1 || hostname.indexOf('.railway.app') !== -1)
      && (hostname.indexOf('staging') !== -1 || hostname.indexOf('test') !== -1)) {
      return true;
    }
    return false;
  }

  if (!isCaptureEnv()) return;
  window.GOB_CAPTURE_BOOTSTRAPPED = true;

  function assetUrl(path) {
    if (window.API_CONFIG && typeof window.API_CONFIG.buildStaticPath === 'function') {
      return window.API_CONFIG.buildStaticPath(path);
    }
    var prefix = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
      ? '/static'
      : '';
    return prefix + path;
  }

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var script = document.createElement('script');
      script.src = src;
      script.async = false;
      script.onload = function () { resolve(); };
      script.onerror = function () { reject(new Error('Failed to load ' + src)); };
      document.head.appendChild(script);
    });
  }

  function showBootstrapError(message) {
    console.error('[GOBCapture] bootstrap failed:', message);
    function paint() {
      if (!document.body) return;
      var el = document.getElementById('gob-capture-rec');
      if (!el) {
        el = document.createElement('div');
        el.id = 'gob-capture-rec';
        document.body.appendChild(el);
      }
      el.style.cssText = [
        'position:fixed',
        'top:12px',
        'right:12px',
        'z-index:100002',
        'padding:6px 10px',
        'border-radius:999px',
        'background:rgba(120,0,0,0.9)',
        'color:#fff',
        'font:600 11px/1 Inter,system-ui,sans-serif',
      ].join(';');
      el.textContent = 'CAP load failed — check console';
    }
    if (document.body) paint();
    else document.addEventListener('DOMContentLoaded', paint, { once: true });
  }

  var html2canvasLocal = assetUrl('/js/vendor/html2canvas.min.js');
  var html2canvasCdn = 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js';

  loadScript(html2canvasLocal)
    .catch(function () { return loadScript(html2canvasCdn); })
    .then(function () { return loadScript(assetUrl('/js/shared/captureUtils.js')); })
    .then(function () { return loadScript(assetUrl('/js/shared/captureDom.js')); })
    .then(function () { return loadScript(assetUrl('/js/shared/captureCourt.js')); })
    .then(function () { return loadScript(assetUrl('/js/shared/captureControls.js')); })
    .then(function () {
      if (window.GOBCaptureControls && typeof window.GOBCaptureControls.init === 'function') {
        window.GOBCaptureControls.init();
      }
    })
    .catch(function (err) {
      showBootstrapError(err && err.message ? err.message : String(err));
    });
})();
