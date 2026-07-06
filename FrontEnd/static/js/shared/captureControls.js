/**
 * Arm/disarm state, keyboard shortcuts, and ● REC indicator (staging only).
 */
(function () {
  'use strict';

  var armed = false;
  var capturing = false;
  var stylesInjected = false;
  var started = false;

  function isTypingTarget(target) {
    if (!target) return false;
    var tag = (target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
    if (target.isContentEditable) return true;
    return false;
  }

  function isCaptureKey(event) {
    return event && (event.code === 'KeyC' || event.key === 'c' || event.key === 'C');
  }

  function injectStyles() {
    if (stylesInjected) return;
    stylesInjected = true;
    var style = document.createElement('style');
    style.id = 'gob-capture-rec-styles';
    style.textContent = [
      '#gob-capture-rec {',
      '  position: fixed;',
      '  top: 12px;',
      '  right: 12px;',
      '  z-index: 100002;',
      '  display: inline-flex;',
      '  align-items: center;',
      '  gap: 6px;',
      '  padding: 6px 10px;',
      '  border-radius: 999px;',
      '  background: rgba(40, 40, 48, 0.88);',
      '  border: 1px solid rgba(255, 255, 255, 0.18);',
      '  color: rgba(255, 255, 255, 0.82);',
      '  font: 600 11px/1 Inter, system-ui, sans-serif;',
      '  letter-spacing: 0.04em;',
      '  pointer-events: none;',
      '  user-select: none;',
      '}',
      'body.gob-capture-court-page #gob-capture-rec {',
      '  top: calc(var(--scoreboard-height, 120px) + 8px);',
      '}',
      'body.has-auth-bar #gob-capture-rec {',
      '  top: 68px;',
      '}',
      '#gob-capture-rec.is-armed {',
      '  background: rgba(120, 0, 0, 0.92);',
      '  border-color: rgba(255, 59, 48, 0.65);',
      '  box-shadow: 0 0 12px rgba(255, 59, 48, 0.35);',
      '  color: #fff;',
      '}',
      '#gob-capture-rec .gob-capture-rec-dot {',
      '  font-size: 13px;',
      '}',
      '#gob-capture-rec.is-idle .gob-capture-rec-dot {',
      '  color: rgba(255, 255, 255, 0.45);',
      '}',
      '#gob-capture-rec.is-armed .gob-capture-rec-dot {',
      '  color: #ff3b30;',
      '  animation: gob-capture-rec-pulse 1.6s ease-in-out infinite;',
      '}',
      '#gob-capture-rec.is-success {',
      '  background: rgba(20, 80, 45, 0.92);',
      '  border-color: rgba(72, 199, 116, 0.65);',
      '  color: #fff;',
      '}',
      '#gob-capture-rec.is-error {',
      '  background: rgba(120, 0, 0, 0.92);',
      '  border-color: rgba(255, 59, 48, 0.65);',
      '  color: #fff;',
      '}',
      '@keyframes gob-capture-rec-pulse {',
      '  0%, 100% { opacity: 1; }',
      '  50% { opacity: 0.45; }',
      '}',
    ].join('\n');
    document.head.appendChild(style);
  }

  function ensureIndicator() {
    injectStyles();
    var el = document.getElementById('gob-capture-rec');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'gob-capture-rec';
    el.className = 'is-idle';
    el.setAttribute('aria-live', 'polite');
    el.innerHTML = [
      '<span class="gob-capture-rec-dot" aria-hidden="true">○</span>',
      '<span class="gob-capture-rec-label">CAP · Shift+C</span>',
    ].join('');
    document.body.appendChild(el);
    return el;
  }

  function renderIndicator() {
    var el = ensureIndicator();
    el.classList.toggle('is-armed', armed);
    el.classList.toggle('is-idle', !armed);
    var dot = el.querySelector('.gob-capture-rec-dot');
    var label = el.querySelector('.gob-capture-rec-label');
    if (dot) dot.textContent = armed ? '●' : '○';
    if (label) label.textContent = armed ? 'REC · c' : 'CAP · Shift+C';
    el.setAttribute('aria-label', armed ? 'Screen capture armed' : 'Screen capture disarmed');
  }

  function setArmed(next) {
    armed = !!next;
    renderIndicator();
    if (window.GOBCaptureUtils) {
      window.GOBCaptureUtils.setEventTag('manual');
    }
    console.info('[GOBCapture]', armed ? 'armed — press c to capture' : 'disarmed');
  }

  function disarm() {
    if (!armed) return;
    setArmed(false);
  }

  function isArmed() {
    return armed;
  }

  function runManualCapture() {
    if (!armed || capturing) return;
    capturing = true;
    var utils = window.GOBCaptureUtils;
    if (utils) utils.setEventTag('manual');

    var promise;
    if (window.GOBCaptureCourt && window.GOBCaptureCourt.isCourtPage()) {
      promise = window.GOBCaptureCourt.captureCourtScreen({ detail: 'manual' });
    } else if (window.GOBCaptureDom) {
      promise = window.GOBCaptureDom.captureCurrentScreen({ detail: 'manual' });
    } else {
      promise = Promise.resolve(false);
    }

    Promise.resolve(promise).then(function (ok) {
      if (utils && typeof utils.flashCaptureStatus === 'function') {
        var errMsg = null;
        if (!ok && window.GOBCaptureDom && typeof window.GOBCaptureDom.getLastCaptureError === 'function') {
          errMsg = window.GOBCaptureDom.getLastCaptureError();
        }
        utils.flashCaptureStatus(!!ok, renderIndicator, errMsg);
      }
    }).finally(function () {
      capturing = false;
    });
  }

  function onKeyDown(event) {
    if (!event || isTypingTarget(event.target)) return;
    if (!isCaptureKey(event)) return;

    if (event.shiftKey) {
      event.preventDefault();
      event.stopImmediatePropagation();
      setArmed(!armed);
      return;
    }

    if (armed && !event.shiftKey && !event.metaKey && !event.ctrlKey && !event.altKey
      && (event.key === 'c' || event.code === 'KeyC')) {
      event.preventDefault();
      event.stopImmediatePropagation();
      runManualCapture();
    }
  }

  function start() {
    if (started) return;
    started = true;
    if (window.GOBCaptureCourt && window.GOBCaptureCourt.isCourtPage()) {
      document.body.classList.add('gob-capture-court-page');
    }
    setArmed(false);
    renderIndicator();
    window.addEventListener('keydown', onKeyDown, true);
    window.addEventListener('pageshow', disarm);
    window.addEventListener('pagehide', disarm);
    console.info('[GOBCapture] ready — Shift+C to arm, c to capture');
  }

  function init() {
    if (window.API_CONFIG && typeof window.API_CONFIG.isCaptureEnv === 'function') {
      if (!window.API_CONFIG.isCaptureEnv()) return;
    } else if (!window.GOB_CAPTURE_BOOTSTRAPPED) {
      return;
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', start, { once: true });
    } else {
      start();
    }
  }

  window.GOBCaptureControls = {
    init: init,
    isArmed: isArmed,
    setArmed: setArmed,
    disarm: disarm,
    runManualCapture: runManualCapture,
  };

  window.GOBCapture = {
    isArmed: isArmed,
    setArmed: setArmed,
    disarm: disarm,
    captureManual: runManualCapture,
  };
})();
