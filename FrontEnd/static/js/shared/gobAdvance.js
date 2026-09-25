/**
 * Shared Advance button. Same labels, dataset.mode, and click routes as the Office.
 * The Office passes its existing helpers. Browse pages use the defaults below.
 */
(function () {
  'use strict';
  if (window.__gobAdvanceStarted) return;
  window.__gobAdvanceStarted = true;

  var INVITE_FIRST_WEEK = 20;
  var INVITE_LAST_WEEK = 26;
  var SIGNING_DAY_WEEK = 35;
  var CONFIRM_NAV_DELAY_MS = 200;

  var EOS_PLAY_CTA_BY_WEEK = Object.freeze({
    27: 'Play Conference Tourney First Round',
    28: 'Play Conference Tourney Semifinals',
    29: 'Play Conference Tourney Championship',
    30: 'Play Region Tourney First Round',
    31: 'Play Region Tourney Championship',
    32: 'Play National Tourney First Round',
    33: 'Play National Tourney Semifinals',
    34: 'Play National Championship!',
  });

  var EOS_SIM_CTA_BY_WEEK = Object.freeze({
    28: 'Sim Conference Tourney Semifinals',
    29: 'Sim Conference Tourney Championship',
    30: 'Sim Region Tourney First Round',
    31: 'Sim Region Tourney Championship',
    32: 'Sim National Tourney First Round',
    33: 'Sim National Tourney Semifinals',
    34: 'Sim National Championship',
  });

  var EOS_SIM_OVERLAY_BY_WEEK = Object.freeze({
    28: 'Simming Conference Semifinals',
    29: 'Simming Conference Finals',
    30: 'Simming Region Semifinals',
    31: 'Simming Region Finals',
    32: 'Simming National First Round',
    33: 'Simming National Semifinals',
    34: 'Simming National Finals',
  });

  var ccInflight = null;
  var ccBody = null;

  function isCommandCenterUrl(url) {
    return String(url || '').indexOf('/franchise/command-center/data') !== -1;
  }

  function jsonResponse(data) {
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  function installFetchWatch() {
    if (window.__gobCcFetchWatch || typeof window.fetch !== 'function') return;
    window.__gobCcFetchWatch = true;
    var orig = window.fetch;
    window.fetch = function (input, init) {
      var url = typeof input === 'string' ? input : (input && input.url) || '';
      var method = (init && init.method) || (input && input.method) || 'GET';
      if (!isCommandCenterUrl(url) || String(method).toUpperCase() !== 'GET') {
        return orig.apply(this, arguments);
      }
      if (ccBody) return Promise.resolve(jsonResponse(ccBody));
      if (ccInflight) {
        return ccInflight.then(function (data) { return jsonResponse(data); });
      }
      var started = performance.now();
      var pending = orig.apply(this, arguments);
      ccInflight = pending.then(function (res) {
        return res.clone().json();
      }).then(function (data) {
        ccBody = data;
        if (data && !window.__gobCommandCenterData) {
          window.__gobCommandCenterData = data;
          window.__gobAdvanceLoadMs = performance.now() - started;
          window.__gobAdvanceLoadReused = false;
        }
        return data;
      }).catch(function () { return null; });
      return pending;
    };
  }

  function playSound(filename) {
    import('/js/shared/uiSfx.js').then(function (m) { m.playSfx(filename, 0.7); }).catch(function () {});
  }

  function waitForConfirmSfx() {
    return new Promise(function (resolve) { setTimeout(resolve, CONFIRM_NAV_DELAY_MS); });
  }

  function cpuSimNeedsRecovery(data) {
    var resume = data && data.cpu_sim_resume;
    return !!(resume && resume.phase_b_required && resume.can_resume_phase_b);
  }

  function eosOverlayCopy(week) {
    var n = Number(week || 0);
    return EOS_SIM_OVERLAY_BY_WEEK[n] || 'Simming Tournament Games';
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function flashSeasonAdvanceScreen() {
    var existing = document.querySelector('.fcc-season-advance-flash');
    if (existing) existing.remove();
    var flash = document.createElement('div');
    flash.className = 'fcc-season-advance-flash';
    flash.setAttribute('aria-hidden', 'true');
    document.body.appendChild(flash);
    var cleanup = function () { flash.remove(); };
    flash.addEventListener('animationend', cleanup, { once: true });
    window.setTimeout(cleanup, 500);
  }

  function showSeasonAdvanceOverlay(nextSeason) {
    var prev = document.querySelector('.fcc-season-advance');
    if (prev) prev.remove();
    var logo = document.getElementById('team-logo');
    var src = (logo && logo.src) || '/images/teams/general/general_banner_primary.jpg';
    var overlay = document.createElement('div');
    overlay.className = 'fcc-season-advance';
    overlay.setAttribute('role', 'status');
    overlay.setAttribute('aria-live', 'polite');
    overlay.innerHTML = ''
      + '<div class="fcc-season-advance__stack">'
      + '<img class="fcc-season-advance__logo" src="' + escapeHtml(src) + '" alt="">'
      + '<div class="fcc-season-advance__copy">Advancing To Season ' + escapeHtml(nextSeason) + '</div>'
      + '<div class="fcc-season-advance__bar"><i></i></div>'
      + '</div>';
    document.body.appendChild(overlay);
    return overlay;
  }

  function showNewSeasonConfirmModal() {
    var overlay = document.createElement('div');
    overlay.className = 'gob-modal-overlay fcc-new-season-modal is-visible';
    overlay.setAttribute('aria-hidden', 'false');
    overlay.innerHTML = ''
      + '<div class="gob-modal-backdrop"></div>'
      + '<div class="gob-modal-box" role="dialog" aria-modal="true" aria-labelledby="fcc-new-season-title" aria-describedby="fcc-new-season-copy">'
      + '<div class="gob-modal-accent is-green"></div>'
      + '<div class="gob-modal-body">'
      + '<h3 id="fcc-new-season-title" class="gob-modal-title">Go To Next Season?</h3>'
      + '<p id="fcc-new-season-copy" class="gob-modal-subtitle">This will create the next season for this franchise instance. Your current season cannot be reopened after you proceed.</p>'
      + '</div>'
      + '<div class="gob-modal-actions">'
      + '<button type="button" class="gob-modal-btn-secondary" id="fcc-new-season-cancel">Cancel</button>'
      + '<button type="button" class="gob-modal-btn-primary is-green" id="fcc-new-season-proceed">Start Next Season</button>'
      + '</div></div>';
    var close = function () {
      document.removeEventListener('keydown', onKeydown);
      overlay.remove();
    };
    var onKeydown = function (event) {
      if (event.key === 'Escape') close();
    };
    overlay.addEventListener('click', function (event) {
      if (event.target === overlay || event.target.classList.contains('gob-modal-backdrop')) close();
    });
    document.addEventListener('keydown', onKeydown);
    overlay.closeGobModal = close;
    document.body.appendChild(overlay);
    var cancel = overlay.querySelector('#fcc-new-season-cancel');
    if (cancel) cancel.focus();
    return overlay;
  }

  function normalizeHexColor(value) {
    var raw = String(value || '').trim();
    if (!/^#?[0-9a-fA-F]{6}$/.test(raw)) return null;
    return raw.charAt(0) === '#' ? raw.toUpperCase() : ('#' + raw.toUpperCase());
  }

  function emptyParams() {
    if (window.FranchiseContext && window.FranchiseContext.createParams) {
      return window.FranchiseContext.createParams();
    }
    return new URLSearchParams();
  }

  function currentRelativeUrl() {
    if (typeof getCurrentRelativeUrl === 'function') return getCurrentRelativeUrl();
    return window.location.pathname + window.location.search;
  }

  function queryId(name) {
    try {
      return new URLSearchParams(window.location.search).get(name) || '';
    } catch (err) {
      return '';
    }
  }

  function updatePlayButton(data, env) {
    var playNowBtn = document.getElementById('play-now');
    if (!playNowBtn || !data) return;
    env = env || {};
    var userTeamId = env.userTeamId;
    playNowBtn.classList.remove('is-loading');

    var eosTournamentActive = data.eos_tournament_active || false;
    var eosTournament = data.eos_tournament;
    var week = Number(data.week || 1);
    playNowBtn.dataset.week = String(week);
    var trainingDisabledForEos = !!data.training_disabled_for_eos;
    var trainingDisabledForPostseason = !!data.training_disabled_for_postseason || week >= 27;
    var userEliminated = data.user_eliminated != null ? !!data.user_eliminated : null;
    var offerSimRest = data.offer_sim_rest != null ? !!data.offer_sim_rest : null;
    var regionQualified = !!data.region_qualified;
    var hasEosGameThisWeek = !!data.has_eos_game_this_week;
    var needsRecovery = env.fccCpuSimNeedsRecovery || cpuSimNeedsRecovery;

    if (needsRecovery(data)) {
      playNowBtn.textContent = 'Finish Computer Games';
      playNowBtn.dataset.mode = 'finish-cpu-sims';
      return;
    }

    var userTeamEliminated = false;
    if (eosTournamentActive && eosTournament && userTeamId && userEliminated == null) {
      var bracket = eosTournament.bracket || {};
      var allMatchups = [].concat(bracket.round1 || [], bracket.round2 || [], bracket.final || []);
      var userInMatchup = allMatchups.some(function (m) {
        return String(m.home_team) === String(userTeamId) || String(m.away_team) === String(userTeamId);
      });
      userTeamEliminated = !userInMatchup && week >= 27;
    }

    var eliminated = userEliminated != null ? userEliminated : userTeamEliminated;
    var showSimRest = offerSimRest != null ? offerSimRest : (eliminated && eosTournamentActive && !(eosTournament && eosTournament.completed));
    var tournamentComplete = !!(eosTournament && eosTournament.completed);
    var cutRequired = !!data.cut_required;

    var wire = data.recruiting_wire || {};
    var inviteWindow = week >= INVITE_FIRST_WEEK && week <= INVITE_LAST_WEEK;
    var invitesPending = inviteWindow && Number(wire.board_saved_week || 0) !== week;

    if (cutRequired) {
      playNowBtn.textContent = 'Assign Practice Squad';
      playNowBtn.dataset.mode = 'cut-players';
    } else if (invitesPending) {
      playNowBtn.textContent = week === INVITE_FIRST_WEEK ? 'Set Recruit Invites' : 'Review Recruit Invites';
      playNowBtn.dataset.mode = 'recruit-invites';
    } else if (week === 35 && wire.week_35_orders_submitted) {
      playNowBtn.textContent = 'Run Recruiting Day';
      playNowBtn.dataset.mode = 'week35-run';
    } else if (week === 35) {
      playNowBtn.textContent = 'Run Signing Day';
      playNowBtn.dataset.mode = 'week35-recruiting';
    } else if (week === 36 && !wire.week_36_results_seen) {
      playNowBtn.textContent = 'View Recruiting Results';
      playNowBtn.dataset.mode = 'view-recruiting-results';
    } else if (week === 36) {
      playNowBtn.textContent = 'Go To Next Season';
      playNowBtn.dataset.mode = 'new-season';
    } else if (tournamentComplete && week >= 37) {
      playNowBtn.textContent = 'Go To Next Season';
      playNowBtn.dataset.mode = 'new-season';
    } else if (showSimRest && eosTournamentActive) {
      playNowBtn.textContent = EOS_SIM_CTA_BY_WEEK[week] || 'Sim Next Round';
      playNowBtn.dataset.mode = 'sim-rest-tournament';
    } else if (
      trainingDisabledForPostseason
      && !eliminated
      && regionQualified
      && week >= 27
      && week <= 29
      && !hasEosGameThisWeek
    ) {
      playNowBtn.textContent = EOS_SIM_CTA_BY_WEEK[week] || 'Sim Next Round';
      playNowBtn.dataset.mode = 'sim-rest-tournament';
    } else if (trainingDisabledForPostseason && !eliminated) {
      playNowBtn.textContent = EOS_PLAY_CTA_BY_WEEK[week] || 'Play Next Game';
      playNowBtn.dataset.mode = 'play';
    } else if (trainingDisabledForEos || eliminated) {
      playNowBtn.textContent = 'Go To Next Season';
      playNowBtn.dataset.mode = 'new-season';
    } else {
      var trainingCompleted = data.training_completed || false;
      var sessionType = data.session_type || 'in-season';
      if (!trainingCompleted) {
        var cpuResumeRequired = !!(data.cpu_training_resume && data.cpu_training_resume.required);
        playNowBtn.textContent = cpuResumeRequired
          ? 'Resume Training'
          : (sessionType === 'preseason' ? 'Run Training Camp' : 'Run Training');
        playNowBtn.dataset.mode = 'training';
      } else {
        playNowBtn.textContent = 'Play Next Game';
        playNowBtn.dataset.mode = 'play';
      }
    }
  }

  function updateEditRecruitingButton(data, env) {
    var btn = document.getElementById('fcc-edit-recruiting');
    if (!btn) return;
    env = env || {};
    var week = Number((data && data.week) || 1);
    var wire = (data && data.recruiting_wire) || {};
    var inviteWindow = week >= INVITE_FIRST_WEEK && week <= INVITE_LAST_WEEK;
    var label = inviteWindow && Number(wire.board_saved_week || 0) === week ? 'Edit Recruit Invites'
      : week === SIGNING_DAY_WEEK && wire.week_35_orders_submitted ? 'Edit Recruiting Orders'
        : null;
    btn.style.display = label ? 'block' : 'none';
    if (!label) return;
    btn.textContent = label;
    if (!btn.dataset.wireBound) {
      btn.dataset.wireBound = '1';
      btn.addEventListener('click', function () {
        var open = env.openRecruitingSurface;
        if (typeof open === 'function') void open();
      });
    }
  }

  function bind(button, envFn) {
    if (!button || button.dataset.gobAdvanceBound === '1') return;
    button.dataset.gobAdvanceBound = '1';
    button.addEventListener('click', function () {
      var env = typeof envFn === 'function' ? envFn() : (envFn || {});
      onAdvanceClick(button, env);
    });
  }

  async function onAdvanceClick(playNowBtn, env) {
    if (playNowBtn.classList.contains('is-loading')) return;
    var advanceLabel = playNowBtn.textContent;
    playNowBtn.classList.add('is-loading');
    playNowBtn.textContent = 'STARTING…';
    var settleAdvance = function () {
      playNowBtn.classList.remove('is-loading');
      if (playNowBtn.textContent === 'STARTING…') playNowBtn.textContent = advanceLabel;
    };
    playSound('confirm-1-lowervol.wav');
    var confirmSfxReady = waitForConfirmSfx();
    var mode = playNowBtn.dataset.mode || 'play';
    var franchiseId = env.franchiseId;
    var userTeamId = env.userTeamId;
    var fetchJSON = env.fetchJSON;
    var needsRecovery = env.fccCpuSimNeedsRecovery || cpuSimNeedsRecovery;
    var recover = env.recoverCpuSimsBeforeFccRender;

    if (mode === 'finish-cpu-sims') {
      var topData = await fetchJSON(apiUrl(franchiseId));
      var recovered = recover ? await recover(topData) : topData;
      if (recovered && !needsRecovery(recovered)) {
        var fccUrl = '/franchise-command-center.html?franchise_id=' + encodeURIComponent(franchiseId);
        if (window.GOBNav && window.GOBNav.exitFlow) window.GOBNav.exitFlow(fccUrl);
        else if (window.GOBNav) window.GOBNav.replace(fccUrl);
        else window.location.replace(fccUrl);
      } else {
        updatePlayButton(recovered || topData, env);
      }
      return;
    }

    if (mode === 'training') {
      var trainingData = await fetchJSON(apiUrl(franchiseId));
      if (trainingData && (trainingData.training_disabled_for_eos || trainingData.training_disabled_for_postseason)) {
        settleAdvance();
        return;
      }
      var sessionType = (trainingData && trainingData.session_type) || 'in-season';
      var params = env.emptyParams ? env.emptyParams() : emptyParams();
      params.set('franchise_id', franchiseId);
      params.set('mode', 'franchise');
      params.set('session_type', sessionType);
      params.set('return_url', env.getCurrentRelativeUrl ? env.getCurrentRelativeUrl() : currentRelativeUrl());
      if (userTeamId) params.set('team_id', userTeamId);
      var trainingReturnUrl = '/training.html?' + params.toString();
      var navigateToTraining = async function () {
        await confirmSfxReady;
        try {
          var music = await import('/js/musicController.js');
          music.clearFranchiseMusicState();
        } catch (err) {}
        if (window.GOBNav && window.GOBNav.go) window.GOBNav.go(trainingReturnUrl);
        else window.location.assign(trainingReturnUrl);
      };
      if (window.GOBTutorialAlerts) {
        var blocked = await window.GOBTutorialAlerts.interceptTraining(franchiseId, navigateToTraining, trainingReturnUrl);
        if (blocked) {
          settleAdvance();
          return;
        }
      } else {
        await navigateToTraining();
      }
      return;
    }

    if (mode === 'recruit-invites' || mode === 'view-recruiting-results') {
      if (env.openRecruitingSurface) await env.openRecruitingSurface();
      return;
    }

    if (mode === 'week35-run') {
      var runParams = env.emptyParams ? env.emptyParams() : emptyParams();
      runParams.set('franchise_id', franchiseId);
      runParams.set('team_id', userTeamId);
      runParams.set('from', 'fcc');
      runParams.set('action', 'run');
      runParams.set('return_url', env.getCurrentRelativeUrl ? env.getCurrentRelativeUrl() : currentRelativeUrl());
      await confirmSfxReady;
      try {
        var musicRun = await import('/js/musicController.js');
        musicRun.clearFranchiseMusicState();
      } catch (err2) {}
      var runUrl = '/recruiting.html?' + runParams.toString();
      if (window.GOBNav && window.GOBNav.go) window.GOBNav.go(runUrl);
      else window.location.assign(runUrl);
      return;
    }

    if (mode === 'week35-recruiting') {
      var recParams = env.emptyParams ? env.emptyParams() : emptyParams();
      recParams.set('franchise_id', franchiseId);
      recParams.set('team_id', userTeamId);
      recParams.set('from', 'fcc');
      recParams.set('return_url', env.getCurrentRelativeUrl ? env.getCurrentRelativeUrl() : currentRelativeUrl());
      var recruitingUrl = '/recruiting.html?' + recParams.toString();
      await confirmSfxReady;
      try {
        var musicRec = await import('/js/musicController.js');
        musicRec.clearFranchiseMusicState();
      } catch (err3) {}
      if (window.GOBNav && window.GOBNav.go) window.GOBNav.go(recruitingUrl);
      else window.location.assign(recruitingUrl);
      return;
    }

    if (mode === 'cut-players') {
      await confirmSfxReady;
      var cutUrl = env.buildAssignPracticeSquadUrl ? env.buildAssignPracticeSquadUrl() : '';
      if (window.GOBNav && window.GOBNav.go) window.GOBNav.go(cutUrl);
      else window.location.assign(cutUrl);
      return;
    }

    if (mode === 'sim-rest-tournament') {
      var originalText = advanceLabel;
      playNowBtn.disabled = true;
      var week = Number(playNowBtn.dataset.week || (env.topData && env.topData.week) || 0);
      if (window.PageLoadOverlay && window.PageLoadOverlay.show) {
        window.PageLoadOverlay.show({
          variant: 'pulse',
          title: (env.fccEosSimOverlayCopy || eosOverlayCopy)(week),
          showBanner: false,
        });
      }
      try {
        var res = await fetch(window.API_CONFIG.buildUrl('/franchise/sim-rest-of-tournament'), {
          method: 'POST',
          headers: Object.assign({ 'Content-Type': 'application/json' }, window.API_CONFIG.getAuthHeaders()),
          body: JSON.stringify({ franchise_id: franchiseId }),
        });
        if (!res.ok) throw new Error('Simulation failed');
        await confirmSfxReady;
        location.reload();
      } catch (err4) {
        console.error(err4);
        if (window.PageLoadOverlay && window.PageLoadOverlay.hide) window.PageLoadOverlay.hide();
        alert('Unable to simulate tournament');
        playNowBtn.disabled = false;
        playNowBtn.textContent = originalText;
        settleAdvance();
      }
      return;
    }

    if (mode === 'new-season') {
      settleAdvance();
      var showModal = env.showNewSeasonConfirmModal || showNewSeasonConfirmModal;
      var modal = showModal();
      var closeModal = function () {
        if (typeof modal.closeGobModal === 'function') modal.closeGobModal();
        else modal.remove();
      };
      var cancelBtn = modal.querySelector('#fcc-new-season-cancel');
      if (cancelBtn) cancelBtn.addEventListener('click', function () { closeModal(); });
      var proceed = modal.querySelector('#fcc-new-season-proceed');
      if (proceed) proceed.addEventListener('click', async function () {
        playSound('confirm-1-lowervol.wav');
        (env.flashSeasonAdvanceScreen || flashSeasonAdvanceScreen)();
        var seasonText = playNowBtn.textContent;
        playNowBtn.disabled = true;
        playNowBtn.textContent = 'Starting...';
        closeModal();

        var goToNextSeasonFcc = function () {
          var nextUrl = '/franchise-command-center.html?franchise_id=' + encodeURIComponent(franchiseId);
          if (window.GOBNav && window.GOBNav.exitFlow) window.GOBNav.exitFlow(nextUrl, { tab: 'home-tab' });
          else if (window.GOBNav) window.GOBNav.replace(nextUrl);
          else window.location.replace(nextUrl);
        };
        var startFinishSeason = function () {
          return fetch(window.API_CONFIG.buildUrl('/franchise/finish-season'), {
            method: 'POST',
            headers: Object.assign({ 'Content-Type': 'application/json' }, window.API_CONFIG.getAuthHeaders()),
            body: JSON.stringify({ franchise_id: franchiseId }),
          }).then(function (res) {
            if (!res.ok) throw new Error('Finish season failed');
            return res.json();
          });
        };
        var failAdvance = function (err, overlay) {
          console.error(err);
          if (overlay) overlay.remove();
          if (window.SeniorTribute && window.SeniorTribute.teardown) window.SeniorTribute.teardown();
          alert('Unable to start new season');
          playNowBtn.disabled = false;
          playNowBtn.textContent = seasonText;
        };
        var nextSeason = env.nextSeasonNumber ? env.nextSeasonNumber() : (Number((env.topData && env.topData.current_season) || 1) + 1);
        var showCover = env.showSeasonAdvanceOverlay || showSeasonAdvanceOverlay;
        var hex = env.normalizeHexColor || normalizeHexColor;

        var tribute = null;
        try {
          tribute = await fetchJSON(window.API_CONFIG.buildUrl('/franchise/senior-tribute') + '?franchise_id=' + encodeURIComponent(franchiseId));
        } catch (err5) {
          console.warn('[TRIBUTE] snapshot failed; using load cover', err5);
        }
        var seniors = (tribute && tribute.players) || [];

        if (!seniors.length || !window.SeniorTribute) {
          var advanceOverlay = showCover(nextSeason);
          try {
            await startFinishSeason();
            goToNextSeasonFcc();
          } catch (err6) {
            failAdvance(err6, advanceOverlay);
          }
          return;
        }

        var finishState = 'pending';
        var finishPromise = startFinishSeason()
          .then(function () { finishState = 'ok'; })
          .catch(function (err) { finishState = 'err'; throw err; });

        window.SeniorTribute.start({
          players: seniors,
          season: tribute.season || (env.topData && env.topData.current_season) || 1,
          teamColor: hex(env.topData && env.topData.primary_color) || undefined,
          onAdvance: async function () {
            var overlay = null;
            if (finishState === 'pending') {
              overlay = showCover(nextSeason);
              window.SeniorTribute.teardown();
            }
            try {
              await finishPromise;
              goToNextSeasonFcc();
            } catch (err7) {
              failAdvance(err7, overlay);
            }
          },
        });
      });
      return;
    }

    console.log('Play Now click search:', typeof currentSearch === 'function' ? currentSearch() : window.location.search);
    var playText = advanceLabel;
    playNowBtn.disabled = true;
    if (!franchiseId) {
      alert('Franchise not loaded');
      playNowBtn.disabled = false;
      playNowBtn.textContent = playText;
      settleAdvance();
      return;
    }
    try {
      var playRes = await fetch(window.API_CONFIG.buildUrl('/franchise/play-next-game'), {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json' }, window.API_CONFIG.getAuthHeaders()),
        body: JSON.stringify({ franchise_id: franchiseId }),
      });
      if (!playRes.ok) throw new Error('Simulation failed');
      var body = await playRes.json();
      var home = body.home;
      var away = body.away;
      var playWeek = body.week;
      var home_id = body.home_id;
      var away_id = body.away_id;
      var home_display = body.home_display;
      var away_display = body.away_display;
      if (!home || !away) throw new Error('Matchup not found');
      try {
        if (franchiseId && window.FranchiseLS) window.FranchiseLS.setWeek(franchiseId, playWeek);
      } catch (err8) {}
      var resolvedSide = '';
      if (userTeamId && home_id != null && away_id != null) {
        if (String(userTeamId) === String(home_id)) resolvedSide = 'home';
        else if (String(userTeamId) === String(away_id)) resolvedSide = 'away';
      }
      if (!resolvedSide) {
        var userName = env.userTeamName || '';
        resolvedSide = (userName === home ? 'home' : (userName === away ? 'away' : ''));
      }
      var url = '/set-lineup.html?mode=franchise&franchise_id=' + encodeURIComponent(franchiseId)
        + '&week=' + playWeek
        + '&home=' + encodeURIComponent(home)
        + '&away=' + encodeURIComponent(away)
        + '&home_id=' + encodeURIComponent(home_id)
        + '&away_id=' + encodeURIComponent(away_id);
      if (home_display) url += '&home_display=' + encodeURIComponent(home_display);
      if (away_display) url += '&away_display=' + encodeURIComponent(away_display);
      if (userTeamId) url += '&team_id=' + encodeURIComponent(userTeamId) + '&user_team_id=' + encodeURIComponent(userTeamId);
      if (resolvedSide) url += '&my_team=' + resolvedSide;
      console.log('Navigating to', url);
      var navigateToLineup = async function () {
        await confirmSfxReady;
        try {
          var musicPlay = await import('/js/musicController.js');
          musicPlay.clearFranchiseMusicState();
        } catch (err9) {}
        if (window.GOBNav) window.GOBNav.go(url);
        else window.location.assign(url);
      };
      if (window.GOBTutorialAlerts) {
        var playBlocked = await window.GOBTutorialAlerts.interceptPlayNextGame(franchiseId, url, navigateToLineup);
        if (playBlocked) {
          playNowBtn.disabled = false;
          playNowBtn.textContent = playText;
          settleAdvance();
          return;
        }
      } else {
        await navigateToLineup();
      }
    } catch (err10) {
      console.error(err10);
      alert('Unable to play next game');
      playNowBtn.disabled = false;
      playNowBtn.textContent = playText;
      settleAdvance();
    }
  }

  function apiUrl(franchiseId) {
    return window.API_CONFIG.buildUrl('/franchise/command-center/data') + '?franchise_id=' + encodeURIComponent(franchiseId) + '&profile=1';
  }

  function defaultFetchJSON(url) {
    return fetch(url, { headers: window.API_CONFIG.getAuthHeaders() }).then(function (res) {
      if (!res.ok) throw new Error('Request failed');
      return res.json();
    });
  }

  async function defaultRecover(topData) {
    if (!cpuSimNeedsRecovery(topData)) return topData;
    var franchiseId = queryId('franchise_id');
    var resume = topData.cpu_sim_resume || {};
    var week = Number(resume.week || topData.week || 0);
    if (!franchiseId || !week) return topData;
    try {
      var mod = await import('/js/phaser/utils/franchisePhaseBClient.js');
      await mod.getOrStartFranchisePhaseB({ franchise_id: franchiseId, week: week });
    } catch (err) {}
    return defaultFetchJSON(apiUrl(franchiseId));
  }

  function defaultOpenRecruiting() {
    var params = emptyParams();
    var franchiseId = queryId('franchise_id');
    var teamId = queryId('team_id') || queryId('user_team_id');
    if (franchiseId) params.set('franchise_id', franchiseId);
    if (teamId) params.set('team_id', teamId);
    params.set('from', 'fcc');
    params.set('return_url', currentRelativeUrl());
    var url = '/recruiting.html?' + params.toString();
    var seen = franchiseId && window.API_CONFIG
      ? fetch(window.API_CONFIG.buildUrl('/franchise/recruiting-wire-seen'), {
          method: 'PATCH',
          headers: Object.assign({ 'Content-Type': 'application/json' }, window.API_CONFIG.getAuthHeaders ? window.API_CONFIG.getAuthHeaders() : {}),
          body: JSON.stringify({ franchise_id: franchiseId }),
        }).catch(function () {})
      : Promise.resolve();
    return seen.then(function () {
      if (window.GOBNav && window.GOBNav.go) window.GOBNav.go(url);
      else window.location.assign(url);
    });
  }

  function defaultCutUrl() {
    var params = emptyParams();
    params.set('franchise_id', queryId('franchise_id'));
    params.set('team_id', queryId('team_id') || queryId('user_team_id'));
    params.set('from', 'fcc');
    params.set('return_url', currentRelativeUrl());
    return '/cut-players.html?' + params.toString();
  }

  function browseEnv(data) {
    var franchiseId = queryId('franchise_id') || (data && data.franchise_id) || '';
    var teamId = queryId('team_id') || queryId('user_team_id') || (data && (data.user_team_id || data.team_id)) || '';
    return {
      franchiseId: franchiseId,
      userTeamId: teamId,
      userTeamName: (data && data.team) || '',
      topData: data,
      fetchJSON: defaultFetchJSON,
      fccCpuSimNeedsRecovery: cpuSimNeedsRecovery,
      recoverCpuSimsBeforeFccRender: defaultRecover,
      emptyParams: emptyParams,
      getCurrentRelativeUrl: currentRelativeUrl,
      openRecruitingSurface: defaultOpenRecruiting,
      buildAssignPracticeSquadUrl: defaultCutUrl,
      fccEosSimOverlayCopy: eosOverlayCopy,
      showNewSeasonConfirmModal: showNewSeasonConfirmModal,
      flashSeasonAdvanceScreen: flashSeasonAdvanceScreen,
      showSeasonAdvanceOverlay: showSeasonAdvanceOverlay,
      normalizeHexColor: normalizeHexColor,
      nextSeasonNumber: function () {
        return Number((data && data.current_season) || 1) + 1;
      },
    };
  }

  function applyData(data, reused) {
    if (!data) return;
    window.__gobCommandCenterData = data;
    var env = browseEnv(data);
    updatePlayButton(data, env);
    updateEditRecruitingButton(data, env);
    var btn = document.getElementById('play-now');
    if (btn) btn.disabled = false;
    if (window.GOBShell && window.GOBShell.syncTop) window.GOBShell.syncTop(data);
    if (window.GOBShell && window.GOBShell.noteCommandCenter) window.GOBShell.noteCommandCenter(data, reused);
  }

  function load() {
    installFetchWatch();
    if (window.__gobCommandCenterData) {
      window.__gobAdvanceLoadMs = 0;
      window.__gobAdvanceLoadReused = true;
      applyData(window.__gobCommandCenterData, true);
      return Promise.resolve(window.__gobCommandCenterData);
    }
    return new Promise(function (resolve) {
      window.setTimeout(function () {
        if (window.__gobCommandCenterData) {
          window.__gobAdvanceLoadMs = window.__gobAdvanceLoadMs || 0;
          window.__gobAdvanceLoadReused = true;
          applyData(window.__gobCommandCenterData, true);
          resolve(window.__gobCommandCenterData);
          return;
        }
        if (ccInflight) {
          ccInflight.then(function (data) {
            window.__gobAdvanceLoadReused = true;
            applyData(data, true);
            resolve(data);
          });
          return;
        }
        var franchiseId = queryId('franchise_id');
        if (!franchiseId || !window.API_CONFIG) {
          resolve(null);
          return;
        }
        var started = performance.now();
        defaultFetchJSON(apiUrl(franchiseId)).then(function (data) {
          window.__gobAdvanceLoadMs = performance.now() - started;
          window.__gobAdvanceLoadReused = false;
          applyData(data, false);
          resolve(data);
        }).catch(function () { resolve(null); });
      }, 0);
    });
  }

  function ordersAreFocus(data) {
    if (queryId('action') === 'run') return true;
    if (!data) return false;
    var week = Number(data.week || 1);
    var wire = data.recruiting_wire || {};
    if (week >= INVITE_FIRST_WEEK && week <= INVITE_LAST_WEEK && Number(wire.board_saved_week || 0) !== week) return true;
    if (week === SIGNING_DAY_WEEK && !wire.week_35_orders_submitted) return true;
    return false;
  }

  installFetchWatch();

  window.GOBAdvance = {
    updatePlayButton: updatePlayButton,
    updateEditRecruitingButton: updateEditRecruitingButton,
    bind: bind,
    load: load,
    browseEnv: browseEnv,
    ordersAreFocus: ordersAreFocus,
    cpuSimNeedsRecovery: cpuSimNeedsRecovery,
  };
})();
