/**
 * Tutorial Alerts — contextual Sammy modals + nav glow on skip.
 *
 * Server-persisted dismissal (cross-device). Lesson progress remains local
 * (`GOB.isSeen`). Yields to archetype reveal + alpha feedback modals on FCC.
 */
(function () {
  'use strict';

  var ORDER = ['player-attributes', 'training', 'team-attributes', 'playbooks', 'scouting', 'recruiting'];

  var LIVE = {
    'player-attributes': '/player-attributes.html',
    'training': '/tutorial-training.html',
    'team-attributes': '/team-attributes.html',
    'playbooks': '/tutorial-playbooks.html',
    'scouting': '/scouting.html',
    'recruiting': '/tutorial-recruiting.html'
  };

  var LABELS = {
    'player-attributes': 'Player Attributes',
    'training': 'Training',
    'team-attributes': 'Team Attributes',
    'playbooks': 'Playbooks',
    'scouting': 'Scouting',
    'recruiting': 'Recruiting'
  };

  var BODIES = {
    'player-attributes': 'Nice work, Coach. Before you start your first franchise, get to know Player Attributes — they\'re the foundation for every decision ahead.',
    'training': 'You\'re about to run training for the first time, Coach. Take a minute with the Training tutorial first.',
    'team-attributes': 'You just evolved some of your team\'s attributes, Coach. The Team Attributes tutorial breaks down the impact of those changes.',
    'playbooks': 'Hey Coach, we think you\'re ready for the Playbooks tutorial.',
    'scouting': 'You\'ve seen the Scouting Report tab by now, Coach. The Scouting tutorial covers how to read it and turn it into an edge.'
  };

  var meCache = null;
  var queue = [];
  var showing = false;
  var drainTimer = null;

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
    if (me.archetype_reveal_seen === false) return true;
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
          cta: 'Tutorials',
          laterLabel: 'I\'ll Do This Later',
          onGo: function () { finish(true); },
          onLater: function () { finish(false); }
        });

        /* showTip marks dismissed via our pre-call; ensure glow after paint */
        requestAnimationFrame(applyNavGlow);
      });
    });
  }

  function enqueue(ids) {
    ids.forEach(function (id) {
      if (queue.indexOf(id) === -1) queue.push(id);
    });
    drainQueue();
  }

  function scheduleDrainRetry() {
    if (drainTimer) return;
    drainTimer = setTimeout(function () {
      drainTimer = null;
      drainQueue();
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
    showAlert(next);
  }

  function evaluateAndShow(opts) {
    var ids = eligibleIds(opts);
    if (!ids.length) {
      applyNavGlow();
      return Promise.resolve(false);
    }
    enqueue(ids);
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

  function interceptTraining(franchiseId, navigate) {
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
      return showAlert(ids[0]).then(function () { return true; });
    });
  }

  window.GOBTutorialAlerts = {
    ORDER: ORDER,
    onAuthMeLoaded: onAuthMeLoaded,
    onFccDomReady: onFccDomReady,
    interceptTraining: interceptTraining,
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
