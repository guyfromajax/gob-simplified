/**
 * Tutorial Alerts — contextual Sammy modals + nav glow on skip.
 *
 * Server-persisted dismissal (cross-device). Lesson progress remains local
 * (`GOB.isSeen`). Yields to archetype reveal + alpha feedback modals on FCC.
 */
(function () {
  'use strict';

  var ORDER = ['player-attributes', 'training', 'team-attributes', 'game-plans', 'playbooks', 'scouting', 'recruiting'];

  var LIVE = {
    'player-attributes': '/player-attributes.html',
    'training': '/tutorial-training.html',
    'team-attributes': '/team-attributes.html',
    'game-plans': '/game-plans.html',
    'playbooks': '/tutorial-playbooks.html',
    'scouting': '/scouting.html',
    'recruiting': '/tutorial-recruiting.html'
  };

  var LABELS = {
    'player-attributes': 'Player Attributes',
    'training': 'Training',
    'team-attributes': 'Team Attributes',
    'game-plans': 'Game Plans',
    'playbooks': 'Playbooks',
    'scouting': 'Scouting',
    'recruiting': 'Recruiting'
  };

  /* Lesson position within the hub's recommended 7-lesson curriculum (1-based). */
  var LESSON_TOTAL = 7;
  var LESSON_INDEX = {
    'player-attributes': 1,
    'training': 2,
    'team-attributes': 3,
    'game-plans': 4,
    'playbooks': 5,
    'scouting': 6,
    'recruiting': 7
  };

  var GENERIC_SAMMY = '/images/sammy_tutorial.png';

  /* Per-team Coach Sammy portraits — mirror of teamCoachAsset.js (that file is an
     ES module; this script is a classic IIFE, so the 8-team map is duplicated
     here intentionally). Lesson 1 uses the generic portrait; lessons 2–7 use the
     selected team's uniform, falling back to generic when no team is set. */
  var TEAM_COACH_ABBR = {
    'Bentley-Truman': 'BT',
    'Four Corners': 'FC',
    'Lancaster': 'Lan',
    'Little York': 'LY',
    'Morristown': 'Mor',
    'Ocean City': 'OC',
    'South Lancaster': 'SL',
    'Xavien': 'Xav'
  };

  function portraitFor(id) {
    if (id === 'player-attributes') return GENERIC_SAMMY;
    var team = '';
    try { team = localStorage.getItem('franchise_user_team') || ''; } catch (e) {}
    var abbr = TEAM_COACH_ABBR[team];
    return abbr ? '/images/coaches/' + abbr + '/Sammy-' + abbr + '.png' : GENERIC_SAMMY;
  }

  var BODIES = {
    'player-attributes': 'Nice work, Coach. Before you start your first franchise, get to know Player Attributes — they\'re the foundation for every decision ahead.',
    'training': 'You\'re about to run training for the first time, Coach. Take a minute with the Training tutorial first.',
    'team-attributes': 'You just evolved some of your team\'s attributes, Coach. The Team Attributes tutorial breaks down the impact of those changes.',
    'game-plans': 'Your first game is next, Coach. Run through the Game Plan tutorial before you tip off.',
    'playbooks': 'Hey Coach, we think you\'re ready for the Playbooks tutorial.',
    'scouting': 'You\'ve seen the Scouting Report tab by now, Coach. The Scouting tutorial covers how to read it and turn it into an edge.'
  };

  var meCache = null;
  var queue = [];
  var showing = false;
  var drainTimer = null;
  var drainRetries = 0;

  function sfx(f) {
    if (window.GOB && window.GOB.playSound) window.GOB.playSound(f);
  }

  function isSeenLesson(id) {
    return window.GOB && window.GOB.isSeen && window.GOB.isSeen(id);
  }

  function dismissed(id) {
    var list = (meCache && meCache.tutorial_alerts_dismissed) || [];
    return list.indexOf(id) !== -1;
  }

  function patchMe(patch) {
    meCache = Object.assign({}, meCache || {}, patch);
    window.__gobAuthMeData = Object.assign({}, window.__gobAuthMeData || {}, patch);
  }

  function apiPatch(path, body) {
    if (typeof API_CONFIG === 'undefined' || !API_CONFIG.buildUrl || !API_CONFIG.getAuthHeaders) {
      return Promise.resolve(null);
    }
    return fetch(API_CONFIG.buildUrl(path), {
      method: 'PATCH',
      headers: Object.assign({ 'Content-Type': 'application/json' }, API_CONFIG.getAuthHeaders()),
      body: JSON.stringify(body || {})
    }).then(function (res) { return res.ok ? res.json() : null; }).catch(function () { return null; });
  }

  function refreshMeFromServer() {
    if (typeof API_CONFIG === 'undefined' || !API_CONFIG.buildUrl || !API_CONFIG.getAuthHeaders) {
      return Promise.resolve(meCache);
    }
    return fetch(API_CONFIG.buildUrl('/api/auth/me'), { headers: API_CONFIG.getAuthHeaders() })
      .then(function (res) { return res.ok ? res.json() : meCache; })
      .then(function (data) {
        if (data) {
          meCache = data;
          window.__gobAuthMeData = data;
        }
        return meCache;
      })
      .catch(function () { return meCache; });
  }

  function markDismissed(alertId) {
    if (!dismissed(alertId)) {
      var next = ((meCache && meCache.tutorial_alerts_dismissed) || []).slice();
      next.push(alertId);
      patchMe({ tutorial_alerts_dismissed: next });
    }
    return apiPatch('/api/auth/tutorial-alert-dismiss', { alert_id: alertId });
  }

  function enrollFranchise(franchiseId) {
    if (!franchiseId) return Promise.resolve();
    if (meCache && meCache.tutorial_alerts_franchise_id) return Promise.resolve();
    return apiPatch('/api/auth/tutorial-alerts-enroll', { franchise_id: String(franchiseId) })
      .then(function () { return refreshMeFromServer(); });
  }

  function incrementCounter(franchiseId, field) {
    if (!franchiseId) return Promise.resolve();
    return apiPatch('/api/auth/tutorial-alerts-increment', {
      franchise_id: String(franchiseId),
      field: field
    }).then(function (data) {
      if (!data || data.skipped) return refreshMeFromServer();
      if (field === 'games') patchMe({ tutorial_alerts_games: data.value });
      if (field === 'training_returns') patchMe({ tutorial_alerts_training_returns: data.value });
      return refreshMeFromServer();
    });
  }

  function franchiseLocked(franchiseId) {
    var locked = meCache && meCache.tutorial_alerts_franchise_id;
    if (!locked) return true;
    return String(locked) === String(franchiseId);
  }

  function recruitingBody(games) {
    var n = parseInt(games, 10) || 6;
    return n + ' games in, Coach. Time to get smart on Recruiting — it\'s how you build your program for the long haul.';
  }

  function bodyFor(id) {
    if (id === 'recruiting') {
      return recruitingBody(meCache && meCache.tutorial_alerts_games);
    }
    return BODIES[id] || '';
  }

  function shouldYieldToOtherModals() {
    var me = meCache || window.__gobAuthMeData;
    if (!me) return false;
    /* These modals (archetype reveal, alpha feedback) only ever mount on the
       FCC. On any other screen — notably mode-select, where Player Attributes
       fires — there is nothing to yield to, and yielding here would defer the
       alert against a blocker that can never clear. Only gate on FCC. */
    if (!isFcc()) return false;
    /* Only yield to the archetype reveal if it will ACTUALLY render this visit:
       it requires a lead_archetype (>= 1 real game) — see archetypeReveal.js.
       Early-franchise alerts (training / team-attributes / playbooks) fire
       before the first game, when seen=false but no reveal can appear; yielding
       there would defer them against a blocker that never shows. */
    if (me.archetype_reveal_seen === false && me.lead_archetype) return true;
    if (me.alpha_feedback_submitted) return false;
    var games = parseInt(me.alpha_feedback_games, 10) || 0;
    var level = parseInt(me.alpha_feedback_prompt_level, 10) || 0;
    if (games >= 5 && level < 5) return true;
    if (games >= 2 && level < 2) return true;
    return false;
  }

  function isModeSelect() {
    return /\/mode-select\.html$/i.test(window.location.pathname || '');
  }

  function isFcc() {
    return (window.location.pathname || '').indexOf('franchise-command-center') !== -1;
  }

  function currentRelativeReturnUrl() {
    var params = new URLSearchParams(window.location.search);
    params.delete('tut_alert');
    var qs = params.toString();
    return window.location.pathname + (qs ? '?' + qs : '') + (window.location.hash || '');
  }

  function defaultReturnUrl(id) {
    if (id === 'player-attributes') return '/mode-select.html';
    if (isFcc()) return currentRelativeReturnUrl();
    return window.location.pathname + window.location.search + (window.location.hash || '');
  }

  function stashAlertResume(alertId, returnUrl) {
    if (window.GOBTutorialAlertResume && window.GOBTutorialAlertResume.setContext) {
      window.GOBTutorialAlertResume.setContext(alertId, returnUrl);
      return;
    }
    try {
      sessionStorage.setItem('gob_tut_alert_resume', JSON.stringify({
        entrySource: 'tutorial-alert',
        alertId: alertId,
        lessonId: alertId,
        returnUrl: returnUrl
      }));
    } catch (e) {}
  }

  /** Resolve FCC URL for Player Attributes "I'll do this later" (mode-select). */
  function fccUrlForPlayerAttributesLater() {
    if (window.GOBModeSelect && typeof window.GOBModeSelect.getFranchiseCommandCenterUrlForLater === 'function') {
      return window.GOBModeSelect.getFranchiseCommandCenterUrlForLater();
    }
    try {
      var fid = localStorage.getItem('franchise_id') || localStorage.getItem('franchiseId');
      var tid = localStorage.getItem('franchise_user_team_id');
      if (fid && typeof buildFranchiseLockerRoomUrl === 'function') {
        return buildFranchiseLockerRoomUrl(fid, tid);
      }
    } catch (e) {}
    return null;
  }

  /**
   * Where to send the user when they skip via "I'll do this later" — only when
   * an underlying action was blocked (intercept) or a concrete advance URL exists.
   */
  function runLaterAdvance(id, opts) {
    opts = opts || {};
    if (typeof opts.onLaterAdvance === 'function') {
      opts.onLaterAdvance();
      return;
    }
    var url = opts.advanceUrl;
    if (!url) {
      if (id === 'player-attributes') url = fccUrlForPlayerAttributesLater();
      else if (id === 'training' || id === 'game-plans') url = opts.returnUrl || null;
      /* team-attributes / playbooks / scouting / recruiting: already on FCC — no navigation */
    }
    if (!url) return;
    var current = window.location.pathname + window.location.search + (window.location.hash || '');
    var resolved = url.charAt(0) === '/' ? url : url.replace(/^\.\//, '/');
    if (resolved === current) return;
    window.location.href = url;
  }

  function eligibleIds(opts) {
    opts = opts || {};
    var out = [];
    var franchiseId = opts.franchiseId;
    var games = parseInt(meCache && meCache.tutorial_alerts_games, 10) || 0;
    var trainingReturns = parseInt(meCache && meCache.tutorial_alerts_training_returns, 10) || 0;

    ORDER.forEach(function (id) {
      if (dismissed(id)) return;

      if (id === 'player-attributes') {
        if (opts.checkPlayerAttributes && meCache && meCache.fte_v2_complete && isModeSelect()) out.push(id);
        return;
      }

      if (!franchiseId || !franchiseLocked(franchiseId)) return;

      if (id === 'training' && opts.checkTrainingClick) out.push(id);
      if (id === 'game-plans' && opts.checkPlayNextGame) out.push(id);
      if (id === 'team-attributes' && opts.checkFccReturn && trainingReturns >= 1) out.push(id);
      if (id === 'playbooks' && opts.checkFccReturn && trainingReturns >= 2) out.push(id);
      if (id === 'scouting' && opts.checkFccReturn && games >= 3) out.push(id);
      if (id === 'recruiting' && opts.checkFccReturn && games >= 6) out.push(id);
    });

    return out;
  }

  function getGlowTarget() {
    for (var i = 0; i < ORDER.length; i++) {
      var id = ORDER[i];
      if (!isSeenLesson(id) && dismissed(id)) return id;
    }
    return null;
  }

  function applyNavGlow() {
    var bar = document.getElementById('auth-bar');
    if (!bar) return;
    var link = bar.querySelector('.nav-tutorials-link');
    if (!link) return;

    var targetId = getGlowTarget();
    var callout = link.querySelector('.nav-tutorials-callout');

    if (!targetId) {
      link.classList.remove('is-alert-glow');
      link.removeAttribute('data-alert-glow');
      if (callout) callout.remove();
      return;
    }

    link.classList.add('is-alert-glow');
    link.setAttribute('data-alert-glow', targetId);
    if (!callout) {
      callout = document.createElement('span');
      callout.className = 'nav-tutorials-callout';
      link.appendChild(callout);
    }
    callout.textContent = 'Next: ' + (LABELS[targetId] || targetId);
  }

  /**
   * Whether an alert modal can be presented right now. False when the tutorial
   * modal builder hasn't loaded yet, or when a higher-priority modal (archetype
   * reveal / alpha feedback) is pending and we must yield to it.
   */
  function canShowAlert() {
    if (!window.GOB || !window.GOB.showTip) return false;
    if (shouldYieldToOtherModals()) return false;
    return true;
  }

  function showAlert(id, opts) {
    opts = opts || {};
    if (!canShowAlert()) return Promise.resolve(false);

    var returnUrl = opts.returnUrl || defaultReturnUrl(id);
    showing = true;
    return markDismissed(id).then(function () {
      return new Promise(function (resolve) {
        var closed = false;
        function finish(startedLesson) {
          if (closed) return;
          closed = true;
          showing = false;
          if (!startedLesson) applyNavGlow();
          resolve(startedLesson);
          drainQueue();
        }

        window.GOB.showTip({
          alertMode: true,
          id: id,
          topicLabel: LABELS[id],
          title: LABELS[id],
          body: bodyFor(id),
          href: LIVE[id] || '/tutorial.html',
          lessonIndex: LESSON_INDEX[id] || 1,
          lessonTotal: LESSON_TOTAL,
          portrait: portraitFor(id),
          cta: 'Start lesson',
          laterLabel: 'I\'ll do this later',
          onGo: function () {
            stashAlertResume(id, returnUrl);
            finish(true);
          },
          onLater: function () {
            finish(false);
            runLaterAdvance(id, opts);
          }
        });

        /* showTip marks dismissed via our pre-call; ensure glow after paint */
        requestAnimationFrame(applyNavGlow);
      });
    });
  }

  function enqueue(items) {
    items.forEach(function (item) {
      var id = typeof item === 'string' ? item : item.id;
      var returnUrl = typeof item === 'object' && item ? item.returnUrl : null;
      var advanceUrl = typeof item === 'object' && item ? item.advanceUrl : null;
      var onLaterAdvance = typeof item === 'object' && item ? item.onLaterAdvance : null;
      if (!id) return;
      var exists = queue.some(function (q) { return q.id === id; });
      if (!exists) queue.push({ id: id, returnUrl: returnUrl, advanceUrl: advanceUrl, onLaterAdvance: onLaterAdvance });
    });
    drainRetries = 0; // fresh batch — give the retry budget a clean slate
    drainQueue();
  }

  /* Bound the retry: a genuine yield clears when the blocking modal is dismissed,
     but those modals PATCH the server WITHOUT refreshing our meCache or
     re-dispatching gob:auth-me-loaded — so we must re-pull /api/auth/me to see
     the cleared state, and stop after a sane number of tries rather than poll
     forever if the user simply leaves the blocker open. */
  var MAX_DRAIN_RETRIES = 20; // ~24s at 1200ms

  function scheduleDrainRetry() {
    if (drainTimer) return;
    if (drainRetries >= MAX_DRAIN_RETRIES) return; // give up; re-evaluated on next FCC load
    drainTimer = setTimeout(function () {
      drainTimer = null;
      drainRetries += 1;
      refreshMeFromServer().then(drainQueue);
    }, 1200);
  }

  function drainQueue() {
    if (showing || !queue.length) return;
    /* Gate BEFORE dequeuing: if a higher-priority modal is up (or the modal
       builder isn't loaded yet), keep the alert queued and retry — don't drop
       it. Retries until the blocker clears (also re-driven by auth-me reload). */
    if (!canShowAlert()) {
      scheduleDrainRetry();
      return;
    }
    var next = queue.shift();
    showAlert(next.id, {
      returnUrl: next.returnUrl,
      advanceUrl: next.advanceUrl,
      onLaterAdvance: next.onLaterAdvance
    });
  }

  function evaluateAndShow(opts) {
    opts = opts || {};
    var ids = eligibleIds(opts);
    if (!ids.length) {
      applyNavGlow();
      return Promise.resolve(false);
    }
    var returnUrl = opts.returnUrl || null;
    enqueue(ids.map(function (id) {
      return { id: id, returnUrl: returnUrl || defaultReturnUrl(id) };
    }));
    return Promise.resolve(true);
  }

  function processFccReturn(franchiseId, eventType) {
    if (!isFcc() || !franchiseId) return Promise.resolve();
    return enrollFranchise(franchiseId).then(function () {
      if (!franchiseLocked(franchiseId)) return null;
      if (eventType === 'training_return') return incrementCounter(franchiseId, 'training_returns');
      if (eventType === 'game_complete') return incrementCounter(franchiseId, 'games');
      return null;
    }).then(function () {
      return evaluateAndShow({
        franchiseId: franchiseId,
        checkFccReturn: true
      });
    });
  }

  function onAuthMeLoaded(me) {
    meCache = me || window.__gobAuthMeData || null;
    applyNavGlow();

    if (meCache && meCache.fte_v2_complete && isModeSelect()) {
      evaluateAndShow({ checkPlayerAttributes: true });
    }

    /* A fresh auth-me usually means a blocking modal (archetype reveal / alpha
       feedback) just resolved — retry any alert deferred by the yield gate. */
    drainQueue();
  }

  function onFccDomReady() {
    if (!isFcc()) return;
    var params = new URLSearchParams(window.location.search);
    var franchiseId = params.get('franchise_id');
    var evt = params.get('tut_alert');
    if (!franchiseId) return;

    if (evt === 'training_return' || evt === 'game_complete') {
      processFccReturn(franchiseId, evt).then(function () {
        params.delete('tut_alert');
        var qs = params.toString();
        var next = window.location.pathname + (qs ? '?' + qs : '') + window.location.hash;
        try { history.replaceState(null, '', next); } catch (e) {}
      });
      return;
    }

    enrollFranchise(franchiseId).then(applyNavGlow);
  }

  function interceptTraining(franchiseId, navigate, returnUrl) {
    meCache = meCache || window.__gobAuthMeData || null;
    return enrollFranchise(franchiseId).then(function () {
      return refreshMeFromServer();
    }).then(function () {
      if (!franchiseLocked(franchiseId)) {
        if (navigate) navigate();
        return false;
      }
      var ids = eligibleIds({ franchiseId: franchiseId, checkTrainingClick: true });
      /* No eligible alert, OR a higher-priority modal is up / scripts not ready:
         let training proceed. Never swallow the click — blocking without showing
         a modal looks like a dead button. */
      if (!ids.length || !canShowAlert()) {
        if (navigate) navigate();
        return false;
      }
      return showAlert(ids[0], {
        returnUrl: returnUrl,
        advanceUrl: returnUrl,
        onLaterAdvance: navigate
      }).then(function () { return true; });
    });
  }

  function interceptPlayNextGame(franchiseId, setLineupUrl, navigate) {
    meCache = meCache || window.__gobAuthMeData || null;
    return enrollFranchise(franchiseId).then(function () {
      return refreshMeFromServer();
    }).then(function () {
      if (!franchiseLocked(franchiseId)) {
        if (navigate) navigate();
        return false;
      }
      var ids = eligibleIds({ franchiseId: franchiseId, checkPlayNextGame: true });
      if (!ids.length || !canShowAlert()) {
        if (navigate) navigate();
        return false;
      }
      return showAlert(ids[0], {
        returnUrl: setLineupUrl,
        advanceUrl: setLineupUrl,
        onLaterAdvance: navigate
      }).then(function () { return true; });
    });
  }

  window.GOBTutorialAlerts = {
    ORDER: ORDER,
    onAuthMeLoaded: onAuthMeLoaded,
    onFccDomReady: onFccDomReady,
    interceptTraining: interceptTraining,
    interceptPlayNextGame: interceptPlayNextGame,
    applyNavGlow: applyNavGlow,
    refreshMeFromServer: refreshMeFromServer,
    processFccReturn: processFccReturn
  };

  window.addEventListener('gob:auth-me-loaded', function (e) {
    onAuthMeLoaded((e && e.detail) || window.__gobAuthMeData);
  });

  window.addEventListener('gob:progress', applyNavGlow);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onFccDomReady);
  } else {
    onFccDomReady();
  }

  if (window.__gobAuthMeData) onAuthMeLoaded(window.__gobAuthMeData);
})();
