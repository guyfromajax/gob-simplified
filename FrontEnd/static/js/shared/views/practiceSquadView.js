/**
 * Team › Practice Squad. The regional practice-squad league.
 * Standings order, win_pct, and is_user come from the standings GET.
 * The schedule opens on current_week and loads one week at a time.
 */

var TIER_LABELS = {
  '1': 'All-Americans',
  '2': 'All-Stars',
  '3': 'Varsity',
  '4': 'JV',
  '5': 'Squad'
};

var BLANK_LOGO = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';

function standingsUrl(tables, franchiseId) {
  return tables.apiBase('/franchise/practice-squad/standings')
    + '?franchise_id=' + encodeURIComponent(franchiseId);
}

function scheduleUrl(tables, franchiseId, week) {
  var url = tables.apiBase('/franchise/practice-squad/schedule')
    + '?franchise_id=' + encodeURIComponent(franchiseId);
  if (week != null) url += '&week=' + encodeURIComponent(week);
  return url;
}

function bracketsUrl(tables, franchiseId) {
  return tables.apiBase('/franchise/practice-squad/brackets')
    + '?franchise_id=' + encodeURIComponent(franchiseId);
}

function psWeekFromUrl() {
  try {
    var raw = new URLSearchParams(window.location.search).get('ps_week');
    var n = Number(raw);
    if (raw != null && raw !== '' && isFinite(n)) return n;
  } catch (err) { /* the server picks current_week */ }
  return null;
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var franchiseId = (ctx && ctx.franchiseId) || '';
  var teamId = (ctx && ctx.teamId) || '';
  var standings = null;
  var meta = null;
  var weekBody = null;
  var brackets = null;
  var requested = psWeekFromUrl();
  var loaded = false;
  var signature = '';

  function writeWeek(week) {
    try {
      var url = new URL(window.location.href);
      url.searchParams.set('tab', 'practice-squad-view');
      url.searchParams.set('ps_week', String(week));
      var next = url.pathname + url.search + url.hash;
      if (next === window.location.pathname + window.location.search + window.location.hash) return;
      window.history.replaceState(window.history.state, '', next);
      if (window.GOBNav && typeof window.GOBNav.syncCurrent === 'function') window.GOBNav.syncCurrent();
    } catch (err) { /* the table still shows the week */ }
  }

  function rosterHref(psTeamId) {
    var back = window.location.pathname + window.location.search;
    return '/team-roster-view.html?mode=practice_squad'
      + '&ps_team_id=' + encodeURIComponent(psTeamId)
      + '&franchise_id=' + encodeURIComponent(franchiseId)
      + '&team_id=' + encodeURIComponent(teamId)
      + '&return_url=' + encodeURIComponent(back);
  }

  function boxHref(gameId) {
    var back = window.location.pathname + window.location.search;
    return '/box-score.html?game_id=' + encodeURIComponent(gameId)
      + '&mode=practice_squad'
      + '&franchise_id=' + encodeURIComponent(franchiseId)
      + '&team_id=' + encodeURIComponent(teamId)
      + '&return_url=' + encodeURIComponent(back);
  }

  function userIds() {
    var ids = {};
    ((standings && standings.tiers) || []).forEach(function (tier) {
      (tier.rows || []).forEach(function (row) {
        if (row.is_user) ids[row.team_id] = true;
      });
    });
    return ids;
  }

  function weeks() {
    return (meta && meta.weeks) || [];
  }

  function shownWeek() {
    if (weekBody && weekBody.week != null) return weekBody.week;
    if (requested != null) return requested;
    return meta ? meta.current_week : '';
  }

  function neighbor(dir) {
    var list = weeks();
    var here = shownWeek();
    var index = -1;
    var i;
    for (i = 0; i < list.length; i++) {
      if (list[i] === here) index = i;
    }
    if (index < 0) return null;
    i = index + dir;
    if (i < 0 || i >= list.length) return null;
    return list[i];
  }

  function paintTools(slot) {
    if (!standings || !standings.initialized) {
      slot.innerHTML = '';
      return;
    }
    var week = shownWeek();
    var prev = neighbor(-1);
    var next = neighbor(1);
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
        loadWeek();
      });
    });
  }

  function ownTools() {
    tables.registerTools('practice-squad-view', paintTools);
    tables.placeTools();
    var slot = document.querySelector('#gob-subtabs .pg-tools[data-owner="practice-squad-view"]');
    if (slot) paintTools(slot);
  }

  function teamLink(id, name) {
    return '<a href="' + tables.esc(rosterHref(id)) + '">' + tables.esc(name || id) + '</a>';
  }

  function standingsHtml() {
    var tiers = (standings && standings.tiers) || [];
    var html = '<div class="gob-ps-grid">';
    tiers.forEach(function (tier) {
      html += '<section class="gob-tcard"><h2>' + tables.esc(tier.label || TIER_LABELS[tier.tier] || '') + '</h2>'
        + '<table class="gob-tbl"><thead><tr>'
        + '<th class="team">Team</th><th>W</th><th>L</th><th>PCT</th>'
        + '</tr></thead><tbody>';
      if (!tier.rows || !tier.rows.length) {
        html += '<tr><td class="team" colspan="4">No data</td></tr>';
      }
      (tier.rows || []).forEach(function (row) {
        var cls = row.is_user ? ' class="me"' : '';
        html += '<tr' + cls + '>'
          + '<td class="team">' + teamLink(row.team_id, row.name) + '</td>'
          + '<td>' + tables.esc(row.w) + '</td>'
          + '<td>' + tables.esc(row.l) + '</td>'
          + '<td>' + tables.esc(tables.formatPct(row.win_pct)) + '</td></tr>';
      });
      html += '</tbody></table></section>';
    });
    html += '</div>';
    return html;
  }

  function scheduleHtml() {
    var games = (weekBody && weekBody.games) || [];
    var html = '<section class="gob-tcard gob-ps-schedule"><h2>Schedule</h2>'
      + '<table class="gob-tbl gob-sched"><thead><tr>'
      + '<th class="team">Away</th><th class="num">Result</th><th class="team">Home</th><th class="box">Box score</th>'
      + '</tr></thead><tbody>';
    if (!games.length) {
      html += '<tr><td class="team" colspan="4">No games</td></tr>';
    }
    games.forEach(function (game) {
      var result = '—';
      if (game.status === 'completed' && game.home_score != null && game.away_score != null) {
        result = String(game.away_score) + '-' + String(game.home_score);
      } else if (game.status === 'forfeit') {
        result = 'Forfeit';
      }
      var box = '—';
      if (game.status === 'completed' && game.game_id) {
        box = '<a class="gob-box" href="' + tables.esc(boxHref(game.game_id)) + '">Box score</a>';
      }
      html += '<tr>'
        + '<td class="team">' + teamLink(game.away_team_id, game.away_display || game.away_team_id) + '</td>'
        + '<td class="num">' + tables.esc(result) + '</td>'
        + '<td class="team">' + teamLink(game.home_team_id, game.home_display || game.home_team_id) + '</td>'
        + '<td class="box">' + box + '</td></tr>';
    });
    html += '</tbody></table></section>';
    return html;
  }

  function championshipHtml() {
    var champ = brackets && brackets.championship;
    if (!champ || !champ.game_id) return '';
    var names = nameMap();
    var home = names[champ.home_team_id] || '';
    var away = names[champ.away_team_id] || '';
    var line = away;
    if (champ.away_score != null || champ.home_score != null) {
      line += ' ' + (champ.away_score != null ? champ.away_score : '')
        + '-' + (champ.home_score != null ? champ.home_score : '');
    }
    if (home) line += (line ? ' ' : '') + home;
    return '<p class="gob-ps-champ">' + tables.esc(line)
      + ' <a class="gob-box" href="' + tables.esc(boxHref(champ.game_id)) + '">Box score</a></p>';
  }

  function nameMap() {
    var names = {};
    var teams = (brackets && brackets.teams) || (standings && standings.teams) || {};
    Object.keys(teams).forEach(function (id) {
      var team = teams[id] || {};
      names[id] = team.display_name || id;
    });
    return names;
  }

  function showBracket() {
    var week = Number((standings && standings.week) || 0);
    return !!(standings && standings.initialized && week >= 16 && brackets && brackets.initialized && brackets.tournaments);
  }

  function bracketHtml() {
    if (!showBracket()) return '';
    var html = championshipHtml();
    html += '<div class="gob-ps-brackets">';
    ['1', '2', '3', '4', '5'].forEach(function (tier) {
      var state = brackets.tournaments[tier];
      if (!state || !state.bracket) return;
      html += '<section class="gob-ps-tier"><h2>' + tables.esc(TIER_LABELS[tier] || ('Tier ' + tier)) + '</h2>'
        + '<div class="gob-ps-bracket" data-ps-tier="' + tier + '"></div></section>';
    });
    html += '</div>';
    return html;
  }

  function paintBrackets() {
    if (typeof window.renderBracketShared !== 'function') return;
    var names = nameMap();
    var mine = userIds();
    container.querySelectorAll('.gob-ps-bracket').forEach(function (node) {
      var tier = node.getAttribute('data-ps-tier');
      var state = brackets.tournaments[tier];
      if (!state || !state.bracket) return;
      window.renderBracketShared(node, state.bracket, names, {
        arena: true,
        tournamentLabel: TIER_LABELS[tier] || 'Practice Squad',
        getLogo: function () { return BLANK_LOGO; },
        isUserTeam: function (id) { return !!mine[String(id)]; }
      });
    });
  }

  function render() {
    if (!standings || !standings.initialized) {
      container.innerHTML = '<p class="gob-ps-empty">Practice Squad has not started yet (available after Week 1 Training Camp).</p>';
      ownTools();
      return;
    }
    container.innerHTML = '<div class="gob-ps">' + bracketHtml() + standingsHtml() + scheduleHtml() + '</div>';
    paintBrackets();
    ownTools();
  }

  function apply() {
    var stamp = JSON.stringify([standings, meta, weekBody, brackets]);
    if (loaded && stamp === signature) {
      ownTools();
      return;
    }
    signature = stamp;
    loaded = true;
    if (standings && standings.initialized && shownWeek() !== '') writeWeek(shownWeek());
    render();
  }

  function loadWeek() {
    var store = ctx && ctx.store;
    if (!store || requested == null) return;
    store.get(scheduleUrl(tables, franchiseId, requested)).then(function (body) {
      weekBody = body || {};
      apply();
    }).catch(function () {
      tables.paintError(container, 'Practice Squad could not be opened.', load);
    });
  }

  function load() {
    var store = ctx && ctx.store;
    if (!store || typeof store.get !== 'function' || !franchiseId) {
      tables.paintError(container, 'Practice Squad could not be opened.', load);
      return;
    }
    if (!loaded) tables.paintSkeleton(container);
    store.get(standingsUrl(tables, franchiseId)).then(function (body) {
      standings = body || {};
      if (!standings.initialized) {
        apply();
        return null;
      }
      return store.get(scheduleUrl(tables, franchiseId));
    }).then(function (body) {
      if (!body) return null;
      meta = body;
      if (requested == null) requested = body.current_week;
      var jobs = [store.get(scheduleUrl(tables, franchiseId, requested))];
      if (Number(standings.week || 0) >= 16) jobs.push(store.get(bracketsUrl(tables, franchiseId)));
      return Promise.all(jobs);
    }).then(function (parts) {
      if (!parts) return;
      weekBody = parts[0] || {};
      brackets = parts[1] || null;
      apply();
    }).catch(function () {
      loaded = false;
      tables.paintError(container, 'Practice Squad could not be opened.', load);
    });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!loaded || !store || typeof store.revalidate !== 'function' || !franchiseId) return;
    store.revalidate(standingsUrl(tables, franchiseId)).then(function (body) {
      if (body) standings = body;
      if (!standings || !standings.initialized) {
        apply();
        return null;
      }
      return store.revalidate(scheduleUrl(tables, franchiseId, shownWeek()));
    }).then(function (body) {
      if (body) weekBody = body;
      apply();
    }).catch(function () { /* keep the mounted tables */ });
  }

  function onTab(event) {
    var tab = event && event.detail && event.detail.tab;
    if (tab !== 'practice-squad-view') return;
    if (!loaded) load();
    else {
      revalidate();
      ownTools();
    }
  }

  document.addEventListener('gob-tab-shown', onTab);
  load();

  return {
    revalidate: revalidate,
    unmount: function () {
      document.removeEventListener('gob-tab-shown', onTab);
      tables.registerTools('practice-squad-view', null);
    }
  };
}

export function unmount() {}
