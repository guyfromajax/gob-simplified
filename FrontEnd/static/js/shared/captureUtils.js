/**
 * Shared helpers for the staging-only screen capture tool.
 */
(function () {
  'use strict';

  var eventTag = 'manual';
  var statusTimer = null;

  function pad2(n) {
    return String(n).padStart(2, '0');
  }

  function buildFilename(tag, detail) {
    var now = new Date();
    var ts = [
      now.getFullYear(),
      pad2(now.getMonth() + 1),
      pad2(now.getDate()),
    ].join('-') + '_' + [
      pad2(now.getHours()),
      pad2(now.getMinutes()),
      pad2(now.getSeconds()),
    ].join('-');
    var parts = ['gob', tag || 'screen'];
    if (detail) parts.push(String(detail).replace(/\s+/g, '-'));
    parts.push(ts);
    return parts.join('_') + '.png';
  }

  function saveCapture(dataUrl, filename) {
    if (!dataUrl) return false;
    var link = document.createElement('a');
    link.download = filename || buildFilename('screen', '');
    link.href = dataUrl;
    document.body.appendChild(link);
    link.click();
    link.remove();
    return true;
  }

  function getRecIndicator() {
    return document.getElementById('gob-capture-rec');
  }

  function hideRecIndicator() {
    var el = getRecIndicator();
    if (!el) return;
    el.dataset.capturePrevVisibility = el.style.visibility || '';
    el.style.visibility = 'hidden';
  }

  function restoreRecIndicator() {
    var el = getRecIndicator();
    if (!el) return;
    el.style.visibility = el.dataset.capturePrevVisibility || '';
    delete el.dataset.capturePrevVisibility;
  }

  function flashCaptureStatus(ok, restoreLabel, message) {
    var el = getRecIndicator();
    if (!el) return;
    var label = el.querySelector('.gob-capture-rec-label');
    if (!label) return;
    if (statusTimer) {
      clearTimeout(statusTimer);
      statusTimer = null;
    }
    el.classList.remove('is-success', 'is-error');
    el.classList.add(ok ? 'is-success' : 'is-error');
    if (ok) {
      label.textContent = '✓ saved';
    } else if (message) {
      label.textContent = message.length > 28 ? message.slice(0, 28) + '…' : message;
    } else {
      label.textContent = 'capture failed';
    }
    el.style.visibility = '';
    statusTimer = setTimeout(function () {
      el.classList.remove('is-success', 'is-error');
      if (typeof restoreLabel === 'function') {
        restoreLabel();
      }
      statusTimer = null;
    }, ok ? 1400 : 2600);
  }

  function setEventTag(tag) {
    eventTag = tag || 'manual';
  }

  function getEventTag() {
    return eventTag;
  }

  window.GOBCaptureUtils = {
    buildFilename: buildFilename,
    saveCapture: saveCapture,
    hideRecIndicator: hideRecIndicator,
    restoreRecIndicator: restoreRecIndicator,
    flashCaptureStatus: flashCaptureStatus,
    setEventTag: setEventTag,
    getEventTag: getEventTag,
  };
})();
