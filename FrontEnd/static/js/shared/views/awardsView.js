/**
 * News › Awards. Week-35 All-American snapshot from GET /franchise/awards.
 * One snapshot: no season selector, no portraits. Navy row is the user's team.
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

function statText(stats, key) {
  var value = stats ? stats[key] : null;
  if (value == null || value === '') return '--';
  if (key === 'DEF%') return String(value) + '%';
  return String(value);
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
      container.innerHTML = '<p class="gob-news-empty">Awards are not available yet.</p>';
      return;
    }
    var html = '<div class="gob-awards">';
    TEAMS.forEach(function (team) {
      var players = teams[team.key] || [];
      html += '<section><h3>' + tables.esc(team.label) + '</h3><div class="gob-tcard">';
      html += '<table class="gob-tbl gob-awards-tbl"><colgroup><col class="c-player"><col class="c-yr"><col class="c-team">';
      STATS.forEach(function () { html += '<col class="c-stat">'; });
      html += '</colgroup><thead><tr><th class="left">Player</th><th class="left">Yr</th><th class="left">Team</th>';
      STATS.forEach(function (key) { html += '<th>' + tables.esc(key) + '</th>'; });
      html += '</tr></thead><tbody>';
      if (!players.length) {
        html += '<tr><td class="left gob-awards-empty" colspan="9">No selections</td></tr>';
      }
      players.forEach(function (player) {
        var mine = sameId(player.team_id, userId);
        var stats = player.stats || {};
        var name = tables.esc(player.name || '--');
        html += '<tr' + (mine ? ' class="me is-user"' : '') + '>';
        html += '<td class="left">' + (player.player_id
          ? '<a class="gob-player" href="' + tables.esc(playerHref(player)) + '">' + name + '</a>'
          : name) + '</td>';
        html += '<td class="left">' + tables.esc(formatYear(player.year)) + '</td>';
        html += '<td class="left">' + tables.teamLink(
          teamHref(player),
          player.team_name || '--',
          player.team_name || '',
          ''
        ) + '</td>';
        STATS.forEach(function (key) {
          html += '<td>' + tables.esc(statText(stats, key)) + '</td>';
        });
        html += '</tr>';
      });
      html += '</tbody></table></div></section>';
    });
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
    container.innerHTML = '<p class="gob-news-empty">Awards are not available yet.</p>';
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
