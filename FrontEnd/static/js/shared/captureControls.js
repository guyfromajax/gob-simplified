/**
 * Arm/disarm state, keyboard shortcuts, and ● REC indicator (staging only).
 */
(function () {
  'use strict';

  var armed = false;
  var capturing = false;
  var stylesInjected = false;

  function isTypingTarget(target) {
    if (!target) return false;
    var tag = (target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
    if (target.isContentEditable) return true;
    return false;
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
      '  display: none;',
      '  align-items: center;',
      '  gap: 6px;',
      '  padding: 6px 10px;',
      '  border-radius: 999px;',
      '  background: rgba(120, 0, 0, 0.88);',
      '  border: 1px solid rgba(255, 59, 48, 0.65);',
      '  box-shadow: 0 0 12px rgba(255, 59, 48, 0.35);',
      '  color: #fff;',
      '  font: 600 12px/1 Inter, system-ui, sans-serif;',
      '  letter-spacing: 0.04em;',
      '  pointer-events: none;',
      '  user-select: none;',
      '}',
      'body.gob-capture-court-page #gob-capture-rec {',
      '  top: calc(var(--scoreboard-height, 120px) + 8px);',
      '}',
      '#gob-capture-rec.is-armed {',
      '  display: inline-flex;',
      '}',
      '#gob-capture-rec .gob-capture-rec-dot {',
      '  color: #ff3b30;',
      '  font-size: 14px;',
      '  animation: gob-capture-rec-pulse 1.6s ease-in-out infinite;',
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
    el.setAttribute('aria-live', 'polite');
    el.innerHTML = '<span class="gob-capture-rec-dot" aria-hidden="true">●</span><span>REC</span>';
    document.body.appendChild(el);
    return el;
  }

  function renderIndicator() {
    var el = ensureIndicator();
    el.classList.toggle('is-armed', armed);
    el.setAttribute('aria-label', armed ? 'Screen capture armed' : 'Screen capture disarmed');
  }

  function setArmed(next) {
    armed = !!next;
    renderIndicator();
    if (window.GOBCaptureUtils) {
      window.GOBCaptureUtils.setEventTag(armed ? 'manual' : 'manual');
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

    Promise.resolve(promise).finally(function () {
      capturing = false;
    });
  }

  function onKeyDown(event) {
    if (!event || isTypingTarget(event.target)) return;

    var key = event.key;
    if (key === 'c' || key === 'C') {
      if (event.shiftKey) {
        event.preventDefault();
        setArmed(!armed);
        return;
      }
      if (key === 'c' && armed) {
        event.preventDefault();
        runManualCapture();
      }
    }
  }

  function init() {
    if (window.API_CONFIG && typeof window.API_CONFIG.isCaptureEnv === 'function') {
      if (!window.API_CONFIG.isCaptureEnv()) return;
    } else if (!window.GOB_CAPTURE_BOOTSTRAPPED) {
      return;
    }

    function start() {
      if (window.GOBCaptureCourt && window.GOBCaptureCourt.isCourtPage()) {
        document.body.classList.add('gob-capture-court-page');
      }
      setArmed(false);
      renderIndicator();
      window.addEventListener('keydown', onKeyDown);
      window.addEventListener('pageshow', disarm);
      window.addEventListener('pagehide', disarm);
      console.info('[GOBCapture] ready — Shift+C to arm, c to capture');
    }

    if (document.body) {
      start();
    } else {
      document.addEventListener('DOMContentLoaded', start, { once: true });
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
