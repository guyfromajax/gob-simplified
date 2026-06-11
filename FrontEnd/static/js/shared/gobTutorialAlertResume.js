/**
 * Tutorial alert resume — sticky "Back To Game" footer on lesson sub-pages
 * when the user entered via a contextual alert modal or the training-page link.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'gob_tut_alert_resume';
  var VALID_ENTRY_SOURCES = { 'tutorial-alert': true, 'training-page': true };

  var PATH_TO_LESSON = {
    '/tutorial-player-attributes.html': 'player-attributes',
    '/tutorial-training.html': 'training',
    '/tutorial-team-attributes.html': 'team-attributes',
    '/tutorial-game-plans.html': 'game-plans',
    '/tutorial-playbooks.html': 'playbooks',
    '/tutorial-scouting.html': 'scouting',
    '/tutorial-recruiting.html': 'recruiting'
  };

  function lessonIdFromPath() {
    var path = (window.location.pathname || '').replace(/\/+$/, '') || '/';
    var id = PATH_TO_LESSON[path];
    if (id) return id;
    var key;
    for (key in PATH_TO_LESSON) {
      if (path.endsWith(key)) return PATH_TO_LESSON[key];
    }
    return null;
  }

  function isValidContext(ctx) {
    return !!(ctx && VALID_ENTRY_SOURCES[ctx.entrySource] && ctx.lessonId && ctx.returnUrl);
  }

  function readContext() {
    try {
      var raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      var ctx = JSON.parse(raw);
      if (!isValidContext(ctx)) return null;
      return ctx;
    } catch (e) {
      return null;
    }
  }

  function clearContext() {
    try { sessionStorage.removeItem(STORAGE_KEY); } catch (e) {}
  }

  function writeContext(lessonId, returnUrl, entrySource) {
    if (!lessonId || !returnUrl || !VALID_ENTRY_SOURCES[entrySource]) return;
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        entrySource: entrySource,
        alertId: lessonId,
        lessonId: lessonId,
        returnUrl: returnUrl
      }));
    } catch (e) {}
  }

  function setContext(alertId, returnUrl) {
    writeContext(alertId, returnUrl, 'tutorial-alert');
  }

  function setTrainingPageContext(returnUrl) {
    writeContext('training', returnUrl, 'training-page');
  }

  function isAtBottom(threshold) {
    var t = typeof threshold === 'number' ? threshold : 32;
    var doc = document.documentElement;
    return window.innerHeight + window.scrollY >= doc.scrollHeight - t;
  }

  function initFooter() {
    var lessonId = lessonIdFromPath();
    if (!lessonId) return;

    var ctx = readContext();
    if (!ctx || ctx.lessonId !== lessonId) return;

    document.body.classList.add('gob-tut--alert-resume');

    var back = document.querySelector('[data-gob-back]');
    if (back) back.hidden = true;

    document.querySelectorAll('.handoff').forEach(function (el) {
      el.remove();
    });

    if (document.querySelector('.gob-tut-alert-resume')) return;

    var bar = document.createElement('div');
    bar.className = 'gob-tut-alert-resume';
    bar.setAttribute('role', 'region');
    bar.setAttribute('aria-label', 'Return to game');

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'gob-btn gob-btn--ghost gob-btn--lg gob-tut-alert-resume__btn';
    btn.textContent = 'Back To Game';

    bar.appendChild(btn);
    document.body.appendChild(bar);

    function syncScrollState() {
      var ready = isAtBottom();
      btn.classList.toggle('is-ready', ready);
      btn.classList.toggle('gob-btn--ghost', !ready);
      btn.classList.toggle('gob-btn--action', ready);
    }

    btn.addEventListener('click', function () {
      if (window.GOB && window.GOB.playSound) window.GOB.playSound('click-tiny.wav');
      var url = ctx.returnUrl;
      clearContext();
      window.location.href = url;
    });

    window.addEventListener('scroll', syncScrollState, { passive: true });
    window.addEventListener('resize', syncScrollState);
    syncScrollState();
  }

  window.GOBTutorialAlertResume = {
    setContext: setContext,
    setTrainingPageContext: setTrainingPageContext,
    clearContext: clearContext,
    readContext: readContext,
    isValidContext: isValidContext
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFooter);
  } else {
    initFooter();
  }
})();
