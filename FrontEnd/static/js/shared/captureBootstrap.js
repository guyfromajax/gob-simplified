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

  function staticPrefix() {
    if (window.API_CONFIG && typeof window.API_CONFIG.buildStaticPath === 'function') {
      return window.API_CONFIG.buildStaticPath('');
    }
    var hostname = window.location.hostname;
    return (hostname === 'localhost' || hostname === '127.0.0.1') ? '/static' : '';
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

  var base = staticPrefix() + '/js/shared/';
  var chain = loadScript('https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js')
    .then(function () { return loadScript(base + 'captureUtils.js'); })
    .then(function () { return loadScript(base + 'captureDom.js'); })
    .then(function () { return loadScript(base + 'captureCourt.js'); })
    .then(function () { return loadScript(base + 'captureControls.js'); })
    .then(function () {
      if (window.GOBCaptureControls && typeof window.GOBCaptureControls.init === 'function') {
        window.GOBCaptureControls.init();
      }
    });

  chain.catch(function (err) {
    console.warn('[GOBCapture] bootstrap failed:', err);
  });
})();
