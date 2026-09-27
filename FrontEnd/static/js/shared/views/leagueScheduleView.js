/**
 * League › Schedule. One national week from GET /franchise/schedule/week.
 * Order, scores, ranks, and which weeks have games come from that payload.
 */

function weekUrl(tables, franchiseId, week) {
  var url = tables.apiBase('/franchise/schedule/week')
    + '?franchise_id=' + encodeURIComponent(franchiseId);
  if (week != null) url += '&week=' + encodeURIComponent(week);
  return url;
}

function weekFromUrl() {
  try {
    var raw = new URLSearchParams(window.location.search).get('week');
    var n = Number(raw);
    if (raw != null && raw !== '' && isFinite(n)) return n;
  } catch (err) { /* the server picks the current week */ }
  return null;
}

function backForward() {
  try {
    var nav = performance.getEntriesByType('navigation')[0];
    return !!(nav && nav.type === 'back_forward');
  } catch (err) {
    return false;
  }
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var franchiseId = (ctx && ctx.franchiseId) || '';
  var teamId = (ctx && ctx.teamId) || '';
  var payload = null;
  var loaded = false;
  var restoredScroll = false;
  var signature = '';
  var requested = weekFromUrl();

  function restoreScroll() {
    if (restoredScroll || !backForward()) return;
    restoredScroll = true;
    var nav = ctx && ctx.nav;
    if (!nav || typeof nav.restoreScroll !== 'function') return;
    requestAnimationFrame(function () {
      nav.restoreScroll();
      requestAnimationFrame(function () { nav.restoreScroll(); });
    });
  }

  function writeWeek(week) {
    try {
      var url = new URL(window.location.href);
      url.searchParams.set('tab', 'league-schedule-view');
      url.searchParams.set('week', String(week));
      var next = url.pathname + url.search + url.hash;
      if (next === window.location.pathname + window.location.search + window.location.hash) return;
      window.history.replaceState(window.history.state, '', next);
      if (window.GOBNav && typeof window.GOBNav.syncCurrent === 'function') window.GOBNav.syncCurrent();
    } catch (err) { /* the table still shows the week */ }
  }

  function teamHref(viewTeamId) {
    var q = new URLSearchParams(window.location.search);
    q.set('tab', 'team-view');
    q.set('view_team_id', viewTeamId);
    q.set('origin', 'league');
    q.set('return_tab', 'league-schedule-view');
    q.delete('player_id');
    q.delete('pager');
    q.delete('up');
    var text = q.toString();
    return window.location.pathname + (text ? '?' + text : '');
  }

  function boxHref(gameId) {
    return '/box-score.html?game_id=' + encodeURIComponent(gameId)
      + '&mode=franchise&franchise_id=' + encodeURIComponent(franchiseId)
      + '&team_id=' + encodeURIComponent(teamId);
  }

  function sideName(side) {
    var rank = Number(side && side.natl_rank);
    var name = (side && side.name) || '';
    if (isFinite(rank) && rank >= 1 && rank < 999) return '#' + rank + ' ' + name;
    return name;
  }

  function teamCell(side) {
    if (!side || !side.team_id) return '—';
    return '<a class="gob-team" data-gob-drill href="' + tables.esc(teamHref(side.team_id)) + '">'
      + tables.markHtml(side.name, side.primary_color)
      + '<span>' + tables.esc(sideName(side)) + '</span></a>';
  }

  function scoreCell(game) {
    var text = '—';
    if (game.status === 'complete' && game.away_score != null && game.home_score != null) {
      text = String(game.away_score) + '-' + String(game.home_score);
    }
    if (!game.tournament_context) return tables.esc(text);
    return tables.esc(text) + '<span class="sub">' + tables.esc(game.tournament_context) + '</span>';
  }

  function boxCell(game) {
    if (game.status !== 'complete' || !game.game_id) return '—';
    return '<a class="gob-box" href="' + tables.esc(boxHref(game.game_id)) + '">Box score</a>';
  }

  function neighbor(dir) {
    var weeks = (payload && payload.weeks) || [];
    var here = payload ? payload.week : 0;
    var index = -1;
    var i;
    for (i = 0; i < weeks.length; i++) {
      if (weeks[i].week === here) index = i;
    }
    if (index < 0) return null;
    i = index + dir;
    while (i >= 0 && i < weeks.length) {
      if (weeks[i].enabled) return weeks[i].week;
      i += dir;
    }
    return null;
  }

  function paintTools(slot) {
    var week = payload ? payload.week : (requested || '');
    var prev = payload ? neighbor(-1) : null;
    var next = payload ? neighbor(1) : null;
    slot.innerHTML = '<div class="gob-wk" role="group" aria-label="Week">'
      + '<button type="button" data-week-step="-1"' + (prev == null ? ' disabled' : '')
      + ' aria-label="Previous week">‹</button>'
      + '<span class="gob-wk-label">Week ' + tables.esc(week) + '</span>'
      + '<button type="button" data-week-step="1"' + (next == null ? ' disabled' : '')
      + ' aria-label="Next week">›</button></div>';
    slot.querySelectorAll('button').forEach(function (button) {
      button.addEventListener('click', function () {
        var dir = Number(button.getAttribute('data-week-step'));
        var target = neighbor(dir);
        if (target == null) return;
        requested = target;
        load(false);
      });
    });
  }

  function ownTools() {
    tables.registerTools('league-schedule-view', paintTools);
    tables.placeTools();
    var slot = document.querySelector('#gob-subtabs .pg-tools[data-owner="league-schedule-view"]');
    if (slot) paintTools(slot);
  }

  function render() {
    var games = (payload && payload.games) || [];
    var title = payload && payload.label && payload.label.indexOf(':') >= 0
      ? payload.label.split(':').slice(1).join(':').trim()
      : '';
    var html = '<section class="gob-tcard">';
    if (title) html += '<p class="gob-sch-round">' + tables.esc(title) + '</p>';
    html += '<div class="gob-scroll"><table class="gob-tbl"><thead><tr>'
      + '<th>Away</th><th>Home</th><th>Result</th><th>Box score</th>'
      + '</tr></thead><tbody>';
    if (!games.length) {
      var empty = payload && payload.week >= 27
        ? 'No tournament matchups available yet.'
        : 'No games scheduled.';
      html += '<tr><td colspan="4">' + tables.esc(empty) + '</td></tr>';
    }
    games.forEach(function (game) {
      var cls = game.is_user ? ' class="me is-user"' : '';
      html += '<tr' + cls + '>'
        + '<td>' + teamCell(game.away) + '</td>'
        + '<td>' + teamCell(game.home) + '</td>'
        + '<td>' + scoreCell(game) + '</td>'
        + '<td>' + boxCell(game) + '</td></tr>';
    });
    html += '</tbody></table></div></section>';
    container.innerHTML = html;
    container.querySelectorAll('a[data-gob-drill]').forEach(function (link) {
      link.addEventListener('click', function (event) {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
        event.preventDefault();
        if (window.GOBViews && typeof window.GOBViews.open === 'function') {
          window.GOBViews.open(link.getAttribute('href'), 'push');
        }
      });
    });
    ownTools();
    restoreScroll();
  }

  function apply(next) {
    var stamp = JSON.stringify(next || {});
    if (loaded && stamp === signature) {
      ownTools();
      return;
    }
    signature = stamp;
    payload = next || {};
    loaded = true;
    if (payload.week != null) writeWeek(payload.week);
    render();
  }

  function load(first) {
    var store = ctx && ctx.store;
    if (!store || typeof store.get !== 'function' || !franchiseId) {
      tables.paintError(container, 'Schedule could not be opened.', function () { load(true); });
      return;
    }
    if (first || !loaded) tables.paintSkeleton(container);
    store.get(weekUrl(tables, franchiseId, requested)).then(function (body) {
      apply(body || {});
    }).catch(function () {
      loaded = false;
      tables.paintError(container, 'Schedule could not be opened.', function () { load(true); });
    });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!loaded || !store || typeof store.revalidate !== 'function' || !franchiseId) return;
    store.revalidate(weekUrl(tables, franchiseId, payload && payload.week)).then(function (body) {
      if (body) apply(body);
    }).catch(function () { /* keep the mounted table */ });
  }

  function onTab(event) {
    var tab = event && event.detail && event.detail.tab;
    if (tab !== 'league-schedule-view') return;
    requested = weekFromUrl() != null ? weekFromUrl() : (payload && payload.week);
    if (!loaded) load(true);
    else revalidate();
    ownTools();
  }

  document.addEventListener('gob-tab-shown', onTab);
  ownTools();
  load(true);

  return {
    revalidate: revalidate,
    unmount: function () {
      document.removeEventListener('gob-tab-shown', onTab);
      tables.registerTools('league-schedule-view', null);
    }
  };
}

export function unmount() {}
