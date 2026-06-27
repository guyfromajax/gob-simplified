/**
 * Shared helpers for the staging-only screen capture tool.
 */
(function () {
  'use strict';

  var eventTag = 'manual';

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
    setEventTag: setEventTag,
    getEventTag: getEventTag,
  };
})();
