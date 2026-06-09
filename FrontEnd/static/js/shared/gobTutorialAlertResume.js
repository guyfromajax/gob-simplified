/**
 * Tutorial alert resume — sticky "Back To Game" footer on lesson sub-pages
 * when the user entered via a contextual alert modal (primary CTA only).
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'gob_tut_alert_resume';

  var PATH_TO_LESSON = {
    '/player-attributes.html': 'player-attributes',
    '/tutorial-training.html': 'training',
    '/team-attributes.html': 'team-attributes',
    '/game-plans.html': 'game-plans',
    '/tutorial-playbooks.html': 'playbooks',
    '/scouting.html': 'scouting',
    '/tutorial-recruiting.html': 'recruiting'
  };

  function lessonIdFromPath() {
    var path = (window.location.pathname || '').replace(/\/+$/, '') || '/';
    return PATH_TO_LESSON[path] || null;
  }

  function readContext() {
    try {
      var raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      var ctx = JSON.parse(raw);
      if (!ctx || ctx.entrySource !== 'tutorial-alert' || !ctx.lessonId || !ctx.returnUrl) return null;
      return ctx;
    } catch (e) {
      return null;
    }
  }

  function clearContext() {
    try { sessionStorage.removeItem(STORAGE_KEY); } catch (e) {}
  }

  function setContext(alertId, returnUrl) {
    if (!alertId || !returnUrl) return;
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        entrySource: 'tutorial-alert',
        alertId: alertId,
        lessonId: alertId,
        returnUrl: returnUrl
      }));
    } catch (e) {}
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

    var handoff = document.querySelector('.handoff');
    if (handoff) handoff.hidden = true;

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
    clearContext: clearContext,
    readContext: readContext
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFooter);
  } else {
    initFooter();
  }
})();
