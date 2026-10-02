/**
 * News › Awards. All-American teams from GET /franchise/awards.
 *
 * Weeks 1-34 it is the projection ("Projected All-Americans", rebuilt once a week and
 * frozen through the tournaments). After the National Tournament it is the final.
 * Each team is one player per position, PG to C. No season selector, no portraits. Navy
 * row is the user's team. How the teams are picked is not shown: the page has the
 * status, the player, the rating and the stat line, and the response carries no weights,
 * scores, ranks or bonus.
 */

var TEAMS = [
  { key: 'first_team', label: '1st Team All-American' },
  { key: 'second_team', label: '2nd Team All-American' },
  { key: 'third_team', label: '3rd Team All-American' }
];

var STATS = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'DEF%'];

function sameId(a, b) {
  return String(a || '') !== '' && String(a) === String(b || '');
}

function formatYear(year) {
  if (window.GOB_PlayerYear && typeof window.GOB_PlayerYear.formatDisplay === 'function') {
    return window.GOB_PlayerYear.formatDisplay(year);
  }
  return year || '--';
}

function statText(stats, key, perGame) {
  var value = stats ? stats[key] : null;
  if (value == null || value === '') return '--';
  if (key === 'DEF%') return String(value) + '%';
  if (perGame && typeof value === 'number') return value.toFixed(1);
  return String(value);
}

function hasStats(teams) {
  return TEAMS.some(function (team) {
    return (teams[team.key] || []).some(function (player) {
      var stats = player.stats || {};
      return STATS.some(function (key) { return stats[key] != null && stats[key] !== ''; });
    });
  });
}

function hasField(teams, field) {
  return TEAMS.some(function (team) {
    return (teams[team.key] || []).some(function (player) { return player[field] != null && player[field] !== ''; });
  });
}

function rtCell(rating) {
  if (typeof rating !== 'number') return '<td>--</td>';
  var text = typeof window.formatRtDisplay === 'function' ? window.formatRtDisplay(rating) : String(Math.round(rating));
  var cls = typeof window.getRtBucketClass === 'function' ? window.getRtBucketClass(rating) : '';
  return '<td' + (cls ? ' class="' + cls + '"' : '') + '>' + text + '</td>';
}

/**
 * Title and the status under it: "Preseason", "After week N", "End of regular season ·
 * Not final: tournament play can still change these", or "Final".
 */
function headHtml(body, esc) {
  var status = body && body.status;
  if (status !== 'projected') {
    return '<header class="gob-awards-head"><h2>All-Americans</h2>'
      + (status === 'final' ? '<p>Final</p>' : '')
      + '</header>';
  }
  var parts = [esc(body.label || 'Projected')];
  if (Number(body.week) >= 26) parts.push('Not final: tournament play can still change these');
  return '<header class="gob-awards-head"><h2>Projected All-Americans</h2><p>'
    + parts.join('<span aria-hidden="true"> \u00b7 </span>') + '</p></header>';
}

export function mount(container, ctx) {
  var tables = window.GOBTables;
  var body = null;
  var signature = '';
  var loaded = false;
  var alive = true;
  var userId = (ctx && ctx.teamId) || '';
  var franchiseId = (ctx && ctx.franchiseId) || '';

  function playerHref(player) {
    var params = new URLSearchParams(window.location.search);
    params.set('tab', 'player-view');
    params.set('player_id', player.player_id || '');
    params.set('origin', 'league');
    params.set('up', 'Awards');
    params.set('return_tab', 'awards-view');
    params.delete('story');
    params.delete('view_team_id');
    var text = params.toString();
    return window.location.pathname + (text ? '?' + text : '');
  }

  function teamHref(player) {
    var params = new URLSearchParams(window.location.search);
    params.set('tab', 'team-view');
    params.set('view_team_id', player.team_id || '');
    params.set('origin', 'league');
    params.set('up', 'Awards');
    params.set('return_tab', 'awards-view');
    params.delete('story');
    var text = params.toString();
    return window.location.pathname + (text ? '?' + text : '');
  }

  function render() {
    if (!alive) return;
    var teams = (body && body.all_american_teams) || null;
    if (!teams) {
      container.innerHTML = '<p class="gob-news-empty gob-empty">Awards are not available yet.</p>';
      return;
    }
    var esc = tables.esc;
    // Columns follow the data: an older stored final has no position or rating, and the
    // preseason projection has no stat lines to show.
    var showPos = hasField(teams, 'position');
    var showRt = hasField(teams, 'rating');
    var showStats = hasStats(teams);
    var perGame = body.stats_basis === 'per_game';
    var columns = 3 + (showPos ? 1 : 0) + (showRt ? 1 : 0) + (showStats ? STATS.length : 0);

    var html = '<div class="gob-awards">' + headHtml(body, esc);
    TEAMS.forEach(function (team) {
      var players = teams[team.key] || [];
      html += '<section><h3>' + esc(team.label) + '</h3><div class="gob-tcard">';
      html += '<table class="gob-tbl gob-awards-tbl"><colgroup>';
      if (showPos) html += '<col class="c-pos">';
      html += '<col class="c-player"><col class="c-yr"><col class="c-team">';
      if (showRt) html += '<col class="c-rt">';
      if (showStats) STATS.forEach(function () { html += '<col class="c-stat">'; });
      html += '</colgroup><thead><tr>';
      if (showPos) html += '<th class="left">Pos</th>';
      html += '<th class="left">Player</th><th class="left">Yr</th><th class="left">Team</th>';
      if (showRt) html += '<th>RT</th>';
      if (showStats) STATS.forEach(function (key) { html += '<th>' + esc(key) + '</th>'; });
      html += '</tr></thead><tbody>';
      if (!players.length) {
        html += '<tr><td class="left gob-awards-empty" colspan="' + columns + '">No selections</td></tr>';
      }
      players.forEach(function (player) {
        var mine = sameId(player.team_id, userId);
        var stats = player.stats || {};
        var name = esc(player.name || '--');
        html += '<tr' + (mine ? ' class="me is-user"' : '') + '>';
        if (showPos) html += '<td class="left gob-awards-pos">' + esc(player.position || '--') + '</td>';
        html += '<td class="left">' + (player.player_id
          ? '<a class="gob-player" href="' + esc(playerHref(player)) + '">' + name + '</a>'
          : name) + '</td>';
        html += '<td class="left">' + esc(formatYear(player.year)) + '</td>';
        html += '<td class="left">' + tables.teamLink(
          teamHref(player),
          player.team_name || '--',
          player.team_name || '',
          ''
        ) + '</td>';
        if (showRt) html += rtCell(player.rating);
        if (showStats) {
          STATS.forEach(function (key) {
            html += '<td>' + esc(statText(stats, key, perGame)) + '</td>';
          });
        }
        html += '</tr>';
      });
      html += '</tbody></table></div></section>';
    });
    if (showStats && perGame) {
      html += '<p class="gob-awards-note">Stats are per game, regular season.</p>';
    }
    html += '</div>';
    container.innerHTML = html;
    container.querySelectorAll('a.gob-team, a.gob-player').forEach(function (link) {
      link.addEventListener('click', function (event) {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
        event.preventDefault();
        if (window.GOBViews && typeof window.GOBViews.open === 'function') {
          window.GOBViews.open(link.getAttribute('href'), 'push');
        }
      });
    });
  }

  function apply(next) {
    var stamp = JSON.stringify(next || {});
    if (loaded && stamp === signature) return;
    signature = stamp;
    body = next;
    loaded = true;
    render();
  }

  function unavailable() {
    if (!alive) return;
    loaded = true;
    body = null;
    signature = 'unavailable';
    container.innerHTML = '<p class="gob-news-empty gob-empty">Awards are not available yet.</p>';
  }

  function fail() {
    if (!alive) return;
    tables.paintError(container, 'This view could not be opened.', load);
  }

  function load() {
    var store = ctx && ctx.store;
    if (!store || typeof store.get !== 'function' || !franchiseId) {
      fail();
      return;
    }
    if (!loaded) tables.paintSkeleton(container);
    store.get(tables.apiBase('/franchise/awards') + '?franchise_id=' + encodeURIComponent(franchiseId))
      .then(function (payload) { apply(payload); })
      .catch(function (err) {
        if (err && err.status === 400) unavailable();
        else fail();
      });
  }

  function revalidate() {
    var store = ctx && ctx.store;
    if (!store || !franchiseId) return;
    store.revalidate(tables.apiBase('/franchise/awards') + '?franchise_id=' + encodeURIComponent(franchiseId))
      .then(function (payload) { if (payload) apply(payload); })
      .catch(function (err) {
        if (err && err.status === 400) unavailable();
      });
  }

  load();
  return {
    revalidate: revalidate,
    unmount: function () { alive = false; }
  };
}
