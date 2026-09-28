/**
 * Module views inside franchise-command-center.html.
 * In-page tabs stay as they are. A registered view loads once, stays mounted,
 * and is shown again with ?tab=<view-id> (rail push, sub-tab replace).
 */
(function (global) {
  'use strict';

  var registry = Object.create(null);
  var mounted = Object.create(null);
  var attempts = Object.create(null);
  var notedTeams = Object.create(null);
  var teamWaiters = Object.create(null);

  function readParams() {
    var fromUrl = new URLSearchParams();
    var fromCtx = null;
    try { fromUrl = new URLSearchParams(global.location.search); }
    catch (err) { fromUrl = new URLSearchParams(); }
    try {
      if (global.FranchiseContext && typeof global.FranchiseContext.toSearchParams === 'function') {
        fromCtx = global.FranchiseContext.toSearchParams();
      }
    } catch (err) { fromCtx = null; }
    function pick(name) {
      return fromUrl.get(name) || (fromCtx && fromCtx.get(name)) || '';
    }
    return {
      franchiseId: pick('franchise_id'),
      urlTeamId: pick('team_id') || pick('user_team_id')
    };
  }

  function teamFromFranchise(franchiseId) {
    if (!franchiseId) return '';
    try {
      if (global.FranchiseLS && typeof global.FranchiseLS.get === 'function') {
        var stored = global.FranchiseLS.get(franchiseId, 'user_team_id');
        if (stored) return String(stored);
      }
    } catch (err) { /* the command-center note is the other source */ }
    return notedTeams[franchiseId] || '';
  }

  function resolveTeamId(read) {
    if (read.urlTeamId) return read.urlTeamId;
    return teamFromFranchise(read.franchiseId);
  }

  function ctx() {
    var read = readParams();
    return {
      franchiseId: read.franchiseId,
      teamId: resolveTeamId(read),
      store: global.GOBStore || null,
      nav: global.GOBNav || null
    };
  }

  function noteUserTeam(franchiseId, teamId) {
    var fid = String(franchiseId || '');
    if (!fid) return;
    if (teamId) notedTeams[fid] = String(teamId);
    var waiting = teamWaiters[fid] || [];
    teamWaiters[fid] = [];
    waiting.forEach(function (done) { done(); });
  }

  function ensureTeam(done) {
    var context = ctx();
    if (context.teamId || !context.franchiseId) {
      done(context);
      return;
    }
    var fid = context.franchiseId;
    if (!teamWaiters[fid]) teamWaiters[fid] = [];
    teamWaiters[fid].push(function () { done(ctx()); });
  }

  function register(spec) {
    if (!spec || !spec.id) return;
    registry[spec.id] = spec;
  }

  function has(id) {
    return !!registry[id];
  }

  function panel(id) {
    return document.getElementById(id);
  }

  function skeleton(host) {
    var html = '<div class="gob-view-skel" aria-hidden="true"><div class="gob-view-skel-bar"></div>';
    var i;
    for (i = 0; i < 8; i++) html += '<div class="gob-view-skel-row"></div>';
    html += '</div>';
    host.innerHTML = html;
  }

  function errorCard(host, onRetry) {
    host.innerHTML = '<div class="gob-view-error" role="alert">'
      + '<p>This view could not be opened.</p>'
      + '<button type="button" class="gob-view-retry">Retry</button>'
      + '</div>';
    var button = host.querySelector('.gob-view-retry');
    if (button) button.addEventListener('click', onRetry);
  }

  function open(url, mode) {
    if (!url) return;
    if (mode === 'push' && global.GOBNav && typeof global.GOBNav.pushSection === 'function') {
      global.GOBNav.pushSection(url);
    } else if (global.history && global.history.replaceState) {
      global.history.replaceState(global.history.state, '', url);
      if (global.GOBNav && typeof global.GOBNav.syncCurrent === 'function') global.GOBNav.syncCurrent();
    }
    var tab = '';
    try { tab = new URL(url, global.location.origin).searchParams.get('tab') || ''; }
    catch (err) { tab = ''; }
    if (global.CommandCenterTabs && tab && typeof global.CommandCenterTabs.show === 'function') {
      global.CommandCenterTabs.show(tab);
    }
    if (mode === 'push') {
      var main = document.querySelector('html.gob-shell .main');
      if (main) main.scrollTop = 0;
    }
  }

  function show(id) {
    var spec = registry[id];
    var host = panel(id);
    if (!host) return Promise.resolve();
    if (!spec) {
      errorCard(host, function () { show(id); });
      return Promise.resolve();
    }
    if (mounted[id]) {
      if (typeof mounted[id].revalidate === 'function') mounted[id].revalidate();
      return Promise.resolve();
    }
    if (host.__gobViewPending) return host.__gobViewPending;
    skeleton(host);
    var attempt = attempts[id] || 0;
    var pending = new Promise(function (resolve) {
      ensureTeam(resolve);
    }).then(function (context) {
      return spec.module(attempt).then(function (mod) {
        return { mod: mod, context: context };
      });
    }).then(function (ready) {
      var mount = ready.mod && (ready.mod.mount || (ready.mod.default && ready.mod.default.mount));
      if (typeof mount !== 'function') throw new Error('missing mount');
      return Promise.resolve(mount(host, ready.context)).then(function (handle) {
        handle = handle || {};
        mounted[id] = handle;
        host.__gobViewPending = null;
        return handle;
      });
    }).catch(function () {
      host.__gobViewPending = null;
      delete mounted[id];
      errorCard(host, function () {
        attempts[id] = (attempts[id] || 0) + 1;
        show(id);
      });
    });
    host.__gobViewPending = pending;
    return pending;
  }

  function unmount(id) {
    var handle = mounted[id];
    if (handle && typeof handle.unmount === 'function') handle.unmount();
    delete mounted[id];
    var host = panel(id);
    if (host) {
      host.__gobViewPending = null;
      host.innerHTML = '';
    }
  }

  function viewModule(file) {
    return function (attempt) {
      var href = '/js/shared/views/' + file;
      if (attempt) href += '?retry=' + attempt;
      return import(href);
    };
  }

  register({
    id: 'rankings-view',
    section: 'league',
    subtab: 'rankings-view',
    title: 'Rankings',
    module: viewModule('rankingsView.js')
  });

  register({
    id: 'standings-view',
    section: 'league',
    subtab: 'standings-view',
    title: 'Standings',
    module: viewModule('standingsView.js')
  });

  register({
    id: 'leaders-view',
    section: 'league',
    subtab: 'leaders-view',
    title: 'Leaders',
    module: viewModule('leadersView.js')
  });

  register({
    id: 'team-stats-view',
    section: 'league',
    subtab: 'team-stats-view',
    title: 'Team Stats',
    module: viewModule('teamStatsView.js')
  });

  register({
    id: 'league-schedule-view',
    section: 'league',
    subtab: 'league-schedule-view',
    title: 'Schedule',
    module: viewModule('leagueScheduleView.js')
  });

  register({
    id: 'tournament-view',
    section: 'league',
    subtab: 'tournament-view',
    title: 'Tournament',
    module: viewModule('tournamentView.js')
  });

  register({
    id: 'roster-view',
    section: 'team',
    subtab: 'roster-view',
    title: 'Roster',
    module: viewModule('rosterView.js')
  });

  register({
    id: 'player-stats-view',
    section: 'team',
    subtab: 'player-stats-view',
    title: 'Player Stats',
    module: viewModule('playerStatsView.js')
  });

  register({
    id: 'team-schedule-view',
    section: 'team',
    subtab: 'team-schedule-view',
    title: 'Schedule',
    module: viewModule('teamScheduleView.js')
  });

  register({
    id: 'practice-squad-view',
    section: 'team',
    subtab: 'practice-squad-view',
    title: 'Practice Squad',
    module: viewModule('practiceSquadView.js')
  });

  register({
    id: 'team-attributes-view',
    section: 'team',
    subtab: 'team-attributes-view',
    title: 'Team Attributes',
    module: viewModule('teamAttributesView.js')
  });

  register({
    id: 'player-view',
    section: 'team',
    subtab: '',
    title: 'Player',
    module: viewModule('playerView.js')
  });

  register({
    id: 'team-view',
    section: 'league',
    subtab: '',
    title: 'Team',
    module: viewModule('teamView.js')
  });

  register({
    id: 'news-view',
    section: 'news',
    subtab: 'news-view',
    title: 'News',
    module: viewModule('newsView.js')
  });

  register({
    id: 'awards-view',
    section: 'news',
    subtab: 'awards-view',
    title: 'Awards',
    module: viewModule('awardsView.js')
  });

  register({
    id: 'training-view',
    section: 'prep',
    subtab: 'training-view',
    title: 'Training',
    module: viewModule('trainingView.js')
  });

  register({
    id: 'training-report-view',
    section: 'prep',
    subtab: 'training-view',
    title: 'Training',
    module: viewModule('trainingReportView.js')
  });

  register({
    id: 'game-plan-view',
    section: 'prep',
    subtab: 'game-plan-view',
    title: 'Game Plan',
    module: viewModule('gamePlanView.js')
  });

  register({
    id: 'scouting-view',
    section: 'prep',
    subtab: 'scouting-view',
    title: 'Scouting Report',
    module: viewModule('scoutingView.js')
  });

  global.GOBViews = {
    register: register,
    has: has,
    show: show,
    open: open,
    unmount: unmount,
    noteUserTeam: noteUserTeam,
    userTeamId: function () { return ctx().teamId; }
  };
})(typeof window !== 'undefined' ? window : this);
